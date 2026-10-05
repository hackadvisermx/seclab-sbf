import pathlib
import tarfile
import tempfile
import unittest
from unittest.mock import patch

from app.services import runner_service as module


class TestRunnerTools(unittest.TestCase):
    def test_source_and_installed_tool_resolution(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            installed = root / 'pt-next'
            installed.touch()
            runner = module.RunnerService()
            with patch.object(module, 'SCRIPTS_DIR', root):
                self.assertEqual(runner._script('pt-audit-next.py', 'pt-next'), installed)
                source = root / 'pt-audit-next.py'
                source.touch()
                self.assertEqual(runner._script('pt-audit-next.py', 'pt-next'), source)

    def test_installed_audit_workflow_without_network(self):
        if not pathlib.Path('/usr/local/bin/pt-scope-validator').is_file():
            self.skipTest('Integration requires the local lab image')
        with tempfile.TemporaryDirectory() as directory:
            project = pathlib.Path(directory)
            (project / 'evidence').mkdir()
            (project / 'recon').mkdir()
            (project / 'scope.txt').write_text('example.test\n')
            (project / 'target.yaml').write_text(
                'engagement:\n  name: runner-test\n  client: Test\n'
                'scope:\n  in_scope:\n    domains: [example.test]\n'
                '  out_of_scope:\n    domains: []\n'
            )
            runner = module.RunnerService()
            self.assertTrue(runner.check_scope('example.test', str(project)).allowed)
            self.assertFalse(runner.check_scope('outside.test', str(project)).allowed)
            compiled = runner.compile_report(str(project))
            self.assertTrue(compiled['success'], compiled['log'])
            self.assertTrue((project / 'REPORT.md').is_file())
            checklist = runner.get_audit_checklist(str(project))
            self.assertNotIn('raw_output', checklist, checklist)
            next_step = runner.get_audit_next_step(str(project))
            self.assertNotIn('raw', next_step, next_step)
            context = runner.get_agent_context(str(project))
            self.assertNotIn("can't open file", context)
            self.assertIn('runner-test', context)
            packed = runner.pack_engagement(str(project))
            self.assertTrue(packed['success'], packed)
            archive = next((project / 'exports').glob('*.tar.gz'))
            with tarfile.open(archive) as bundle:
                self.assertTrue(any(name.endswith('/REPORT.md') or name == 'REPORT.md' for name in bundle.getnames()))
