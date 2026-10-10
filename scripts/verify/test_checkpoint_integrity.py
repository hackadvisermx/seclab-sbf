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

    def test_resumed_stage_preserves_origin_and_is_not_counted_as_new_execution(self):
        with patch.dict(os.environ, {'SECLAB_RECON_RUN_ID': 'a' * 32}):
            saved = self.fail_after_subdomains()
        with patch.dict(os.environ, {'SECLAB_RECON_RUN_ID': 'b' * 32}), patch.object(pipeline, 'ProbeClient') as client:
            client.return_value.probe.return_value = []
            result = self.engine().run_all(resume=True)
        self.assertEqual(saved['completed']['subdomains']['origin_run_id'], 'a' * 32)
        self.assertEqual(result['summary']['stages_executed'], ['probe', 'urls', 'patterns'])
        self.assertEqual(result['summary']['stages_recovered'], ['subdomains'])
        self.assertEqual(result['stage_results']['subdomains']['execution'], 'recovered')
        self.assertEqual(result['stage_results']['subdomains']['origin_run_id'], 'a' * 32)
        for name in ('probe', 'urls', 'patterns'):
            self.assertEqual(result['stage_results'][name]['origin_run_id'], 'b' * 32)
            self.assertEqual(result['stage_results'][name]['execution'], 'current')

    def test_cli_without_external_job_id_gets_distinct_run_ids_and_retains_origin(self):
        with patch.dict(os.environ, {}, clear=True):
            saved = self.fail_after_subdomains()
            with patch.object(pipeline, 'ProbeClient') as client:
                client.return_value.probe.return_value = []
                result = self.engine().run_all(resume=True)
        origin = saved['completed']['subdomains']['origin_run_id']
        self.assertRegex(origin, r'^[a-f0-9]{32}$')
        self.assertNotEqual(origin, result['summary']['run_id'])
        self.assertEqual(result['stage_results']['subdomains']['origin_run_id'], origin)

    def test_repeated_resume_keeps_each_original_run_across_later_failures(self):
        with patch.dict(os.environ, {'SECLAB_RECON_RUN_ID': 'a' * 32}):
            self.fail_after_subdomains()
        with patch.dict(os.environ, {'SECLAB_RECON_RUN_ID': 'b' * 32}), patch.object(pipeline, 'ProbeClient') as client, \
                patch.object(pipeline.ReconPipeline, 'run_url_harvesting', side_effect=pipeline.StageError('fixture')):
            client.return_value.probe.return_value = []
            self.engine().run_all(resume=True)
        with patch.dict(os.environ, {'SECLAB_RECON_RUN_ID': 'c' * 32}), patch.object(pipeline, 'ProbeClient') as client:
            result = self.engine().run_all(resume=True)
        client.assert_not_called()
        self.assertEqual(result['summary']['stages_recovered'], ['subdomains', 'probe'])
        self.assertEqual(result['summary']['stages_executed'], ['urls', 'patterns'])
        self.assertEqual(result['stage_results']['subdomains']['origin_run_id'], 'a' * 32)
        self.assertEqual(result['stage_results']['probe']['origin_run_id'], 'b' * 32)
        self.assertEqual(result['stage_results']['urls']['origin_run_id'], 'c' * 32)

    def test_previous_v2_checkpoint_recovers_unknown_origin_without_inventing_one(self):
        saved = self.fail_after_subdomains()
        for field in ('execution', 'origin_run_id'):
            saved['completed']['subdomains'].pop(field)
        self.checkpoint.write_text(json.dumps(saved))
        with patch.dict(os.environ, {'SECLAB_RECON_RUN_ID': 'b' * 32}), patch.object(pipeline, 'ProbeClient') as client:
            client.return_value.probe.return_value = []
            result = self.engine().run_all(resume=True)
        self.assertIsNone(result['stage_results']['subdomains']['origin_run_id'])
        self.assertEqual(result['stage_results']['subdomains']['execution'], 'recovered')

    def test_invalid_checkpoint_origin_metadata_blocks_before_new_actions(self):
        saved = self.fail_after_subdomains()
        for origin in ('private/path', 'a' * 64, True, ['a' * 32]):
            edited = copy.deepcopy(saved)
            edited['completed']['subdomains']['origin_run_id'] = origin
            self.checkpoint.write_text(json.dumps(edited))
            self.assert_resume_blocked()
        edited = copy.deepcopy(saved)
        edited['completed']['subdomains']['execution'] = 'invented'
        self.checkpoint.write_text(json.dumps(edited))
        self.assert_resume_blocked()

    def test_manual_stage_has_current_origin_and_invalid_external_id_stays_unknown(self):
        for run_id, expected in [('a' * 32, 'a' * 32), ('private/path', None)]:
            with patch.dict(os.environ, {'SECLAB_RECON_RUN_ID': run_id}), patch.object(pipeline, 'ProbeClient') as client:
                client.return_value.probe.return_value = []
                result = self.engine().run_all(stage='probe')
            self.assertEqual(result['stage_results']['probe']['origin_run_id'], expected)
            self.assertEqual(result['summary']['stages_executed'], ['probe'])
            self.assertEqual(result['summary']['stages_recovered'], [])

    def test_summary_keeps_completed_versions_when_later_stage_changes_the_file_and_fails(self):
        def change_then_fail():
            (self.root / 'recon/subdomains.txt').write_text('changed later\n')
            raise pipeline.StageError('fixture')
        with patch.object(pipeline.ReconPipeline, 'run_live_probing', side_effect=change_then_fail):
            result = self.engine().run_all()
        capture = result['summary']['stage_artifacts']['subdomains']
        self.assertEqual(capture['status'], 'recorded')
        self.assertEqual(capture['refs'][0]['sha256'], hashlib.sha256(b'10.0.0.1\n').hexdigest())
        self.assertNotIn('probe', result['summary']['stage_artifacts'])
        (self.root / 'recon/subdomains.txt').write_text('another version\n')
        saved = json.loads((self.root / 'recon/summary.json').read_text())
        self.assertEqual(saved['stage_artifacts']['subdomains'], capture)

    def test_manual_stage_records_versions_and_unavailable_capture_preserves_completion(self):
        self.fail_after_subdomains()
        with patch.object(pipeline, 'ProbeClient') as client:
            client.return_value.probe.return_value = []
            result = self.engine().run_all(stage='probe')
        self.assertEqual(result['summary']['stage_artifacts']['probe']['status'], 'recorded')
        self.assertEqual(len(result['summary']['stage_artifacts']['probe']['refs']), 5)
        with patch.object(pipeline, 'ProbeClient') as client, \
                patch.object(pipeline, 'read_artifact_snapshot', side_effect=ValueError('private-path')):
            client.return_value.probe.return_value = []
            result = self.engine().run_all(stage='probe')
        self.assertEqual(result['summary']['status'], 'completed')
        self.assertEqual(result['summary']['stage_artifacts'], {'probe': {'status': 'unavailable', 'refs': []}})
        self.assertNotIn('private-path', json.dumps(result['summary']))

    def test_resume_retains_checkpoint_artifacts_and_dry_run_records_none(self):
        saved = self.fail_after_subdomains()
        with patch.object(pipeline, 'ProbeClient') as client:
            client.return_value.probe.return_value = []
            result = self.engine().run_all(resume=True)
        self.assertEqual(result['summary']['stage_artifacts']['subdomains']['refs'], saved['artifact_refs']['subdomains'])
        self.assertEqual(set(result['summary']['stage_artifacts']), set(pipeline.STAGE_ARTIFACTS))
        self.assertEqual(sum(len(item['refs']) for item in result['summary']['stage_artifacts'].values()), 17)
        result = self.engine(dry_run=True).run_all()
        self.assertEqual(result['summary']['stage_artifacts'], {})

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
