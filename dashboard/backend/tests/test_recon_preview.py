import json
import pathlib
import tempfile
import unittest
from unittest.mock import patch
from app.services import recon_service as module


class TestReconPreview(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = pathlib.Path(self.temporary.name)
        self.target = self.root / 'workspace/engagements/fixture'
        self.target.mkdir(parents=True)
        (self.target / 'target.yaml').write_text('scope:\n  in_scope:\n    domains: [example.test]\n')
        (self.target / 'recon').mkdir()
        (self.target / 'recon/subdomains.txt').write_text('example.test\nunknown.test\n')
        patched = patch.object(module, 'WORKSPACE_DIR', self.root / 'workspace')
        patched.start()
        self.addCleanup(patched.stop)
        self.service = module.ReconService(self.root / 'jobs.db')
        self.addCleanup(self.service.shutdown)

    def test_installed_preview_shows_authorization_block_without_job_or_artifact(self):
        before = {str(path): path.read_bytes() for path in self.target.rglob('*') if path.is_file()}
        result = self.service.preview_pipeline('fixture', 'probe')
        self.assertTrue(result['success'], result)
        self.assertFalse(result['can_start'])
        self.assertEqual(result['stages'][0]['targets'], ['example.test'])
        self.assertEqual(result['stages'][0]['discarded_count'], 1)
        self.assertIsNone(self.service.store.get(('engagement', 'fixture')))
        self.assertEqual(before, {str(path): path.read_bytes() for path in self.target.rglob('*') if path.is_file()})
        self.assertTrue(self.service.preview_pipeline('fixture', 'probe', True)['can_start'])

    def test_changed_inputs_or_permission_block_submission_before_job_creation(self):
        result = self.service.preview_pipeline('fixture', 'probe', True)
        (self.target / 'recon/subdomains.txt').write_text('changed.test\n')
        with patch.object(module.threading, 'Thread') as worker:
            blocked = self.service.run_pipeline('fixture', 'probe', True, expected_plan=result['plan_revision'])
            self.assertFalse(blocked['success'])
            worker.assert_not_called()
        (self.target / 'recon/subdomains.txt').write_text('example.test\n')
        denied = self.service.preview_pipeline('fixture', 'probe')
        with patch.object(module.threading, 'Thread') as worker:
            result = self.service.run_pipeline('fixture', 'probe', expected_plan=denied['plan_revision'])
            self.assertFalse(result['success'])
            worker.assert_not_called()
        self.assertIsNone(self.service.store.get(('engagement', 'fixture')))

    def test_missing_or_invalid_configuration_fails_closed(self):
        self.assertFalse(self.service.preview_pipeline('missing')['success'])
        (self.target / 'target.yaml').write_text('scope: [broken')
        self.assertFalse(self.service.preview_pipeline('fixture', dry_run=True)['success'])
        self.assertFalse(self.service.preview_pipeline('fixture', 'bad-stage')['success'])

    def test_preview_timeout_and_invalid_response_fail_closed(self):
        import subprocess
        with patch.object(module.subprocess, 'run', side_effect=subprocess.TimeoutExpired('preview', 10)):
            self.assertFalse(self.service.preview_pipeline('fixture')['success'])
        with patch.object(module.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, json.dumps([]), '')):
            self.assertFalse(self.service.preview_pipeline('fixture')['success'])

    def test_review_is_saved_before_worker_and_not_rebuilt_from_current_inputs(self):
        self.addCleanup(self.service._threads.clear)
        preview = self.service.preview_pipeline('fixture', 'probe', True)
        with patch.object(module.threading.Thread, 'start'):
            result = self.service.run_pipeline('fixture', 'probe', True, expected_plan=preview['plan_revision'])
        self.assertTrue(result['success'], result)
        review = self.service.get_history('fixture')['jobs'][0]['reviewed_plan']
        self.assertEqual(review['plan_revision'], preview['plan_revision'])
        self.assertEqual(review['scope_revision'], preview['scope_revision'])
        self.assertEqual(review['stages'][0]['targets'], [{'host': 'example.test', 'verdict': 'IN_SCOPE'}])
        self.assertEqual(review['stages'][0]['discarded'], [{'host': 'unknown.test', 'verdict': 'UNKNOWN'}])
        self.assertFalse(review['authorization']['allow_active'])
        self.service.store.finish(('engagement', 'fixture'), result['job']['run_id'], 'failed', 'fixture')
        (self.target / 'recon/subdomains.txt').write_text('changed.test\n')
        (self.target / 'target.yaml').write_text('scope:\n  in_scope:\n    domains: [changed.test]\n')
        reopened = module.ReconService(self.root / 'jobs.db')
        self.addCleanup(reopened.shutdown)
        job = reopened.get_history('fixture')['jobs'][0]
        self.assertEqual(job['reviewed_plan'], review)
        self.assertIsNone(job['scope_revision'])
        self.assertEqual(job['status'], 'failed')

    def test_no_review_is_invented_for_direct_api_and_incomplete_review_creates_no_job(self):
        self.addCleanup(self.service._threads.clear)
        with patch.object(module.threading.Thread, 'start'):
            result = self.service.run_pipeline('fixture', dry_run=True)
        self.assertTrue(result['success'])
        self.assertIsNone(self.service.get_history('fixture')['jobs'][0]['reviewed_plan'])
        self.service.store.finish(('engagement', 'fixture'), result['job']['run_id'], 'simulated')
        with patch.object(self.service, 'preview_pipeline', return_value={
                'success': True, 'plan_revision': 'a' * 64, 'can_start': True}):
            denied = self.service.run_pipeline('fixture', dry_run=True, expected_plan='a' * 64)
        self.assertFalse(denied['success'])
        self.assertEqual(len(self.service.get_history('fixture')['jobs']), 1)
