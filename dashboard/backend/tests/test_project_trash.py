import errno
import pathlib
import tempfile
import threading
import unittest
from unittest.mock import patch


class TestProjectTrash(unittest.TestCase):
    def setUp(self):
        from app.services.workspace_sync import WorkspaceSyncService
        from app.services import workspace_sync, recon_service
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = pathlib.Path(self.temp.name)
        self.workspace = WorkspaceSyncService(self.root / 'workspace')
        self.workspace_module = workspace_sync
        self.recon = recon_service.ReconService(self.root / 'jobs.db')
        self.service_patch = patch.object(workspace_sync, 'workspace_service', self.workspace)
        self.service_patch.start()
        self.addCleanup(self.service_patch.stop)

    def seed(self, name='sample', kind='engagement'):
        self.workspace.create_engagement(name, kind)
        target = self.workspace._resolve_dir(name, kind)
        (target / 'REPORT.md').write_text('# Informe')
        (target / 'loot/nested').mkdir()
        (target / 'loot/nested/credential.json').write_text('{"fixture":"local"}')
        (target / 'evidence/a.md').write_text('evidence')
        (target / 'flags.json').write_text('{"fixture":"captured"}')
        return target

    def test_round_trip_preserves_all_files_and_same_name_other_type(self):
        for kind in ('reto', 'engagement'):
            self.seed(kind=kind)
        expected = {p.relative_to(self.workspace._resolve_dir('sample', 'reto')): p.read_bytes()
                    for p in self.workspace._resolve_dir('sample', 'reto').rglob('*') if p.is_file()}
        entry = self.recon.delete_engagement('sample', 'reto')
        self.assertFalse(self.workspace._resolve_dir('sample', 'reto').exists())
        self.assertTrue(self.workspace._resolve_dir('sample').exists())
        self.assertEqual(self.workspace.trash.list_entries(), [entry])
        self.recon.restore_engagement(entry['entry_id'], entry['project_id'], entry['type'])
        restored = self.workspace._resolve_dir('sample', 'reto')
        self.assertEqual({p.relative_to(restored): p.read_bytes() for p in restored.rglob('*') if p.is_file()}, expected)
        self.assertEqual(self.workspace.trash.list_entries(), [])
        self.assertEqual((self.workspace.ws_path / '.seclab-trash').stat().st_mode & 0o777, 0o700)
        self.assertIsNone(self.recon.store.get(('reto', 'sample')))

    def test_multiple_versions_conflict_and_second_restore_is_missing(self):
        self.seed()
        first = self.recon.delete_engagement('sample')
        self.seed()
        self.workspace.save_notes('sample', 'new version')
        second = self.recon.delete_engagement('sample')
        self.assertNotEqual(first['entry_id'], second['entry_id'])
        self.assertEqual(len(self.workspace.trash.list_entries()), 2)
        self.recon.restore_engagement(second['entry_id'], 'sample')
        with self.assertRaises(RuntimeError):
            self.recon.restore_engagement(first['entry_id'], 'sample')
        self.assertEqual(self.workspace.get_notes('sample'), 'new version')
        self.assertEqual(self.workspace.trash.list_entries(), [first])
        with self.assertRaises(FileNotFoundError):
            self.recon.restore_engagement(second['entry_id'], 'sample')

    def test_jobs_running_and_cancelling_block_move_and_restore(self):
        for kind in ('engagement', 'reto'):
            target = self.seed(name=kind, kind=kind)
            entry = self.recon.delete_engagement(kind, kind)
            job = self.recon.store.begin((kind, kind), 'all', False)
            for status in ('running', 'cancelling'):
                if status == 'cancelling':
                    self.recon.store.request_cancel((kind, kind))
                with self.subTest(kind=kind, status=status), self.assertRaises(RuntimeError):
                    self.recon.restore_engagement(entry['entry_id'], kind, kind)
                self.assertFalse(target.exists())
                self.workspace.create_engagement(kind, kind)
                with self.assertRaises(RuntimeError):
                    self.recon.delete_engagement(kind, kind)
                self.assertTrue(target.exists())
                import shutil
                shutil.rmtree(target)
            self.recon.store.finish((kind, kind), job['run_id'], 'cancelled')
            self.recon.restore_engagement(entry['entry_id'], kind, kind)
            self.assertTrue(target.exists())

    def test_recreated_service_lists_deleted_entries_after_restart(self):
        from app.services.workspace_sync import WorkspaceSyncService
        self.seed()
        entry = self.recon.delete_engagement('sample')
        reloaded = WorkspaceSyncService(self.workspace.ws_path)
        self.assertEqual(reloaded.trash.list_entries(), [entry])
        reloaded.restore_engagement(entry['entry_id'], 'sample')
        self.assertEqual(reloaded.trash.list_entries(), [])

    def test_invalid_identity_token_date_and_type_leave_files_untouched(self):
        self.seed()
        entry = self.recon.delete_engagement('sample')
        for token in ('..', '../sample', '', 'x', '20261399T999999999999Z-' + 'a' * 32):
            with self.subTest(token=token), self.assertRaises(ValueError):
                self.recon.restore_engagement(token, 'sample')
        for project in ('..', '../sample', '/tmp', '.hidden', 'a' * 129):
            with self.subTest(project=project), self.assertRaises(ValueError):
                self.recon.restore_engagement(entry['entry_id'], project)
        with self.assertRaises(ValueError):
            self.recon.restore_engagement(entry['entry_id'], 'sample', 'unknown')
        self.assertEqual(self.workspace.trash.list_entries(), [entry])

    def test_wrong_type_or_id_never_restore_another_project(self):
        self.seed(kind='reto')
        entry = self.recon.delete_engagement('sample', 'reto')
        for project, kind in (('sample', 'engagement'), ('other', 'reto')):
            with self.subTest(project=project, kind=kind), self.assertRaises(FileNotFoundError):
                self.recon.restore_engagement(entry['entry_id'], project, kind)
        self.assertEqual(self.workspace.trash.list_entries(), [entry])

    def test_trash_root_and_category_symlinks_are_rejected(self):
        self.seed()
        outside = self.root / 'outside'
        outside.mkdir()
        trash = self.workspace.ws_path / '.seclab-trash'
        trash.symlink_to(outside, target_is_directory=True)
        with self.assertRaises(ValueError):
            self.recon.delete_engagement('sample')
        trash.unlink()
        trash.mkdir()
        (trash / 'engagements').symlink_to(outside, target_is_directory=True)
        with self.assertRaises(ValueError):
            self.recon.delete_engagement('sample')
        self.assertTrue(self.workspace._resolve_dir('sample').exists())
        self.assertEqual(list(outside.iterdir()), [])

    def test_project_and_deleted_entry_nested_links_are_rejected(self):
        target = self.seed()
        outside = self.root / 'outside.txt'
        outside.write_text('keep')
        (target / 'loot/link').symlink_to(outside)
        with self.assertRaises(ValueError):
            self.recon.delete_engagement('sample')
        (target / 'loot/link').unlink()
        entry = self.recon.delete_engagement('sample')
        source = self.workspace.ws_path / '.seclab-trash/engagements/sample' / entry['entry_id']
        (source / 'loot/link').symlink_to(outside)
        with self.assertRaises(ValueError):
            self.recon.restore_engagement(entry['entry_id'], 'sample')
        self.assertEqual(self.workspace.trash.list_entries(), [])
        self.assertEqual(outside.read_text(), 'keep')
        self.assertTrue(source.is_dir())

    def test_atomic_move_failure_preserves_source(self):
        target = self.seed()
        with patch('app.core.project_trash.move_without_replacing', side_effect=OSError(errno.EXDEV, 'fixture')):
            with self.assertRaises(OSError):
                self.recon.delete_engagement('sample')
        self.assertTrue((target / 'REPORT.md').exists())
        self.assertEqual(self.workspace.trash.list_entries(), [])
        entry = self.recon.delete_engagement('sample')
        with patch('app.core.project_trash.move_without_replacing', side_effect=PermissionError('fixture')):
            with self.assertRaises(OSError):
                self.recon.restore_engagement(entry['entry_id'], 'sample')
        self.assertFalse(target.exists())
        self.assertEqual(self.workspace.trash.list_entries(), [entry])

    def test_new_empty_target_during_restore_is_not_overwritten(self):
        from app.core.project_trash import move_without_replacing
        self.seed()
        entry = self.recon.delete_engagement('sample')
        target = self.workspace._resolve_dir('sample')
        def race(source, destination):
            target.mkdir()
            return move_without_replacing(source, destination)
        with patch('app.core.project_trash.move_without_replacing', side_effect=race):
            with self.assertRaises(RuntimeError):
                self.recon.restore_engagement(entry['entry_id'], 'sample')
        self.assertEqual(list(target.iterdir()), [])
        self.assertEqual(self.workspace.trash.list_entries(), [entry])

    def test_restore_and_create_are_serialized(self):
        self.seed()
        entry = self.recon.delete_engagement('sample')
        results = []
        barrier = threading.Barrier(2)
        def mutate(restore):
            barrier.wait(timeout=5)
            try:
                if restore:
                    self.recon.restore_engagement(entry['entry_id'], 'sample')
                else:
                    self.workspace.create_engagement('sample')
                results.append('restored' if restore else 'created')
            except (ValueError, RuntimeError):
                results.append('conflict')
        threads = [threading.Thread(target=mutate, args=(value,)) for value in (True, False)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=5)
            self.assertFalse(thread.is_alive())
        self.assertEqual(results.count('conflict'), 1)
        if 'created' in results:
            self.assertEqual(self.workspace.trash.list_entries(), [entry])
        else:
            self.assertTrue((self.workspace._resolve_dir('sample') / 'REPORT.md').exists())
            self.assertEqual(self.workspace.trash.list_entries(), [])

    def test_invalid_entry_does_not_hide_other_versions(self):
        self.seed()
        entry = self.recon.delete_engagement('sample')
        parent = self.workspace.ws_path / '.seclab-trash/engagements/sample'
        (parent / 'invalid-token').mkdir()
        self.assertEqual(self.workspace.trash.list_entries(), [entry])

    def test_authenticated_trash_api_statuses_and_names_do_not_conflict(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from app.api.endpoints import trash, engagements, auth
        app = FastAPI()
        from fastapi import Depends
        app.include_router(trash.router, dependencies=[Depends(auth.require_operator)])
        app.include_router(engagements.router)
        self.seed('trash')
        entry = self.recon.delete_engagement('trash')
        with patch.object(trash, 'workspace_service', self.workspace), patch.object(trash, 'recon_service', self.recon), patch.object(engagements, 'workspace_service', self.workspace), TestClient(app) as client:
            self.assertEqual(client.get('/trash').status_code, 401)
            url = f"/trash/{entry['entry_id']}/restore?project_id=trash"
            self.assertEqual(client.post(url).status_code, 401)
            app.dependency_overrides[auth.require_operator] = lambda: 'tester'
            self.assertEqual(client.get('/trash').json(), [entry])
            self.assertEqual(client.post('/trash/invalid/restore?project_id=trash').status_code, 400)
            self.assertEqual(client.post(url + '&type=invalid').status_code, 400)
            self.assertEqual(client.post(url.replace('project_id=trash', 'project_id=missing')).status_code, 404)
            job = self.recon.store.begin(('engagement', 'trash'), 'all', False)
            self.assertEqual(client.post(url).status_code, 409)
            self.recon.store.finish(('engagement', 'trash'), job['run_id'], 'completed')
            self.assertEqual(client.post(url).json(), entry)
            self.assertEqual(client.get('/engagements/trash').status_code, 200)
            self.assertEqual(client.post(url).status_code, 404)
            self.assertEqual(client.get('/trash').json(), [])


if __name__ == '__main__':
    unittest.main()
