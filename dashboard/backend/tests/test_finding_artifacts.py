import hashlib
import json
import pathlib
import tempfile
import unittest
from app.models.schemas import FindingCreate
from app.services.workspace_sync import WorkspaceSyncService, FindingUpdateError


class TestFindingArtifacts(unittest.TestCase):
    def current_version(self, slug):
        path = self.service._resolve_dir('fixture') / 'evidence' / (slug + '.md')
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.service = WorkspaceSyncService(pathlib.Path(temporary.name))
        self.service.create_engagement('fixture', domain='example.test')
        self.path = self.service._resolve_dir('fixture') / 'recon/raw.txt'
        self.path.write_bytes(b'fixture')
        self.reference = {'path': 'recon/raw.txt', 'sha256': hashlib.sha256(b'fixture').hexdigest()}

    def test_create_reload_edit_omission_and_explicit_removal_preserve_body(self):
        created = self.service.save_finding('fixture', FindingCreate(slug='linked', title='Fixture', artifact_refs=[self.reference]))
        self.assertEqual(created.artifact_refs, [self.reference])
        path = self.path.parent.parent / 'evidence/linked.md'
        self.assertIn('artifact_refs: ' + json.dumps([self.reference]), path.read_text())
        loaded = self.service.list_findings('fixture')[0]
        updated = self.service.save_finding('fixture', FindingCreate(slug='linked', title='Edit', body=loaded.body, expected_source_sha256=self.current_version('linked')))
        self.assertEqual(updated.artifact_refs, [self.reference])
        self.assertEqual(updated.body, loaded.body)
        cleared = self.service.save_finding('fixture', FindingCreate(slug='linked', title='Edit', body=loaded.body, artifact_refs=[], expected_source_sha256=self.current_version('linked')))
        self.assertEqual(cleared.artifact_refs, [])
        self.assertEqual(self.path.read_bytes(), b'fixture')

    def test_invalid_changed_and_missing_refs_cannot_overwrite_existing_finding(self):
        finding = self.service.save_finding('fixture', FindingCreate(slug='linked', title='Fixture', artifact_refs=[self.reference]))
        path = self.path.parent.parent / 'evidence/linked.md'
        before = path.read_bytes()
        cases = [[dict(self.reference, sha256='0' * 64)], [dict(self.reference, path='../outside')],
                 [dict(self.reference, path='loot/credentials.json')], [self.reference, self.reference],
                 [self.reference] * 11, None]
        for references in cases:
            with self.subTest(references=references), self.assertRaises(FindingUpdateError):
                self.service.save_finding('fixture', FindingCreate(slug='linked', title='changed', body=finding.body, artifact_refs=references, expected_source_sha256=self.current_version('linked')))
            self.assertEqual(path.read_bytes(), before)
        self.path.unlink()
        with self.assertRaises(FindingUpdateError):
            self.service.save_finding('fixture', FindingCreate(slug='linked', title='changed', body=finding.body, artifact_refs=[self.reference], expected_source_sha256=self.current_version('linked')))
        self.assertEqual(path.read_bytes(), before)

    def test_invalid_metadata_is_visible_and_requires_explicit_repair(self):
        path = self.path.parent.parent / 'evidence/invalid.md'
        path.write_text('---\ntitle: Invalid refs\nartifact_refs: null\n---\nOriginal body')
        result = self.service.list_findings('fixture')[0]
        self.assertIsNotNone(result.artifact_refs_error)
        self.assertEqual(result.body, 'Original body')
        with self.assertRaises(ValueError):
            self.service.save_finding('fixture', FindingCreate(slug='invalid', title='Invalid refs', body=result.body, expected_source_sha256=self.current_version('invalid')))
        repaired = self.service.save_finding('fixture', FindingCreate(slug='invalid', title='Invalid refs', body=result.body, artifact_refs=[], expected_source_sha256=self.current_version('invalid')))
        self.assertIsNone(repaired.artifact_refs_error)
