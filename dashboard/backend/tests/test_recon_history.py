import json
import pathlib
import sqlite3
from contextlib import closing
import tempfile
import threading
import unittest
from unittest.mock import patch, Mock
from app.core.recon_jobs import ReconJobStore
from app.core.recon_review import reviewed_plan, target_host
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

    def review(self):
        return reviewed_plan({'generated_at': '2026-10-08T00:00:00Z', 'stage': 'patterns',
            'dry_run': True, 'can_start': True, 'scope_revision': 'a'*64, 'plan_revision': 'b'*64,
            'operational_limits': {'max_requests_per_second': 1, 'max_parallel_threads': 1,
                                   'max_probe_targets': 1000, 'probe_timeout_seconds': 8},
            'authorization': {'reference_present': True, 'reference': 'secret-reference', 'allow_passive': False,
                              'allow_active': False, 'valid_from': '', 'valid_until': ''},
            'stages': [{'stage': 'patterns', 'interaction': 'local', 'targets_pending': False,
                        'targets_count': 70, 'discarded_count': 1,
                        'targets': ['https://user:secret-password@example.test/secret-path?key=secret-query#secret-fragment'] * 70,
                        'discarded': [{'target': 'https://unknown.test/?secret-discard', 'verdict': 'UNKNOWN', 'reason': 'secret-reason'}],
                        'target_reasons': {'secret-target': 'secret-reason'}, 'block_reasons': []}]})

    def test_review_is_bounded_sanitized_and_survives_finish_cancel_restart_and_backup(self):
        review = self.review()
        self.assertEqual(len(review['stages'][0]['targets']), 50)
        self.assertEqual(review['stages'][0]['targets_count'], 70)
        self.assertNotIn('secret', json.dumps(review))
        for raw, expected in [('https://user:password@[2001:db8::1]:443/path?k=secret', '2001:db8::1'),
                              ('example.test', 'example.test'), ('https://[broken', '[target omitido]')]:
            self.assertEqual(target_host(raw), expected)
        first = self.store.begin(self.key, 'patterns', True, reviewed_plan=review)
        self.store.finish(self.key, first['run_id'], 'simulated', scope_revision='c'*64)
        review['plan_revision'] = 'd'*64
        second = self.store.begin(self.key, 'patterns', True, reviewed_plan=review)
        self.store.request_cancel(self.key)
        reopened = ReconJobStore(self.db)
        reopened.recover()
        jobs = reopened.history(self.key)['jobs']
        self.assertEqual([job['reviewed_plan']['plan_revision'] for job in jobs], ['d'*64, 'b'*64])
        self.assertEqual(jobs[0]['run_id'], second['run_id'])
        self.assertEqual(jobs[0]['status'], 'interrupted')
        self.assertEqual(jobs[1]['scope_revision'], 'c'*64)
        self.assertEqual(jobs[1]['reviewed_plan']['scope_revision'], 'a'*64)
        snapshot = self.root / 'snapshot.db'
        with closing(reopened.connect()) as source, closing(sqlite3.connect(snapshot)) as destination:
            source.backup(destination)
        self.assertEqual(ReconJobStore(snapshot).history(self.key)['jobs'], jobs)
        self.assertNotIn(b'secret', self.db.read_bytes())

    def test_review_creation_is_atomic_bounded_and_deletion_is_scoped(self):
        with self.assertRaises(ValueError):
            self.store.begin(self.key, 'patterns', True, reviewed_plan={'oversized': 'a' * 200000})
        self.assertIsNone(self.store.get(self.key))
        with self.store.connect() as conn:
            conn.execute("CREATE TRIGGER reject_review BEFORE INSERT ON recon_job_reviews BEGIN SELECT RAISE(ABORT, 'fixture'); END")
        with self.assertRaises(sqlite3.IntegrityError):
            self.store.begin(self.key, 'patterns', True, reviewed_plan=self.review())
        self.assertIsNone(self.store.get(self.key))
        self.assertEqual(self.store.history(self.key)['jobs'], [])
        with self.store.connect() as conn:
            conn.execute('DROP TRIGGER reject_review')
        for key in [self.key, ('reto', 'fixture')]:
            self.store.begin(key, 'patterns', True, reviewed_plan=self.review())
        self.store.delete(self.key)
        self.assertEqual(self.store.history(self.key)['jobs'], [])
        self.assertIsNotNone(self.store.history(('reto', 'fixture'))['jobs'][0]['reviewed_plan'])
        with self.store.connect() as conn:
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM recon_job_reviews').fetchone()[0], 1)

    def test_old_schema_inserts_remain_compatible_and_orphan_reviews_are_removed(self):
        job = self.store.begin(self.key, 'patterns', True, reviewed_plan=self.review())
        self.store.finish(self.key, job['run_id'], 'simulated')
        with self.store.connect() as conn:
            conn.execute("UPDATE recon_jobs SET run_id='old-version', status='completed'")
            conn.execute("""INSERT INTO recon_job_history
                SELECT engagement_type, engagement_id, run_id, status, stage, dry_run,
                       started_at, finished_at, error, NULL, 'dashboard' FROM recon_jobs""")
        reopened = ReconJobStore(self.db)
        self.assertEqual(len(reopened.history(self.key)['jobs']), 2)
        with reopened.connect() as conn:
            conn.execute('DELETE FROM recon_job_history')
            conn.execute('DELETE FROM recon_jobs')
        restored = ReconJobStore(self.db)
        with restored.connect() as conn:
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM recon_job_reviews').fetchone()[0], 0)

    def test_passive_source_does_not_claim_active_target_authorization(self):
        preview = {'generated_at': '2026-10-08T00:00:00Z', 'stage': 'subdomains', 'dry_run': False,
                   'can_start': True, 'scope_revision': 'a'*64, 'plan_revision': 'b'*64,
                   'authorization': {'reference_present': True, 'allow_passive': True,
                                     'allow_active': False, 'valid_from': '', 'valid_until': ''},
                   'operational_limits': {}, 'stages': [{'stage': 'subdomains', 'interaction': 'passive',
                   'targets_pending': False, 'targets_count': 1, 'discarded_count': 0,
                   'targets': ['example.test'], 'discarded': []}]}
        self.assertEqual(reviewed_plan(preview)['stages'][0]['targets'][0]['verdict'], 'PASSIVE_SOURCE')
