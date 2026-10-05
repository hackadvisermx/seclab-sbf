import json
import pathlib
import tempfile
import unittest
from unittest.mock import patch

from app.services import recon_service as module


class TestReconExecutionSafety(unittest.TestCase):
    def test_installed_pipeline_dry_run_and_failure_are_distinct_without_network(self):
        service = module.ReconService()
        self.assertTrue(service.pipeline_script.is_file())
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            (root / 'target.yaml').write_text('scope:\n  in_scope:\n    domains: [example.test]\n')
            recon = root / 'recon'
            recon.mkdir()
            log = recon / 'recon.log'
            key = ('engagement', 'fixture')
            service._jobs[key] = {'status': 'running'}
            service._execute_pipeline_worker(key, root, 'all', True, log)
            self.assertEqual(service._jobs[key]['status'], 'simulated', log.read_text())
            self.assertFalse((recon / 'summary.json').exists())
            self.assertFalse((recon / 'subdomains.txt').exists())
            self.assertFalse((root / 'terminal.log').exists())
            service._jobs[key] = {'status': 'running'}
            service._execute_pipeline_worker(key, root, 'probe', False, log)
            self.assertEqual(service._jobs[key]['status'], 'failed', log.read_text())
            summary = json.loads((recon / 'summary.json').read_text())
            self.assertEqual(summary['status'], 'failed')
            self.assertEqual(summary['live_hosts_count'], 0)
            self.assertFalse((recon / 'live_hosts.txt').exists())

    def test_invalid_stage_cannot_create_job_or_start_worker(self):
        service = module.ReconService()
        with patch.object(module.threading, 'Thread') as worker:
            self.assertFalse(service.run_pipeline('fixture', 'unexpected')['success'])
            worker.assert_not_called()
        self.assertEqual(service._jobs, {})
