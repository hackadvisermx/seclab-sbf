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
from app.services.workspace_sync import WorkspaceSyncService


def race_writer(root, digest, ready, start, result, delete):
    service = WorkspaceSyncService(pathlib.Path(root))
    ready.put(True)
    start.wait(10)
    try:
        if delete:
            service.delete_finding('fixture', 'first', expected_source_sha256=digest)
        else:
            service.save_finding('fixture', FindingCreate(slug='first', title='Race winner', body='Race update', expected_source_sha256=digest))
        result.put(('deleted' if delete else 'edited', True))
    except Exception as error:
        result.put(('conflict', type(error).__name__))


class TestFindingDeleteVersion(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.service = WorkspaceSyncService(pathlib.Path(tmp.name))
        self.service.create_engagement('fixture', domain='example.test')
        self.detail = self.service.save_finding('fixture', FindingCreate(slug='first', title='Original'))
        self.path = self.service._resolve_dir('fixture') / 'evidence/first.md'
        app = FastAPI()
        app.include_router(findings.router)
        self.client = TestClient(app)
        self.addCleanup(self.client.close)
        patcher = patch.object(findings, 'workspace_service', self.service)
        patcher.start()
        self.addCleanup(patcher.stop)

    def delete(self, digest=None, project='fixture', type='engagement'):
        query = {'type': type}
        if digest is not None:
            query['expected_source_sha256'] = digest
        return self.client.delete('/findings/' + project + '/first', params=query)

    def test_stale_delete_preserves_other_edit_and_fresh_review_can_delete(self):
        updated = self.service.save_finding('fixture', FindingCreate(slug='first', title='Other', body='Updated', expected_source_sha256=self.detail.source_sha256))
        before = self.path.read_bytes()
        response = self.delete(self.detail.source_sha256)
        self.assertEqual(response.status_code, 409, response.text)
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(self.delete(updated.source_sha256).status_code, 200)
        self.assertFalse(self.path.exists())
        self.assertEqual(self.delete(updated.source_sha256).status_code, 404)

    def test_missing_invalid_version_does_not_delete(self):
        before = self.path.read_bytes()
        for digest in [None, '', 'bad', 'A'*64, '0'*64]:
            response = self.delete(digest)
            self.assertEqual(response.status_code, 409, response.text)
            self.assertEqual(self.path.read_bytes(), before)

    def test_replacement_at_same_slug_and_other_project_are_not_deleted(self):
        self.path.unlink()
        replacement = self.service.save_finding('fixture', FindingCreate(slug='first', title='Replacement'))
        self.assertNotEqual(replacement.finding_id, self.detail.finding_id)
        before = self.path.read_bytes()
        self.assertEqual(self.delete(self.detail.source_sha256).status_code, 409)
        self.assertEqual(self.path.read_bytes(), before)
        self.service.create_engagement('other', domain='example.test')
        other = self.service.save_finding('other', FindingCreate(slug='first', title='Other project'))
        self.assertEqual(self.delete(replacement.source_sha256, project='other').status_code, 409)
        self.assertEqual(self.service.get_finding('other', 'first').source_sha256, other.source_sha256)

    def test_legacy_source_requires_exact_version_without_migration(self):
        self.path.write_text('---\ntitle: Legacy\n---\nLegacy body')
        before = self.path.read_bytes()
        self.assertEqual(self.delete().status_code, 409)
        current = self.client.get('/findings/fixture/first').json()
        self.assertIsNone(current['finding_id'])
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(self.delete(hashlib.sha256(before).hexdigest()).status_code, 200)

    def test_edit_delete_race_across_processes_does_not_remove_unread_update_or_recreate(self):
        ctx = multiprocessing.get_context('fork')
        ready, result, start = ctx.Queue(), ctx.Queue(), ctx.Event()
        processes = [ctx.Process(target=race_writer, args=(str(self.service.ws_path), self.detail.source_sha256, ready, start, result, delete)) for delete in [False, True]]
        try:
            for process in processes:
                process.start()
            for _ in processes:
                ready.get(timeout=10)
            start.set()
            outcomes = [result.get(timeout=10) for _ in processes]
            self.assertEqual(sum(status != 'conflict' for status, _ in outcomes), 1, outcomes)
            self.assertIn(('conflict', 'FindingUpdateError'), outcomes)
            if ('edited', True) in outcomes:
                self.assertEqual(self.service.get_finding('fixture', 'first').body, 'Race update')
            else:
                self.assertFalse(self.path.exists())
        finally:
            start.set()
            for process in processes:
                process.join(2)
                if process.is_alive():
                    process.terminate()
                    process.join(2)
            ready.close()
            result.close()
