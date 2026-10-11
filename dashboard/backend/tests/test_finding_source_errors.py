import hashlib
import pathlib
import tempfile
import unittest
from unittest.mock import patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.api.endpoints import findings
from app.models.schemas import FindingCreate
from app.services.workspace_sync import WorkspaceSyncService
from app.core.artifact_snapshot import ArtifactChangedError
from app.core.workspace_paths import UnsafeWorkspacePath
from app.services import workspace_sync


class TestFindingSourceErrors(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.service = WorkspaceSyncService(pathlib.Path(tmp.name))
        self.service.create_engagement('fixture', domain='example.test')
        self.path = self.service._resolve_dir('fixture') / 'evidence/broken.md'
        app = FastAPI()
        app.include_router(findings.router)
        self.client = TestClient(app, raise_server_exceptions=False)
        self.addCleanup(self.client.close)
        patcher = patch.object(findings, 'workspace_service', self.service)
        patcher.start()
        self.addCleanup(patcher.stop)

    def details(self):
        detail = self.client.get('/findings/fixture/broken')
        self.assertEqual(detail.status_code, 200, detail.text)
        listing = self.client.get('/findings/fixture')
        self.assertEqual(listing.status_code, 200, listing.text)
        matches = [f for f in listing.json() if f['slug'] == 'broken']
        self.assertEqual(len(matches), 1, listing.text)
        self.assertEqual(detail.json(), matches[0])
        return detail.json()

    def assert_blocked(self, value):
        self.assertTrue(value.get('source_error'), value)
        self.assertEqual(value['frontmatter']['status'], 'BLOCKED')
        self.assertEqual(value['frontmatter']['severity'], 'UNKNOWN')
        self.assertIsNone(value['frontmatter']['cvss_score'])
        self.assertIsNone(value['finding_id'])
        self.assertEqual(value['artifact_refs'], [])

    def test_invalid_syntax_shape_duplicates_and_field_types_stay_visible(self):
        cases = ['title: [', '- list', 'false', '[]', 'title: Good\nstatus: PROVEN\nstatus: CANDIDATE',
                 'title: [one, two]', 'cvss_score: .nan', 'cvss_score: 11', 'status: [PROVEN]', 'severity: [HIGH]', 'custom: {key: one, key: two}', 'base: &base {title: Base}\n<<: *base', '1: value', 'title: Good\nasset: {secret: value}']
        for metadata in cases:
            with self.subTest(metadata=metadata):
                content = '---\n' + metadata + '\n---\nOriginal <script>hostile()</script>'
                self.path.write_text(content)
                current = self.details()
                self.assert_blocked(current)
                self.assertEqual(current['body'], content)
                self.assertEqual(current['source_sha256'], hashlib.sha256(content.encode()).hexdigest())
                self.assertEqual(self.path.read_text(), content)
                rejected = self.client.post('/findings/fixture', json=dict(slug='broken', title='Overwrite', body='New', expected_source_sha256=current['source_sha256']))
                self.assertEqual(rejected.status_code, 409, rejected.text)
                self.assertEqual(self.path.read_text(), content)

    def test_unclosed_frontmatter_is_not_a_candidate(self):
        content = '---\ntitle: Legacy\nstatus: PROVEN\nMissing delimiter'
        self.path.write_text(content)
        current = self.details()
        self.assert_blocked(current)
        self.assertEqual(current['body'], content)
        self.assertEqual(self.path.read_text(), content)

    def test_binary_or_oversize_source_has_no_editable_version_and_remains_listed(self):
        for content in [b'\xff\x00private bytes', b'UTF8 with\0binary bytes']:
            self.path.write_bytes(content)
            self.assert_blocked(current := self.details())
            self.assertIsNone(current['source_sha256'])
            self.assertEqual(current['body'], '')
        with self.path.open('wb') as f:
            f.truncate(32 * 1024 * 1024 + 1)
        self.assert_blocked(current := self.details())
        self.assertIsNone(current['source_sha256'])
        self.assertEqual(current['body'], '')
        self.assertEqual(self.path.stat().st_size, 32 * 1024 * 1024 + 1)

    def test_symlink_and_changed_read_show_safe_error_without_source_or_host_paths(self):
        external = self.path.parent.parent / 'external.txt'
        external.write_text('outside-private-content')
        self.path.symlink_to(external)
        with self.assertRaises(UnsafeWorkspacePath):
            self.service.get_finding('fixture', 'broken')
        current = workspace_sync._finding_detail(self.path, 'fixture').model_dump()
        self.assert_blocked(current)
        self.assertIsNone(current['source_sha256'])
        self.assertNotIn('outside-private-content', str(current))
        self.assertNotIn(str(external), str(current))
        self.path.unlink()
        self.path.write_text('Body')
        with patch('app.services.workspace_sync._read_finding_source', side_effect=ArtifactChangedError('private diagnostic')):
            self.assert_blocked(current := self.details())
            self.assertNotIn('private diagnostic', str(current))
            self.assertIsNone(current['source_sha256'])

    def test_valid_legacy_empty_metadata_and_crlf_keep_existing_semantics_without_migration(self):
        for content in ['Body only', '---\n\n---\nBody', '---\r\ntitle: Legacy\r\nstatus: VERIFIED\r\n---\r\nBody']:
            self.path.write_bytes(content.encode())
            current = self.details()
            self.assertIsNone(current.get('source_error'))
            self.assertIsNone(current['finding_id'])
            self.assertEqual(self.path.read_bytes(), content.encode())
            self.assertEqual(current['source_sha256'], hashlib.sha256(content.encode()).hexdigest())
        self.assertEqual(current['frontmatter']['status'], 'VERIFIED')
        self.assertTrue(current['confirmation_error'])

    def test_duplicate_keys_cannot_be_silently_overwritten_and_manual_repair_recovers(self):
        self.path.write_text('---\ntitle: Original\nstatus: PROVEN\nstatus: CANDIDATE\n---\nBody')
        before = self.path.read_bytes()
        response = self.client.post('/findings/fixture', json=dict(slug='broken', title='Overwrite', body='New', expected_source_sha256=hashlib.sha256(before).hexdigest()))
        self.assertEqual(response.status_code, 409, response.text)
        self.assertEqual(self.path.read_bytes(), before)
        self.path.write_text('---\ntitle: Repaired\nstatus: CANDIDATE\n---\nBody')
        current = self.details()
        self.assertIsNone(current.get('source_error'))
        saved = self.client.post('/findings/fixture', json=dict(slug='broken', title='Reviewed', body='Body', expected_source_sha256=current['source_sha256']))
        self.assertEqual(saved.status_code, 200, saved.text)
        self.assertIsNotNone(saved.json()['finding_id'])
