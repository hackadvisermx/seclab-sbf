import copy
import hashlib
import importlib.machinery
import importlib.util
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPTS = pathlib.Path(os.environ.get('CHECKPOINT_SCRIPTS', pathlib.Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(SCRIPTS))
source = SCRIPTS / ('pt-recon-pipeline' if os.environ.get('CHECKPOINT_SCRIPTS') else 'pt-recon-pipeline.py')
loader = importlib.machinery.SourceFileLoader('checkpoint_pipeline', str(source))
spec = importlib.util.spec_from_loader(loader.name, loader)
pipeline = importlib.util.module_from_spec(spec)
loader.exec_module(pipeline)


class CheckpointIntegrityTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = pathlib.Path(temporary.name)
        (self.root / 'target.yaml').write_text(
            'scope:\n  in_scope:\n    ips: ["10.0.0.1"]\nauthorization:\n'
            '  reference: isolated-fixture\n  valid_from: "2000-01-01T00:00:00Z"\n'
            '  valid_until: "2099-01-01T00:00:00Z"\n  allow_passive: true\n  allow_active: true\n')
        self.checkpoint = self.root / 'recon/.checkpoint.json'
        self.addCleanup(patch.stopall)
        patch.object(pipeline, 'detect_tools', return_value={}).start()
        patch.object(pipeline, 'send_notification').start()

    def engine(self, dry_run=False):
        return pipeline.ReconPipeline(self.root, dry_run=dry_run)

    def fail_after_subdomains(self):
        with patch.object(pipeline, 'ProbeClient') as client:
            client.return_value.probe.side_effect = OSError('isolated probe failure')
            result = self.engine().run_all()
        self.assertEqual(result['summary']['resumable_from'], 'probe')
        return json.loads(self.checkpoint.read_text())

    def file_state(self):
        return {str(path.relative_to(self.root)): path.read_bytes() for path in self.root.rglob('*')
                if path.is_file() and not path.is_symlink()}

    def assert_resume_blocked(self):
        before = self.file_state()
        with patch.object(pipeline, 'ProbeClient') as client, \
                patch.object(pipeline.subprocess, 'run') as command, \
                patch.object(pipeline.socket, 'getaddrinfo') as dns:
            with self.assertRaisesRegex(pipeline.ScopeError, 'checkpoint.*sin --resume'):
                self.engine().run_all(resume=True)
        client.assert_not_called()
        command.assert_not_called()
        dns.assert_not_called()
        self.assertEqual(self.file_state(), before)

    def test_modified_completed_output_blocks_resume_without_writes_or_network(self):
        self.fail_after_subdomains()
        (self.root / 'recon/subdomains.txt').write_text('10.0.0.1\n10.0.0.2\n')
        self.assert_resume_blocked()

    def test_unchanged_resume_skips_completed_stage_and_removes_checkpoint(self):
        saved = self.fail_after_subdomains()
        self.assertEqual(saved['schema_version'], 2)
        self.assertEqual(saved['artifact_refs']['subdomains'][0], {
            'path': 'recon/subdomains.txt', 'sha256': hashlib.sha256(b'10.0.0.1\n').hexdigest(), 'size': 9})
        os.utime(self.root / 'recon/subdomains.txt', (1, 1))
        with patch.object(pipeline.ReconPipeline, 'run_subdomain_enumeration') as completed, \
                patch.object(pipeline, 'ProbeClient') as client:
            client.return_value.probe.return_value = []
            result = self.engine().run_all(resume=True)
        completed.assert_not_called()
        self.assertEqual(result['summary']['status'], 'completed')
        self.assertFalse(self.checkpoint.exists())

    def test_every_completed_output_is_checked_even_when_not_a_next_stage_input(self):
        with patch.object(pipeline, 'ProbeClient') as client, \
                patch.object(pipeline.ReconPipeline, 'run_url_harvesting', side_effect=pipeline.StageError('fixture')):
            client.return_value.probe.return_value = []
            self.engine().run_all()
        saved = json.loads(self.checkpoint.read_text())
        self.assertEqual(set(saved['artifact_refs']), {'subdomains', 'probe'})
        for items in saved['artifact_refs'].values():
            for ref in items:
                path = self.root / ref['path']
                original = path.read_bytes()
                with self.subTest(path=ref['path']):
                    path.write_bytes(original + b'edited\n')
                    self.assert_resume_blocked()
                    path.write_bytes(original)

    def test_missing_symlink_and_nonregular_outputs_are_rejected(self):
        self.fail_after_subdomains()
        path = self.root / 'recon/subdomains_new.txt'
        original = path.read_bytes()
        path.unlink()
        self.assert_resume_blocked()
        destination = self.root / 'external.txt'
        destination.write_bytes(original)
        path.symlink_to(destination)
        self.assert_resume_blocked()
        path.unlink()
        os.mkfifo(path)
        self.assert_resume_blocked()
        path.unlink()
        path.write_bytes(original)

    def test_corrupt_legacy_and_incomplete_checkpoints_never_start_a_fresh_run(self):
        saved = self.fail_after_subdomains()
        variants = ['{invalid', '[]', '{}', json.dumps(saved)[:-1] + ',"schema_version":2}']
        for key in ('schema_version', 'artifact_refs', 'scope_revision'):
            item = copy.deepcopy(saved)
            item.pop(key)
            variants.append(json.dumps(item))
        for edit in (
            lambda item: item.update(schema_version=True),
            lambda item: item.update(failed_stage='urls'),
            lambda item: item.update(timestamp='invalid'),
            lambda item: item['artifact_refs']['subdomains'].pop(),
            lambda item: item['artifact_refs']['subdomains'][0].update(path='../external.txt'),
            lambda item: item['artifact_refs']['subdomains'][0].update(sha256='z' * 64),
            lambda item: item['artifact_refs']['subdomains'][0].update(size=True),
            lambda item: item['completed']['subdomains'].update(status='failed'),
        ):
            item = copy.deepcopy(saved)
            edit(item)
            variants.append(json.dumps(item))
        for content in variants:
            with self.subTest(content=content[:80]):
                self.checkpoint.write_text(content)
                self.assert_resume_blocked()

    def test_checkpoint_symlink_and_fifo_are_rejected(self):
        self.fail_after_subdomains()
        destination = self.root / 'checkpoint-copy.json'
        destination.write_bytes(self.checkpoint.read_bytes())
        self.checkpoint.unlink()
        self.checkpoint.symlink_to(destination)
        self.assert_resume_blocked()
        self.checkpoint.unlink()
        os.mkfifo(self.checkpoint)
        self.assert_resume_blocked()
        self.checkpoint.unlink()

    def test_hashes_are_captured_at_stage_completion_not_after_a_later_failure(self):
        def fail_and_edit(*args, **kwargs):
            (self.root / 'recon/subdomains.txt').write_text('changed after completion\n')
            raise OSError('isolated probe failure')
        with patch.object(pipeline, 'ProbeClient') as client:
            client.return_value.probe.side_effect = fail_and_edit
            self.engine().run_all()
        saved = json.loads(self.checkpoint.read_text())
        self.assertEqual(saved['artifact_refs']['subdomains'][0]['sha256'], hashlib.sha256(b'10.0.0.1\n').hexdigest())
        self.assert_resume_blocked()

    def test_unavailable_fingerprint_does_not_mark_stage_completed(self):
        with patch.object(pipeline, 'read_artifact_snapshot', return_value={'size': pipeline.HASH_LIMIT + 1, 'sha256': None}), \
                patch.object(pipeline, 'ProbeClient') as client:
            result = self.engine().run_all()
        client.assert_not_called()
        self.assertEqual(result['summary']['resumable_from'], 'subdomains')
        saved = json.loads(self.checkpoint.read_text())
        self.assertEqual(saved['completed'], {})
        self.assertEqual(saved['artifact_refs'], {})

    def test_dry_run_ignores_checkpoint_without_writes_or_tool_calls(self):
        self.fail_after_subdomains()
        self.checkpoint.write_text('{invalid')
        before = self.file_state()
        with patch.object(pipeline, 'read_artifact_snapshot') as read, patch.object(pipeline, 'ProbeClient') as client:
            result = self.engine(dry_run=True).run_all(resume=True)
        read.assert_not_called()
        client.assert_not_called()
        self.assertEqual(result['summary']['status'], 'simulated')
        self.assertEqual(self.file_state(), before)

    def test_explicit_fresh_run_replaces_legacy_checkpoint(self):
        self.fail_after_subdomains()
        self.checkpoint.write_text('{}')
        with patch.object(pipeline, 'ProbeClient') as client:
            client.return_value.probe.return_value = []
            result = self.engine().run_all()
        self.assertEqual(result['summary']['status'], 'completed')
        self.assertFalse(self.checkpoint.exists())

    def test_aggregate_fingerprint_budget_blocks_before_the_next_stage(self):
        with patch.object(pipeline, 'read_artifact_snapshot', return_value={'size': pipeline.HASH_LIMIT // 2, 'sha256': 'a' * 64}), \
                patch.object(pipeline, 'ProbeClient') as client:
            result = self.engine().run_all()
        client.assert_not_called()
        self.assertEqual(result['summary']['resumable_from'], 'subdomains')
        self.assertEqual(json.loads(self.checkpoint.read_text())['artifact_refs'], {})

    def test_cli_rejects_stale_checkpoint_and_reports_private_initial_block(self):
        self.fail_after_subdomains()
        (self.root / 'recon/subdomains.txt').write_text('changed fixture\n')
        before = self.file_state()
        with tempfile.TemporaryFile() as channel:
            result = subprocess.run([sys.executable, str(source), 'run', str(self.root), '--resume', '--json'],
                capture_output=True, text=True, timeout=10, pass_fds=(channel.fileno(),),
                env={**os.environ, 'SECLAB_RECON_RUN_ID': 'fixture-only', 'SECLAB_RECON_FAILURE_FD': str(channel.fileno())})
            channel.seek(0)
            outcome = json.load(channel)
        self.assertEqual((result.returncode, result.stdout), (1, ''))
        self.assertIn('checkpoint', result.stderr)
        self.assertNotIn('changed fixture', result.stderr)
        self.assertEqual(outcome['run_id'], 'fixture-only')
        self.assertEqual(outcome['failure_kind'], 'scope_guard')
        self.assertEqual(self.file_state(), before)


if __name__ == '__main__':
    unittest.main(verbosity=2)
