import json
import pathlib
import sqlite3
import tempfile
import threading
import unittest
from contextlib import closing
from unittest.mock import patch, Mock

from fastapi.testclient import TestClient
from app.api.endpoints import recon, checklist, auth
from app.core.recon_jobs import ReconJobStore, TERMINAL_STATUSES
from app.core.recon_decision import recon_decision
from app.main import app
from app.services import recon_service as module
from app.services.workspace_sync import WorkspaceSyncService


class TestReconOutcomeReview(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = pathlib.Path(temporary.name)
        self.ws = WorkspaceSyncService(self.root / 'workspace')
        self.ws.create_engagement('fixture')
        self.ws.create_engagement('fixture', eng_type='reto')
        self.service = module.ReconService(self.root / 'state/jobs.db')
        self.store = self.service.store
        self.key = ('engagement', 'fixture')

    def final(self, status='blocked', key=None):
        key = key or self.key
        job = self.store.begin(key, 'probe', status == 'simulated')
        self.store.finish(key, job['run_id'], status, 'private-token-DO-NOT-COPY', 'a' * 64)
        return self.store.get(key)

    def review(self, job, key=None):
        return self.store.review_outcome(key or self.key, job['run_id'], job['outcome_revision'])

    def test_all_final_states_preserve_outcome_and_idempotent_review_after_restart_and_backup(self):
        for status in TERMINAL_STATUSES:
            with self.subTest(status=status):
                job = self.final(status)
                history = self.store.history(self.key)['jobs'][0]
                self.assertEqual(history['outcome_revision'], job['outcome_revision'])
                reviewed = self.review(job)
                self.assertEqual(reviewed['status'], status)
                self.assertEqual(reviewed['finished_at'], job['finished_at'])
                self.assertEqual(reviewed['error'], job['error'])
                record = reviewed['outcome_review']
                self.assertEqual(record['decision'], 'prepare_new_plan')
                self.assertEqual(record['job_revision'], job['outcome_revision'])
                self.assertTrue(record['reviewed_at'].endswith('+00:00'))
                self.assertEqual(self.review(job)['outcome_review'], record)
                self.assertEqual(ReconJobStore(self.store.path).get(self.key)['outcome_review'], record)
                self.assertEqual(self.store.history(self.key)['jobs'][0]['outcome_review'], record)
                decision = recon_decision(reviewed)
                self.assertEqual(decision['next_step']['id'], 'recon_prepare_plan')
                self.assertIsNone(decision['next_step']['command'])
                self.assertFalse(decision['prompt_available'])
        snapshot = self.root / 'snapshot.db'
        with closing(self.store.connect()) as source, closing(sqlite3.connect(snapshot)) as destination:
            source.backup(destination)
        self.assertEqual(ReconJobStore(snapshot).history(self.key), self.store.history(self.key))
        with closing(self.store.connect()) as conn:
            reviews = [dict(row) for row in conn.execute('SELECT * FROM recon_job_outcome_reviews')]
        self.assertNotIn('private-token', json.dumps(reviews))
        self.assertEqual(len(reviews), len(TERMINAL_STATUSES))

    def test_active_stale_foreign_or_changed_outcomes_cannot_be_reviewed(self):
        running = self.store.begin(self.key, 'probe', False)
        for status in ('running', 'cancelling'):
            if status == 'cancelling': self.store.request_cancel(self.key)
            with self.assertRaises(RuntimeError): self.review(self.store.get(self.key))
        self.store.finish(self.key, running['run_id'], 'cancelled')
        old = self.store.get(self.key)
        current = self.final()
        with self.assertRaises(RuntimeError): self.review(old)
        with self.assertRaises(RuntimeError): self.review(current, ('reto', 'fixture'))
        reviewed = self.review(current)
        with closing(self.store.connect()) as conn, conn:
            conn.execute("UPDATE recon_jobs SET error='changed' WHERE run_id=?", (current['run_id'],))
            conn.execute("UPDATE recon_job_history SET error='changed' WHERE run_id=?", (current['run_id'],))
        changed = self.store.get(self.key)
        self.assertIsNone(changed['outcome_review'])
        self.assertNotEqual(changed['outcome_revision'], reviewed['outcome_revision'])
        with self.assertRaises(RuntimeError): self.review(current)
        self.assertIsNotNone(self.review(changed)['outcome_review'])

    def test_scope_plan_and_result_changes_invalidate_the_review(self):
        job = self.final()
        self.review(job)
        with closing(self.store.connect()) as conn, conn:
            conn.execute("UPDATE recon_job_history SET scope_revision=? WHERE run_id=?", ('b'*64, job['run_id']))
        changed = self.store.get(self.key)
        self.assertIsNone(changed['outcome_review'])
        self.review(changed)
        with closing(self.store.connect()) as conn, conn:
            conn.execute('INSERT INTO recon_job_reviews VALUES (?, ?, ?, ?)', (*self.key, job['run_id'], '{"schema_version":1}'))
        self.assertIsNone(self.store.get(self.key)['outcome_review'])
        self.review(self.store.get(self.key))
        with closing(self.store.connect()) as conn, conn:
            conn.execute('INSERT INTO recon_job_results VALUES (?, ?, ?, ?)', (*self.key, job['run_id'], '{}'))
        self.assertIsNone(self.store.get(self.key)['outcome_review'])

    def test_simultaneous_review_and_new_job_never_review_the_new_job(self):
        old = self.final('failed')
        other = ReconJobStore(self.store.path)
        barrier = threading.Barrier(2)
        errors = []
        def review():
            barrier.wait()
            try: self.review(old)
            except RuntimeError: errors.append('stale')
        def begin():
            barrier.wait()
            other.begin(self.key, 'urls', True)
        threads = [threading.Thread(target=review), threading.Thread(target=begin)]
        for thread in threads: thread.start()
        for thread in threads: thread.join(5)
        self.assertTrue(all(not thread.is_alive() for thread in threads))
        current = self.store.get(self.key)
        self.assertEqual(current['status'], 'running')
        self.assertIsNone(current['outcome_review'])
        previous = self.store.history(self.key)['jobs'][1]
        self.assertEqual(previous['status'], 'failed')
        self.assertEqual(previous['outcome_review'] is None, bool(errors))

    def test_review_is_scoped_even_when_projects_share_run_id_and_deletion_preserves_other_type(self):
        with patch('app.core.recon_jobs.uuid.uuid4', return_value=Mock(hex='c'*32)):
            first = self.final()
            second = self.final(key=('reto', 'fixture'))
        with self.assertRaises(RuntimeError): self.review(first, ('reto', 'fixture'))
        self.review(first)
        self.review(second, ('reto', 'fixture'))
        self.store.delete(self.key)
        self.assertEqual(self.store.history(self.key)['jobs'], [])
        self.assertIsNotNone(self.store.get(('reto', 'fixture'))['outcome_review'])
        with closing(self.store.connect()) as conn:
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM recon_job_outcome_reviews').fetchone()[0], 1)

    def test_corrupt_review_and_legacy_downgrade_never_present_a_current_review(self):
        job = self.final('failed')
        self.review(job)
        with closing(self.store.connect()) as conn, conn:
            self.assertEqual(len(conn.execute('PRAGMA table_info(recon_jobs)').fetchall()), 9)
            conn.execute("UPDATE recon_job_outcome_reviews SET reviewed_at='not-UTC'")
        self.assertIsNone(self.store.get(self.key)['outcome_review'])
        self.review(self.store.get(self.key))
        with closing(self.store.connect()) as conn, conn:
            conn.execute("UPDATE recon_jobs SET status='running', finished_at=NULL WHERE run_id=?", (job['run_id'],))
        reopened = ReconJobStore(self.store.path)
        self.assertIsNone(reopened.get(self.key)['outcome_review'])
        self.assertIsNone(reopened.history(self.key)['jobs'][0]['outcome_review'])
        with self.assertRaises(RuntimeError):
            reopened.review_outcome(self.key, job['run_id'], job['outcome_revision'])

    def test_review_changes_only_local_next_decision_and_keeps_terminal_status_and_permissions(self):
        for status in ('blocked', 'failed', 'cancelled', 'interrupted'):
            job = self.final(status)
            self.assertEqual(recon_decision(job)['next_step']['id'], 'recon_' + status)
            result = recon_decision(self.review(job))
            self.assertEqual(result['decision_job']['status'], status)
            self.assertIn('Preparar otro plan', result['next_step']['title'])
            self.assertEqual(result['next_step']['action']['view'], 'recon')
            self.assertIsNone(result['next_step']['command'])
            self.assertFalse(result['next_step']['ready_for_closure'])
            self.assertFalse(result['prompt_available'])
            self.assertEqual(result['prompt'], '')
        self.store.begin(self.key, 'probe', False)
        self.assertEqual(recon_decision(self.store.get(self.key))['next_step']['id'], 'recon_running')

    def test_api_requires_authentication_exact_revision_and_never_executes_or_edits_workspace(self):
        target = self.root / 'workspace/engagements/fixture/target.yaml'
        before = target.read_bytes()
        job = self.final()
        body = {'run_id': job['run_id'], 'expected_revision': job['outcome_revision']}
        with patch.object(module, 'WORKSPACE_DIR', self.root / 'workspace'), \
                patch.object(recon, 'recon_service', self.service), \
                patch.object(checklist, 'recon_service', self.service), \
                patch.object(checklist, 'workspace_service', self.ws), \
                patch.object(module.subprocess, 'Popen') as launch:
            client = TestClient(app)
            self.addCleanup(client.close)
            url = '/api/v1/recon/fixture/review'
            self.assertEqual(client.post(url, json=body).status_code, 401)
            app.dependency_overrides[auth.require_operator] = lambda: 'fixture-only'
            try:
                for malformed in [{}, {**body, 'expected_revision': 'bad'}, {**body, 'run_id': '../bad'},
                                  {**body, 'decision': 'execute'}, {**body, 'reason': 'secret'}]:
                    self.assertEqual(client.post(url, json=malformed).status_code, 422)
                self.assertEqual(client.post(url, json={**body, 'expected_revision': '0'*64}).status_code, 409)
                self.assertEqual(client.post(url+'?type=reto', json=body).status_code, 409)
                self.assertEqual(client.post('/api/v1/recon/missing/review', json=body).status_code, 404)
                response = client.post(url, json=body)
                self.assertEqual(response.status_code, 200, response.text)
                self.assertEqual(response.json()['job']['status'], 'blocked')
                decision = client.get('/api/v1/checklist/fixture/next?prompt=true').json()
                self.assertIn('Preparar otro plan', decision['next_step']['title'])
                self.assertFalse(decision['prompt_available'])
                with patch.object(self.store, 'review_outcome', side_effect=sqlite3.OperationalError('private database path')):
                    error = client.post(url, json=body)
                    self.assertEqual(error.status_code, 503)
                    self.assertNotIn('private database', error.text)
                launch.assert_not_called()
                self.assertEqual(target.read_bytes(), before)
            finally:
                app.dependency_overrides.pop(auth.require_operator, None)
