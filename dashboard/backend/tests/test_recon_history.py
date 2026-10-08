import json
import pathlib
import sqlite3
from contextlib import closing
import tempfile
import threading
import unittest
from unittest.mock import patch, Mock
from app.core.recon_jobs import ReconJobStore
from app.services import recon_service as module


class TestReconHistory(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = pathlib.Path(temporary.name)
        self.db = self.root / 'state/jobs.db'
        self.store = ReconJobStore(self.db)
        self.key = ('engagement', 'fixture')

    def completed(self, stage='probe', key=None, status='completed'):
        key = key or self.key
        job = self.store.begin(key, stage, status == 'simulated')
        self.store.finish(key, job['run_id'], status)
        return job

    def test_history_retains_every_job_and_current_contract_after_reopening(self):
        ids = [self.completed(status=status)['run_id'] for status in ['completed', 'simulated', 'failed']]
        reopened = ReconJobStore(self.db)
        jobs = reopened.history(self.key)['jobs']
        self.assertEqual([j['run_id'] for j in jobs], ids[::-1])
        self.assertEqual([j['status'] for j in jobs], ['failed', 'simulated', 'completed'])
        self.assertTrue(all(j['finished_at'] for j in jobs))
        self.assertTrue(all(j['origin'] == 'dashboard' for j in jobs))
        self.assertEqual(reopened.get(self.key)['run_id'], ids[-1])
        self.assertEqual(self.db.stat().st_mode & 0o777, 0o600)

    def test_active_job_and_stale_completion_cannot_duplicate_or_rewrite_history(self):
        old = self.completed()
        current = self.store.begin(self.key, 'urls', False)
        with self.assertRaises(RuntimeError):
            self.store.begin(self.key, 'all', False)
        self.store.finish(self.key, old['run_id'], 'failed', 'stale completion')
        jobs = {j['run_id']: j for j in self.store.history(self.key)['jobs']}
        self.assertEqual(len(jobs), 2)
        self.assertEqual(jobs[old['run_id']]['status'], 'completed')
        self.assertEqual(jobs[current['run_id']]['status'], 'running')
        for status, revision in [('running', None), ('completed', 'bad-revision')]:
            with self.assertRaises(ValueError):
                self.store.finish(self.key, current['run_id'], status, scope_revision=revision)
        self.assertEqual(self.store.get(self.key)['status'], 'running')

    def test_cancellation_and_recovery_update_history_without_changing_completed_jobs(self):
        completed = self.completed()
        pending = self.store.begin(self.key, 'probe', False)
        self.store.request_cancel(self.key)
        self.assertEqual(self.store.history(self.key)['jobs'][0]['status'], 'cancelling')
        reopened = ReconJobStore(self.db)
        reopened.recover()
        jobs = {j['run_id']: j for j in reopened.history(self.key)['jobs']}
        self.assertEqual(jobs[completed['run_id']]['status'], 'completed')
        self.assertEqual(jobs[pending['run_id']]['status'], 'interrupted')
        self.assertEqual(jobs[pending['run_id']]['started_at'], pending['started_at'])
        self.assertEqual(jobs[pending['run_id']]['finished_at'], reopened.get(self.key)['finished_at'])

    def test_legacy_migration_imports_only_last_known_job_once(self):
        job = self.completed()
        with self.store.connect() as conn:
            conn.execute('DROP TABLE recon_job_history')
        for _ in range(2):
            reopened = ReconJobStore(self.db)
            jobs = reopened.history(self.key)['jobs']
            self.assertEqual(len(jobs), 1)
            self.assertEqual(jobs[0]['run_id'], job['run_id'])
            self.assertEqual(jobs[0]['origin'], 'legacy-current')
            self.assertIsNone(jobs[0]['scope_revision'])

    def test_reopening_reconciles_current_job_finished_by_an_older_version(self):
        job = self.store.begin(self.key, 'probe', False)
        with self.store.connect() as conn:
            conn.execute("UPDATE recon_jobs SET status='completed', finished_at='2026-10-08T00:00:00Z' WHERE run_id=?", (job['run_id'],))
        reopened = ReconJobStore(self.db)
        history = reopened.history(self.key)['jobs'][0]
        self.assertEqual(history['status'], 'completed')
        self.assertEqual(history['finished_at'], reopened.get(self.key)['finished_at'])
        self.assertEqual(history['origin'], 'dashboard')

    def test_pagination_is_stable_across_new_jobs_and_isolates_project_and_type(self):
        ids = [self.completed()['run_id'] for _ in range(4)]
        other = self.completed(key=('reto', 'fixture'))
        first = self.store.history(self.key, 2)
        self.assertEqual([j['run_id'] for j in first['jobs']], ids[-2:][::-1])
        self.completed()
        second = self.store.history(self.key, 2, first['next_cursor'])
        self.assertEqual([j['run_id'] for j in second['jobs']], ids[:2][::-1])
        self.assertIsNone(second['next_cursor'])
        for cursor in [other['run_id'], 'missing']:
            with self.assertRaises(ValueError):
                self.store.history(self.key, before=cursor)
        for limit in [0, 101, True]:
            with self.assertRaises(ValueError):
                self.store.history(self.key, limit)

    def test_parallel_starts_keep_one_active_job_and_one_history_record(self):
        stores = [self.store, ReconJobStore(self.db)]
        barrier = threading.Barrier(2)
        errors = []
        def begin(store):
            barrier.wait()
            try:
                store.begin(self.key, 'all', False)
            except RuntimeError as error:
                errors.append(error)
        threads = [threading.Thread(target=begin, args=(store,)) for store in stores]
        for thread in threads: thread.start()
        for thread in threads: thread.join(timeout=5)
        self.assertTrue(all(not thread.is_alive() for thread in threads))
        self.assertEqual(len(errors), 1)
        self.assertEqual(len(self.store.history(self.key)['jobs']), 1)

    def test_sqlite_backup_preserves_history_and_works_after_reopening(self):
        ids = [self.completed()['run_id'] for _ in range(3)]
        snapshot = self.root / 'snapshot/jobs.db'
        snapshot.parent.mkdir()
        with closing(self.store.connect()) as source, closing(sqlite3.connect(snapshot)) as destination:
            source.backup(destination)
        restored = ReconJobStore(snapshot)
        self.assertEqual([job['run_id'] for job in restored.history(self.key)['jobs']], ids[::-1])
        self.assertEqual(restored.get(self.key)['run_id'], ids[-1])

    def test_cancel_is_scoped_even_if_legacy_projects_share_a_run_identifier(self):
        with patch('app.core.recon_jobs.uuid.uuid4', return_value=Mock(hex='a' * 32)):
            self.store.begin(self.key, 'probe', False)
            self.store.begin(('reto', 'fixture'), 'probe', False)
        self.store.request_cancel(self.key)
        self.assertEqual(self.store.history(self.key)['jobs'][0]['status'], 'cancelling')
        self.assertEqual(self.store.history(('reto', 'fixture'))['jobs'][0]['status'], 'running')

    def test_delete_purges_only_this_project_history(self):
        self.completed()
        self.completed(key=('reto', 'fixture'))
        self.store.delete(self.key)
        self.assertIsNone(self.store.get(self.key))
        self.assertEqual(self.store.history(self.key)['jobs'], [])
        self.assertEqual(len(self.store.history(('reto', 'fixture'))['jobs']), 1)

    def test_summary_revision_requires_matching_run_and_safe_bounded_file(self):
        recon = self.root / 'project/recon'
        recon.mkdir(parents=True)
        summary = recon / 'summary.json'
        for data, expected in [({'run_id':'fixture', 'scope_revision':'a'*64}, 'a'*64),
                               ({'run_id':'previous', 'scope_revision':'a'*64}, None),
                               ({'run_id':'fixture', 'scope_revision':'bad'}, None), ([], None)]:
            summary.write_text(json.dumps(data))
            self.assertEqual(module.ReconService._completed_scope_revision(recon.parent, 'fixture'), expected)
        summary.write_bytes(b' ' * (2 * 1024 * 1024 + 1))
        self.assertIsNone(module.ReconService._completed_scope_revision(recon.parent, 'fixture'))
        summary.unlink()
        source = self.root / 'source.json'
        source.write_text(json.dumps({'run_id':'fixture', 'scope_revision':'a'*64}))
        summary.symlink_to(source)
        self.assertIsNone(module.ReconService._completed_scope_revision(recon.parent, 'fixture'))

    def test_history_api_authentication_pagination_and_missing_project(self):
        from fastapi.testclient import TestClient
        from app.main import app
        from app.api.endpoints import recon, auth
        target = self.root / 'workspace/engagements/fixture'
        target.mkdir(parents=True)
        service = module.ReconService(self.db)
        with patch.object(module, 'WORKSPACE_DIR', self.root / 'workspace'), patch.object(recon, 'recon_service', service):
            client = TestClient(app)
            self.addCleanup(client.close)
            self.assertEqual(client.get('/api/v1/recon/fixture/history').status_code, 401)
            app.dependency_overrides[auth.require_operator] = lambda: 'fixture-only'
            try:
                self.completed()
                response = client.get('/api/v1/recon/fixture/history')
                self.assertEqual(response.status_code, 200, response.text)
                self.assertEqual(len(response.json()['jobs']), 1)
                self.assertEqual(client.get('/api/v1/recon/missing/history').status_code, 404)
                self.assertEqual(client.get('/api/v1/recon/fixture/history?limit=101').status_code, 422)
                self.assertEqual(client.get('/api/v1/recon/fixture/history?before=bad').status_code, 422)
                self.assertEqual(client.get('/api/v1/recon/fixture/history?before=' + '0'*32).status_code, 400)
            finally:
                app.dependency_overrides.pop(auth.require_operator, None)
