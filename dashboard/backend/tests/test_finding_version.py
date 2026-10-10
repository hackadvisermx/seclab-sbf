import hashlib
import multiprocessing
import pathlib
import tempfile
import unittest
from unittest.mock import patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.api.endpoints import findings
from app.models.schemas import FindingCreate
from app.services.workspace_sync import WorkspaceSyncService, FindingUpdateError
from app.services import workspace_sync


def concurrent_edit(workspace, digest, ready, start, result, title):
    service = WorkspaceSyncService(pathlib.Path(workspace))
    ready.put(title)
    start.wait(10)
    try:
        service.save_finding('fixture', FindingCreate(slug='first', title=title, body=title,
            expected_source_sha256=digest))
        result.put(('saved', title))
    except FindingUpdateError:
        result.put(('conflict', title))


class TestFindingVersion(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.service = WorkspaceSyncService(pathlib.Path(temporary.name))
        self.service.create_engagement('fixture', domain='example.test')
        self.service.save_finding('fixture', FindingCreate(slug='first', title='Original'))
        self.path = self.service._resolve_dir('fixture') / 'evidence/first.md'
        app = FastAPI()
        app.include_router(findings.router)
        self.client = TestClient(app)
        self.addCleanup(self.client.close)
        patcher = patch.object(findings, 'workspace_service', self.service)
        patcher.start()
        self.addCleanup(patcher.stop)

    def payload(self, title='Edited', **extra):
        return dict(slug='first', title=title, body='Draft ' + title,
            expected_source_sha256=hashlib.sha256(self.path.read_bytes()).hexdigest(), **extra)

    def test_api_stale_edit_preserves_first_update_and_returns_conflict(self):
        stale = self.payload('Stale')
        saved = self.client.post('/findings/fixture', json=self.payload('First update'))
        self.assertEqual(saved.status_code, 200, saved.text)
        before = self.path.read_bytes()
        rejected = self.client.post('/findings/fixture', json=stale)
        self.assertEqual(rejected.status_code, 409, rejected.text)
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(self.service.get_finding('fixture', 'first').frontmatter.title, 'First update')

    def test_reads_and_save_return_hash_of_exact_source_bytes_without_rewriting(self):
        before = self.path.read_bytes()
        digest = hashlib.sha256(before).hexdigest()
        for response in [self.client.get('/findings/fixture/first').json(), self.client.get('/findings/fixture').json()[0]]:
            self.assertEqual(response.get('source_sha256'), digest)
        self.assertEqual(self.path.read_bytes(), before)
        saved = self.client.post('/findings/fixture', json=self.payload())
        self.assertEqual(saved.status_code, 200, saved.text)
        self.assertEqual(saved.json()['source_sha256'], hashlib.sha256(self.path.read_bytes()).hexdigest())
        self.assertNotEqual(saved.json()['source_sha256'], digest)

    def test_missing_version_and_deleted_source_never_overwrite_or_recreate(self):
        before = self.path.read_bytes()
        request = self.payload()
        for digest in [None, '', 'bad', '0' * 64]:
            payload = dict(request, expected_source_sha256=digest)
            if digest is None:
                payload.pop('expected_source_sha256')
            response = self.client.post('/findings/fixture', json=payload)
            self.assertEqual(response.status_code, 409, response.text)
            self.assertEqual(self.path.read_bytes(), before)
        self.path.unlink()
        rejected = self.client.post('/findings/fixture', json=request)
        self.assertEqual(rejected.status_code, 409, rejected.text)
        self.assertFalse(self.path.exists())

    def test_external_edit_requires_reload_and_legacy_receives_version_without_migration(self):
        stale = self.payload()
        self.path.write_text('---\ntitle: Legacy\ncustom: preserved\n---\nBody externo á\n')
        before = self.path.read_bytes()
        self.assertEqual(self.client.post('/findings/fixture', json=stale).status_code, 409)
        current = self.client.get('/findings/fixture/first').json()
        self.assertIsNone(current['finding_id'])
        self.assertEqual(self.path.read_bytes(), before)
        saved = self.client.post('/findings/fixture', json=dict(slug='first', title='Reviewed', body=current['body'],
            expected_source_sha256=current.get('source_sha256')))
        self.assertEqual(saved.status_code, 200, saved.text)
        self.assertEqual(saved.json()['body'], current['body'])
        self.assertIn('custom: preserved', self.path.read_text())
        self.assertIsNotNone(saved.json()['finding_id'])

    def test_two_processes_with_same_version_allow_exactly_one_update(self):
        context = multiprocessing.get_context('fork')
        ready, result, start = context.Queue(), context.Queue(), context.Event()
        digest = hashlib.sha256(self.path.read_bytes()).hexdigest()
        processes = [context.Process(target=concurrent_edit, args=(str(self.service.ws_path), digest, ready, start, result, title)) for title in ['A', 'B']]
        try:
            for process in processes:
                process.start()
            for _ in processes:
                ready.get(timeout=10)
            start.set()
            outcomes = [result.get(timeout=10) for _ in processes]
            self.assertEqual(sorted(status for status, _ in outcomes), ['conflict', 'saved'])
            winner = next(title for status, title in outcomes if status == 'saved')
            current = self.service.get_finding('fixture', 'first')
            self.assertEqual(current.frontmatter.title, winner)
            self.assertEqual(current.body, winner)
        finally:
            start.set()
            for process in processes:
                process.join(2)
                if process.is_alive():
                    process.terminate()
                    process.join(2)
            ready.close()
            result.close()
        self.assertEqual(list(self.path.parent.glob('.*.tmp')), [])

    def test_source_changed_or_deleted_during_validation_blocks_final_replace(self):
        original = workspace_sync._finding_markdown
        for action in ['change', 'delete']:
            with self.subTest(action=action):
                if not self.path.exists():
                    self.service.save_finding('fixture', FindingCreate(slug='first', title='Original'))
                payload = self.payload()
                def change_source(metadata, body):
                    if action == 'change':
                        self.path.write_text('---\ntitle: External\n---\nExternal body')
                    else:
                        self.path.unlink()
                    return original(metadata, body)
                with patch.object(workspace_sync, '_finding_markdown', side_effect=change_source):
                    response = self.client.post('/findings/fixture', json=payload)
                self.assertEqual(response.status_code, 409, response.text)
                if action == 'change':
                    self.assertEqual(self.service.get_finding('fixture', 'first').body, 'External body')
                else:
                    self.assertFalse(self.path.exists())
                self.assertEqual(list(self.path.parent.glob('.*.tmp')), [])
