import json
import pathlib
import tempfile
import unittest
import subprocess
from unittest.mock import patch

from app.services import recon_service as module


class TestReconExecutionSafety(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db_path = pathlib.Path(self.temp.name) / 'jobs.db'

    def test_installed_pipeline_dry_run_and_failure_are_distinct_without_network(self):
        service = module.ReconService(self.db_path)
        self.assertTrue(service.pipeline_script.is_file())
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            (root / 'target.yaml').write_text('scope:\n  in_scope:\n    domains: [example.test]\n')
            recon = root / 'recon'
            recon.mkdir()
            log = recon / 'recon.log'
            key = ('engagement', 'fixture')
            job = service.store.begin(key, 'all', True)
            service._execute_pipeline_worker(key, root, 'all', True, log, job['run_id'])
            self.assertEqual(service.store.get(key)['status'], 'simulated', log.read_text())
            self.assertFalse((recon / 'summary.json').exists())
            self.assertFalse((recon / 'subdomains.txt').exists())
            self.assertFalse((root / 'terminal.log').exists())
            job = service.store.begin(key, 'probe', False)
            service._execute_pipeline_worker(key, root, 'probe', False, log, job['run_id'])
            self.assertEqual(service.store.get(key)['status'], 'failed', log.read_text())
            summary = json.loads((recon / 'summary.json').read_text())
            self.assertEqual(summary['status'], 'failed')
            self.assertEqual(summary['live_hosts_count'], 0)
            self.assertFalse((recon / 'live_hosts.txt').exists())

    def test_invalid_stage_cannot_create_job_or_start_worker(self):
        service = module.ReconService(self.db_path)
        with patch.object(module.threading, 'Thread') as worker:
            self.assertFalse(service.run_pipeline('fixture', 'unexpected')['success'])
            worker.assert_not_called()
        self.assertIsNone(service.store.get(('engagement', 'fixture')))

    def test_installed_initial_scope_rejection_is_blocked_without_replacing_artifacts(self):
        service = module.ReconService(self.db_path)
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            (root / 'target.yaml').write_text('scope: [invalid')
            recon = root / 'recon'
            recon.mkdir()
            (recon / 'summary.json').write_text('{"run_id":"previous","status":"completed"}')
            (recon / 'subdomains.txt').write_text('example.test\n')
            before = {path.name: path.read_bytes() for path in recon.iterdir()}
            key = ('engagement', 'fixture')
            job = service.store.begin(key, 'probe', False)
            service._execute_pipeline_worker(key, root, 'probe', False, recon / 'recon.log', job['run_id'])
            current = service.store.get(key)
            self.assertEqual(current['status'], 'blocked')
            self.assertNotEqual(current['error'], 'Código de salida: 1')
            self.assertEqual(before, {name: (recon / name).read_bytes() for name in before})
            reopened = module.ReconService(self.db_path)
            self.assertEqual(reopened.store.history(key)['jobs'][0]['status'], 'blocked')

    def test_installed_changed_plan_at_worker_start_is_blocked_without_new_summary(self):
        service = module.ReconService(self.db_path)
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            (root / 'target.yaml').write_text('scope:\n  in_scope:\n    domains: [example.test]\n')
            recon = root / 'recon'
            recon.mkdir()
            hosts = recon / 'subdomains.txt'
            hosts.write_text('example.test\n')
            preview = subprocess.run([service.py_bin, str(service.pipeline_script), 'preview', str(root),
                                      '--stage', 'probe', '--dry-run'], capture_output=True, text=True, check=True)
            revision = json.loads(preview.stdout)['plan_revision']
            hosts.write_text('unknown.test\n')
            key = ('engagement', 'fixture')
            job = service.store.begin(key, 'probe', True)
            service._execute_pipeline_worker(key, root, 'probe', True, recon / 'recon.log', job['run_id'], revision)
            current = service.store.get(key)
            self.assertEqual(current['status'], 'blocked')
            self.assertIn('plan revisado cambió', current['error'])
            self.assertFalse((recon / 'summary.json').exists())
            self.assertFalse((recon / 'progress.json').exists())
            self.assertEqual(hosts.read_text(), 'unknown.test\n')
