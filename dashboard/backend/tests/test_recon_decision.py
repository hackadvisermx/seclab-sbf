import pathlib
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient
from app.api.endpoints import checklist, auth
from app.core.recon_jobs import ReconJobStore
from app.main import app
from app.services.workspace_sync import WorkspaceSyncService


class TestReconDecision(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = pathlib.Path(temporary.name)
        self.ws = WorkspaceSyncService(self.root / 'workspace')
        for project, kind in [('fixture', 'engagement'), ('fixture', 'reto'), ('other', 'engagement')]:
            self.ws.create_engagement(project, eng_type=kind)
        self.db = self.root / 'jobs.db'
        self.store = ReconJobStore(self.db)
        self.key = ('engagement', 'fixture')
        self.runner_result = {'next_step': {'id': 'fuzzing', 'command': 'pt-fuzz-params <url>'}, 'prompt': 'legacy execution prompt'}
        for patcher in [patch.object(checklist, 'workspace_service', self.ws),
                        patch.object(checklist, 'recon_service', SimpleNamespace(store=self.store))]:
            patcher.start()
            self.addCleanup(patcher.stop)
        patcher = patch.object(checklist.runner_service, 'get_audit_next_step', return_value=self.runner_result)
        self.runner = patcher.start()
        self.addCleanup(patcher.stop)
        app.dependency_overrides[auth.require_operator] = lambda: 'fixture-only'
        self.addCleanup(app.dependency_overrides.pop, auth.require_operator, None)
        self.client = TestClient(app)
        self.addCleanup(self.client.close)

    def job(self, status, key=None):
        key = key or self.key
        job = self.store.begin(key, 'probe', False)
        if status == 'cancelling':
            self.store.request_cancel(key)
        elif status != 'running':
            self.store.finish(key, job['run_id'], status, 'SECRET https://private.test/?token=private')
        return job

    def get(self, prompt=False, query=''):
        response = self.client.get('/api/v1/checklist/fixture/next?prompt=' + str(prompt).lower() + query)
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def test_failed_job_takes_precedence_over_prior_artifacts_and_prompt(self):
        job = self.job('failed')
        (self.root / 'workspace/engagements/fixture/recon/live_hosts.txt').write_text('https://example.test\n')
        for prompt in (False, True):
            result = self.get(prompt)
            self.assertEqual(result['next_step']['id'], 'recon_failed')
            self.assertEqual(result['decision_job']['run_id'], job['run_id'])
            self.assertIsNone(result['next_step']['command'])
            self.assertEqual(result['next_step']['action']['view'], 'recon')
            self.assertFalse(result['next_step']['ready_for_closure'])
            self.assertFalse(result['prompt_available'])
            self.assertEqual(result['prompt'], '')
            self.assertNotIn('SECRET', str(result))
            self.assertNotIn('private.test', str(result))
            self.assertNotIn('fuzzing', str(result))
        self.runner.assert_not_called()

    def test_each_unfinished_state_has_an_explicit_local_decision(self):
        for status in ('running', 'cancelling', 'blocked', 'cancelled', 'interrupted'):
            with self.subTest(status=status):
                self.store.delete(self.key)
                job = self.job(status)
                result = self.get(True)
                self.assertEqual(result['next_step']['id'], 'recon_' + status)
                self.assertEqual(result['decision_job']['status'], status)
                self.assertEqual(result['decision_job']['run_id'], job['run_id'])
                self.assertEqual(result['next_step']['action']['view'], 'scope' if status == 'blocked' else 'recon')
                self.assertIsNone(result['next_step']['command'])
                self.assertFalse(result['prompt_available'])
        self.runner.assert_not_called()

    def test_missing_completed_and_simulated_jobs_preserve_the_cli_contract(self):
        self.assertEqual(self.get(), self.runner_result)
        for status in ('completed', 'simulated'):
            self.store.delete(self.key)
            job = self.store.begin(self.key, 'probe', status == 'simulated')
            self.store.finish(self.key, job['run_id'], status)
            self.assertEqual(self.get(True), self.runner_result)
        self.assertEqual(self.runner.call_count, 3)
        self.assertEqual(self.runner.call_args.kwargs, {'prompt_mode': True})

    def test_state_survives_reopening_and_isolated_by_project_and_type(self):
        job = self.job('blocked')
        self.job('failed', ('reto', 'fixture'))
        self.job('cancelled', ('engagement', 'other'))
        checklist.recon_service.store = ReconJobStore(self.db)
        self.assertEqual(self.get()['decision_job']['run_id'], job['run_id'])
        self.assertEqual(self.get(query='&type=reto')['next_step']['id'], 'recon_failed')
        other = self.client.get('/api/v1/checklist/other/next').json()
        self.assertEqual(other['next_step']['id'], 'recon_cancelled')
        self.store.delete(self.key)
        self.assertEqual(self.get(), self.runner_result)
        self.assertEqual(self.get(query='&type=reto')['next_step']['id'], 'recon_failed')

    def test_job_starting_during_cli_generation_discards_execution_prompt(self):
        def generate(*args, **kwargs):
            self.job('running')
            return self.runner_result
        self.runner.side_effect = generate
        result = self.get(True)
        self.assertEqual(result['next_step']['id'], 'recon_running')
        self.assertFalse(result['prompt_available'])
        self.assertEqual(result['prompt'], '')
        self.assertNotIn('legacy', str(result))

    def test_authentication_and_invalid_or_missing_projects(self):
        app.dependency_overrides.pop(auth.require_operator)
        self.assertEqual(self.client.get('/api/v1/checklist/fixture/next').status_code, 401)
        app.dependency_overrides[auth.require_operator] = lambda: 'fixture-only'
        self.assertEqual(self.client.get('/api/v1/checklist/missing/next').status_code, 404)
        self.assertEqual(self.client.get('/api/v1/checklist/fixture/next?type=invalid').status_code, 400)
        self.runner.assert_not_called()

    def test_unavailable_store_does_not_offer_an_unchecked_cli_recommendation(self):
        with patch.object(self.store, 'get', side_effect=OSError('private state path')):
            response = self.client.get('/api/v1/checklist/fixture/next')
            self.assertEqual(response.status_code, 503)
            self.assertNotIn('private state path', response.text)
        self.runner.assert_not_called()
