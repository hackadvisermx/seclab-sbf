import importlib.util
import json
import os
import pathlib
import re
import socket
import shlex
import ssl
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from authorization_fixture import AUTHORIZATION_FIXTURE, AUTHORIZATION_YAML
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import Mock, patch

SCRIPTS = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
import seclab_scope as scope
import seclab_recon_probe as probe

spec = importlib.util.spec_from_file_location('recon_safety_pipeline', SCRIPTS / 'pt-recon-pipeline.py')
pipeline = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pipeline)


def rules():
    return {'authorization': dict(AUTHORIZATION_FIXTURE), 'scope': {'in_scope': {'domains': ['example.test', '*.example.test']},
                      'out_of_scope': {'domains': ['excluded.example.test']}}}


class ReconScopeSafetyTests(unittest.TestCase):
    def test_exact_and_wildcard_scope_have_distinct_boundaries(self):
        data = rules()
        data['scope']['in_scope']['domains'] = ['*.example.test']
        for target, expected in [('example.test', 'UNKNOWN'), ('child.example.test', 'IN_SCOPE'),
                                 ('deep.child.example.test', 'IN_SCOPE'), ('excluded.example.test', 'OUT_OF_SCOPE'),
                                 ('example.test.evil.test', 'UNKNOWN'), ('https://user@example.test/', 'UNKNOWN')]:
            self.assertEqual(scope.check_scope(target, data)[0], expected)
        data['scope']['in_scope']['domains'] = ['example.test']
        self.assertEqual(scope.check_scope('child.example.test', data)[0], 'UNKNOWN')
        self.assertEqual(scope.check_scope('https://EXAMPLE.TEST./', data)[0], 'IN_SCOPE')

    def test_cidr_candidate_cannot_authorize_only_its_first_address(self):
        data = rules()
        data['scope']['in_scope']['ips'] = ['8.8.8.8']
        self.assertEqual(scope.check_scope('8.8.8.8/8', data)[0], 'UNKNOWN')
        self.assertEqual(scope.check_scope('::ffff:8.8.8.8', data)[0], 'IN_SCOPE')
        data['scope']['out_of_scope']['cidrs'] = ['::ffff:8.8.8.0/120']
        self.assertEqual(scope.check_scope('8.8.8.8', data)[0], 'OUT_OF_SCOPE')

    def test_endpoint_exclusions_override_domain_and_preserve_path_boundaries(self):
        data = rules()
        data['scope']['out_of_scope']['endpoints'] = ['https://example.test/private']
        self.assertEqual(scope.check_scope('https://example.test/private/login', data)[0], 'OUT_OF_SCOPE')
        self.assertEqual(scope.check_scope('https://example.test/privateish', data)[0], 'IN_SCOPE')
        self.assertEqual(scope.check_scope('http://example.test/private', data)[0], 'IN_SCOPE')

    def test_malformed_duplicate_and_misspelled_exclusions_fail_closed(self):
        contents = ['scope: [broken', 'scope:\n  in_scope:\n    domains: [example.test]\n    domains: [evil.test]\n',
                    'scope:\n  in_scope:\n    domains: [example.test]\n  out_of_scope:\n    domans: [example.test]\n',
                    'scope:\n  in_scope:\n    domains: [example.test]\nscope:\n  in_scope:\n    domains: [evil.test]\n']
        with tempfile.TemporaryDirectory() as folder:
            path = pathlib.Path(folder) / 'target.yaml'
            for content in contents:
                path.write_text(content)
                with self.subTest(content=content), self.assertRaises(scope.ScopeError):
                    scope.load_target_yaml(path)
                with self.assertRaises(scope.ScopeError):
                    scope.parse_simple_yaml_lists(content)

    def test_invalid_operational_limits_are_not_silently_defaulted(self):
        for key, value in [('max_requests_per_second', 0), ('max_requests_per_second', 'nan'),
                           ('max_parallel_threads', 1.5), ('max_parallel_threads', True),
                           ('max_probe_targets', 10001), ('probe_timeout_seconds', None)]:
            data = rules()
            data['operational_limits'] = {key: value}
            with self.subTest(key=key, value=value), self.assertRaises(scope.ScopeError):
                probe.operational_limits(data)

    def test_stdlib_parser_accepts_seed_template_without_ignoring_limits(self):
        data = scope.parse_simple_yaml_lists((SCRIPTS.parent / 'workspace-seed/templates/target.yaml').read_text())
        self.assertEqual(probe.operational_limits(data)['max_requests_per_second'], 1)
        self.assertEqual(scope.check_scope('payments.example.com', data)[0], 'OUT_OF_SCOPE')

    def test_protected_and_explicitly_excluded_dns_addresses_are_blocked(self):
        data = rules()
        data['scope']['in_scope']['cidrs'] = ['0.0.0.0/0', '::/0']
        data['scope']['out_of_scope']['ips'] = ['8.8.4.4']
        for address in ['127.0.0.1', '::1', '169.254.169.254', '168.63.129.16', '100.100.100.100',
                        'fd7a:115c:a1e0::1', 'fd00:ec2::254', 'fd20:ce::254', '224.0.0.1', '0.0.0.0', '8.8.4.4', '172.18.0.1']:
            with self.subTest(address=address):
                self.assertFalse(probe.destination_permitted(address, data, {'172.18.0.1'}))
        self.assertTrue(probe.destination_permitted('8.8.8.8', data, set()))

    def test_private_dns_requires_explicit_network_authorization(self):
        data = rules()
        self.assertFalse(probe.destination_permitted('10.20.30.40', data, set()))
        data['scope']['in_scope']['cidrs'] = ['10.20.30.0/24']
        self.assertTrue(probe.destination_permitted('10.20.30.40', data, set()))
        self.assertFalse(probe.destination_permitted('10.20.30.40', data, {'10.20.30.40'}))


class ReconPipelineSafetyTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = pathlib.Path(self.temporary.name)
        self.root.joinpath('target.yaml').write_text('scope:\n  in_scope:\n    domains: [example.test, "*.example.test"]\n  out_of_scope:\n    domains: [excluded.example.test]\n' + AUTHORIZATION_YAML)
        self.recon = self.root / 'recon'
        self.recon.mkdir()

    def make_pipeline(self, dry_run=False):
        with patch.object(pipeline, 'detect_tools', return_value={}):
            return pipeline.ReconPipeline(self.root, dry_run)

    def test_preview_is_read_only_and_never_opens_network_or_runs_tools(self):
        self.recon.joinpath('subdomains.txt').write_text('example.test\nexcluded.example.test\nevil.test\n')
        self.recon.joinpath('urls_all.txt').write_text('https://example.test/profile?id=1\nhttps://excluded.example.test/a\nhttps://excluded.example.test/b\n')
        before = {str(path): path.read_bytes() for path in self.root.rglob('*') if path.is_file()}
        instance = self.make_pipeline()
        with patch.object(socket, 'socket', side_effect=AssertionError('network')), patch.object(socket, 'getaddrinfo', side_effect=AssertionError('DNS')), patch.object(pipeline.subprocess, 'run', side_effect=AssertionError('tool')):
            result = instance.preview('probe')
            local = instance.preview('patterns', True)
        self.assertEqual(local['stages'][0]['targets'], ['https://example.test/profile?id=1'])
        self.assertEqual(local['stages'][0]['discarded_count'], 2)
        self.assertTrue(result['can_start'])
        self.assertEqual(result['stages'][0]['targets'], ['example.test'])
        self.assertEqual(result['stages'][0]['discarded_count'], 2)
        self.assertEqual(before, {str(path): path.read_bytes() for path in self.root.rglob('*') if path.is_file()})

    def test_preview_permissions_simulation_pending_targets_and_bounded_lists(self):
        config = self.root / 'target.yaml'
        config.write_text(config.read_text().replace('allow_active: true', 'allow_active: false'))
        self.recon.joinpath('subdomains.txt').write_text(''.join(f'host{number}.example.test\n' for number in range(70)))
        result = self.make_pipeline().preview('probe')
        self.assertFalse(result['can_start'])
        self.assertFalse(result['authorization']['allow_active'])
        self.assertTrue(result['authorization']['reference_present'])
        self.assertNotIn('reference', result['authorization'])
        self.assertEqual(result['stages'][0]['targets_count'], 70)
        self.assertEqual(len(result['stages'][0]['targets']), 50)
        self.assertTrue(self.make_pipeline().preview('probe', True)['can_start'])
        complete = self.make_pipeline().preview('all')
        self.assertTrue(complete['stages'][1]['targets_pending'])
        self.assertTrue(complete['stages'][3]['targets_pending'])

    def test_preview_revision_changes_with_scope_or_input_and_cli_rejects_stale_plan(self):
        self.recon.joinpath('subdomains.txt').write_text('example.test\n')
        original = self.make_pipeline().preview('probe', True)
        self.assertEqual(original['plan_revision'], self.make_pipeline().preview('probe', True)['plan_revision'])
        with tempfile.TemporaryDirectory() as other:
            clone = pathlib.Path(other)
            (clone / 'recon').mkdir()
            (clone / 'target.yaml').write_bytes((self.root / 'target.yaml').read_bytes())
            (clone / 'recon/subdomains.txt').write_text('example.test\n')
            self.assertNotEqual(original['plan_revision'], pipeline.ReconPipeline(clone, True).preview('probe', True)['plan_revision'])
        self.recon.joinpath('subdomains.txt').write_text('child.example.test\n')
        changed = self.make_pipeline().preview('probe', True)
        self.assertNotEqual(original['plan_revision'], changed['plan_revision'])
        result = subprocess.run([sys.executable, str(SCRIPTS / 'pt-recon-pipeline.py'), 'run', str(self.root), '--stage', 'probe', '--dry-run', '--expected-plan', original['plan_revision']], capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        self.assertIn('plan revisado cambió', result.stderr)
        self.assertFalse((self.recon / 'summary.json').exists())
        config = self.root / 'target.yaml'
        config.write_text(config.read_text().replace('allow_active: true', 'allow_active: false'))
        self.assertNotEqual(changed['plan_revision'], self.make_pipeline().preview('probe', True)['plan_revision'])

    def test_local_pattern_classification_does_not_require_passive_permission(self):
        config = self.root / 'target.yaml'
        config.write_text(config.read_text().replace('allow_passive: true', 'allow_passive: false'))
        self.recon.joinpath('urls_all.txt').write_text('https://example.test/profile?id=1\n')
        instance = self.make_pipeline()
        instance.tools['gf'] = 'fixture-gf'
        with patch.object(pipeline.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, '', '')):
            result = instance.run_all('patterns')
        self.assertEqual(result['summary']['status'], 'completed', result['summary'].get('error'))

    def test_scope_filter_runs_before_probe_constructor_or_dns(self):
        self.recon.joinpath('subdomains.txt').write_text('example.test\nexcluded.example.test\nevil.test\nhttps://user@example.test\n')
        with patch.object(pipeline, 'ProbeClient') as client:
            client.return_value.probe.return_value = []
            result = self.make_pipeline().run_all('probe')
            client.return_value.probe.assert_called_once_with(['example.test'])
        self.assertEqual(result['summary']['live_hosts_count'], 0)
        self.assertEqual(result['stage_results']['probe']['discarded_count'], 3)

    def test_target_cap_is_checked_before_any_network_setup(self):
        self.recon.joinpath('subdomains.txt').write_text('one.example.test\ntwo.example.test\n')
        engine = self.make_pipeline()
        engine.limits['max_probe_targets'] = 1
        for dry_run in (False, True):
            engine.dry_run = dry_run
            with patch.object(pipeline, 'ProbeClient') as client:
                result = engine.run_all('probe')
                client.assert_not_called()
            self.assertEqual(result['summary']['status'], 'failed')

    def test_missing_enumerator_stops_full_flow_and_preserves_prior_artifacts(self):
        previous = self.recon / 'live_hosts.txt'
        previous.write_text('https://previous.example.test\n')
        engine = self.make_pipeline()
        with patch.object(engine, 'run_live_probing') as active:
            result = engine.run_all()
            active.assert_not_called()
        self.assertEqual(result['summary']['status'], 'failed')
        self.assertEqual(result['summary']['metrics_source'], 'previous_artifacts')
        self.assertEqual(previous.read_text(), 'https://previous.example.test\n')
        self.assertFalse(self.recon.joinpath('subdomains.txt').exists())

    def test_live_tool_publishes_output_before_exit_and_preserves_artifacts_on_failure(self):
        tool = self.root / 'slow-tool'
        tool.write_text(f'#!{sys.executable}\nimport time\nprint("candidate.example.test", flush=True)\ntime.sleep(1)\nraise SystemExit(2)\n')
        tool.chmod(0o755)
        self.recon.joinpath('subdomains.txt').write_text('previous.example.test\n')
        engine = self.make_pipeline()
        engine.live = True
        engine.tools = {'subfinder': str(tool)}
        errors = []
        def execute():
            try:
                engine._tool('subfinder', [])
            except pipeline.StageError as error:
                errors.append(str(error))
        worker = threading.Thread(target=execute)
        worker.start()
        self.addCleanup(worker.join)
        deadline = time.monotonic() + 3
        progress = {}
        while time.monotonic() < deadline:
            path = self.recon / 'progress.json'
            if path.exists():
                progress = json.loads(path.read_text())
                if 'candidate.example.test' in progress['recent_output']:
                    break
            time.sleep(.01)
        self.assertTrue(worker.is_alive(), 'output must be visible while the tool is still running')
        self.assertEqual(progress['command_status'], 'running')
        self.assertIn('candidate.example.test', progress['recent_output'])
        worker.join(3)
        self.assertTrue(errors)
        self.assertEqual(json.loads((self.recon / 'progress.json').read_text())['command_status'], 'failed')
        self.assertEqual(self.recon.joinpath('subdomains.txt').read_text(), 'previous.example.test\n')

    def test_live_tool_timeout_kills_child_and_bounds_output_history(self):
        tool = self.root / 'timeout-tool'
        tool.write_text(f'#!{sys.executable}\nimport os,time\nprint(os.getpid(), flush=True)\ntime.sleep(10)\n')
        tool.chmod(0o755)
        engine = self.make_pipeline()
        engine.live = True
        engine.tools = {'subfinder': str(tool)}
        with self.assertRaises(pipeline.StageError):
            engine._tool('subfinder', [], timeout=1.5)
        data = json.loads((self.recon / 'progress.json').read_text())
        pid = int(data['recent_output'][0])
        with self.assertRaises(ProcessLookupError):
            os.kill(pid, 0)
        engine._emit('output', output='\n'.join(str(n) for n in range(100)))
        self.assertEqual(len(json.loads((self.recon / 'progress.json').read_text())['recent_output']), 80)

    def test_probe_live_callback_reports_fast_host_before_slow_one_without_reordering_results(self):
        client = probe.ProbeClient(rules(), probe.operational_limits(rules()))
        client.limits['max_parallel_threads'] = 2
        def result(host):
            if host == 'slow':
                time.sleep(.2)
            return [{'host': host, 'status': 'response'}]
        reported = []
        with patch.object(client, 'probe_host', side_effect=result):
            rows = client.probe(['slow', 'fast'], on_result=lambda rows: reported.append(rows[0]['host']))
        self.assertEqual(reported, ['fast', 'slow'])
        self.assertEqual([row['host'] for row in rows], ['slow', 'fast'])

    def test_tool_failure_or_timeout_discards_partial_stdout(self):
        self.recon.joinpath('subdomains.txt').write_text('previous.example.test\n')
        for outcome in [subprocess.CompletedProcess([], 2, 'invented.example.test\n', 'error'),
                        subprocess.TimeoutExpired('subfinder', 180, output='invented.example.test\n')]:
            engine = self.make_pipeline()
            engine.tools = {'subfinder': '/fixture/subfinder'}
            with patch.object(pipeline.subprocess, 'run', **({'side_effect': outcome} if isinstance(outcome, Exception) else {'return_value': outcome})):
                result = engine.run_all('subdomains')
            self.assertEqual(result['summary']['status'], 'failed')
            self.assertEqual(self.recon.joinpath('subdomains.txt').read_text(), 'previous.example.test\n')

    def test_subfinder_missing_provider_config_reports_action_without_partial_results(self):
        self.recon.joinpath('subdomains.txt').write_text('previous.example.test\n')
        engine = self.make_pipeline()
        engine.tools = {'subfinder': '/fixture/subfinder'}
        failure = subprocess.CompletedProcess([], 1, 'invented.example.test\n', 'Could not create provider config file: read-only file system')
        with patch.object(pipeline.subprocess, 'run', return_value=failure):
            result = engine.run_all('subdomains')
        error = result['stage_results']['subdomains']['error']
        self.assertIn('provider-config.yaml', error)
        self.assertIn('reconstruye la imagen', error)
        self.assertEqual(self.recon.joinpath('subdomains.txt').read_text(), 'previous.example.test\n')
        self.assertEqual(result['summary']['status'], 'failed')

    def test_subdomains_new_file_tracks_only_items_absent_from_previous_run(self):
        self.root.joinpath('target.yaml').write_text('scope:\n  in_scope:\n    ips: ["10.0.0.1"]\n' + AUTHORIZATION_YAML)
        result = self.make_pipeline().run_all('subdomains')
        self.assertEqual(result['summary']['subdomains_new_count'], 1)
        self.assertEqual(self.recon.joinpath('subdomains_new.txt').read_text(), '10.0.0.1\n')

        self.root.joinpath('target.yaml').write_text('scope:\n  in_scope:\n    ips: ["10.0.0.1", "10.0.0.2"]\n' + AUTHORIZATION_YAML)
        result = self.make_pipeline().run_all('subdomains')
        self.assertEqual(result['summary']['subdomains_new_count'], 1)
        self.assertEqual(self.recon.joinpath('subdomains_new.txt').read_text(), '10.0.0.2\n')

        result = self.make_pipeline().run_all('subdomains')
        self.assertEqual(result['summary']['subdomains_new_count'], 0)
        self.assertEqual(self.recon.joinpath('subdomains_new.txt').read_text(), '')

    def test_live_hosts_new_file_tracks_newly_responsive_hosts_across_runs(self):
        self.recon.joinpath('subdomains.txt').write_text('a.example.test\nb.example.test\n')
        with patch.object(pipeline, 'ProbeClient') as client:
            client.return_value.probe.return_value = [
                {'url': 'https://a.example.test', 'status': 'response', 'target': 'a.example.test'},
            ]
            result = self.make_pipeline().run_all('probe')
        self.assertEqual(result['summary']['live_hosts_new_count'], 1)
        self.assertEqual(self.recon.joinpath('live_hosts_new.txt').read_text(), 'https://a.example.test\n')

        with patch.object(pipeline, 'ProbeClient') as client:
            client.return_value.probe.return_value = [
                {'url': 'https://a.example.test', 'status': 'response', 'target': 'a.example.test'},
                {'url': 'https://b.example.test', 'status': 'response', 'target': 'b.example.test'},
            ]
            result = self.make_pipeline().run_all('probe')
        self.assertEqual(result['summary']['live_hosts_new_count'], 1)
        self.assertEqual(self.recon.joinpath('live_hosts_new.txt').read_text(), 'https://b.example.test\n')

        with patch.object(pipeline, 'ProbeClient') as client:
            client.return_value.probe.return_value = [
                {'url': 'https://a.example.test', 'status': 'response', 'target': 'a.example.test'},
                {'url': 'https://b.example.test', 'status': 'response', 'target': 'b.example.test'},
            ]
            result = self.make_pipeline().run_all('probe')
        self.assertEqual(result['summary']['live_hosts_new_count'], 0)
        self.assertEqual(self.recon.joinpath('live_hosts_new.txt').read_text(), '')

    def test_resume_skips_completed_stages_and_retries_only_the_failed_one(self):
        self.root.joinpath('target.yaml').write_text('scope:\n  in_scope:\n    ips: ["10.0.0.1"]\n' + AUTHORIZATION_YAML)
        engine = self.make_pipeline()
        with patch.object(pipeline, 'ProbeClient') as client:
            client.return_value.probe.side_effect = OSError('fallo simulado de red')
            result = engine.run_all('all')
        self.assertEqual(result['summary']['status'], 'failed')
        self.assertEqual(result['summary']['resumable_from'], 'probe')
        self.assertEqual(result['stage_results']['subdomains']['status'], 'completed')
        checkpoint = json.loads(self.recon.joinpath('.checkpoint.json').read_text())
        self.assertEqual(checkpoint['failed_stage'], 'probe')
        self.assertIn('subdomains', checkpoint['completed'])

        engine2 = self.make_pipeline()
        with patch.object(pipeline.ReconPipeline, 'run_subdomain_enumeration') as subdomains_action, \
             patch.object(pipeline, 'ProbeClient') as client2:
            client2.return_value.probe.return_value = [{'url': 'https://10.0.0.1', 'status': 'response', 'target': '10.0.0.1'}]
            result2 = engine2.run_all('all', resume=True)
        subdomains_action.assert_not_called()
        self.assertEqual(result2['summary']['status'], 'completed')
        self.assertIsNone(result2['summary']['resumable_from'])
        self.assertEqual(result2['stage_results']['subdomains']['subdomains'], ['10.0.0.1'])
        self.assertFalse(self.recon.joinpath('.checkpoint.json').exists())

    def test_resume_without_a_checkpoint_behaves_like_a_fresh_run(self):
        self.root.joinpath('target.yaml').write_text('scope:\n  in_scope:\n    ips: ["10.0.0.1"]\n' + AUTHORIZATION_YAML)
        result = self.make_pipeline().run_all('all', resume=True)
        self.assertEqual(result['summary']['status'], 'completed')
        self.assertEqual(result['stage_results']['subdomains']['subdomains'], ['10.0.0.1'])

    def test_manual_single_stage_run_invalidates_the_checkpoint(self):
        self.root.joinpath('target.yaml').write_text('scope:\n  in_scope:\n    ips: ["10.0.0.1"]\n' + AUTHORIZATION_YAML)
        engine = self.make_pipeline()
        with patch.object(pipeline, 'ProbeClient') as client:
            client.return_value.probe.side_effect = OSError('fallo simulado')
            engine.run_all('all')
        self.assertTrue(self.recon.joinpath('.checkpoint.json').is_file())

        engine2 = self.make_pipeline()
        with patch.object(pipeline, 'ProbeClient') as client2:
            client2.return_value.probe.return_value = []
            engine2.run_all('probe')
        self.assertFalse(self.recon.joinpath('.checkpoint.json').exists())

    def test_resume_flag_requires_the_default_stage(self):
        result = subprocess.run([sys.executable, str(SCRIPTS / 'pt-recon-pipeline.py'), 'run', str(self.root), '--stage', 'probe', '--resume'], capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        self.assertIn('--resume', result.stderr)

    def test_generate_next_commands_suggests_pt_nmp_and_pt_fuzz_params_per_host(self):
        engine = self.make_pipeline()
        lines = engine.generate_next_commands(['https://a.example.test', 'http://b.example.test'])
        self.assertEqual(lines, [
            '# https://a.example.test',
            'pt-nmp a.example.test',
            'pt-fuzz-params "https://a.example.test"',
            '',
            '# http://b.example.test',
            'pt-nmp b.example.test',
            'pt-fuzz-params "http://b.example.test"',
        ])

    def test_generate_next_commands_strips_ipv6_brackets_for_pt_nmp_but_not_the_url(self):
        engine = self.make_pipeline()
        lines = engine.generate_next_commands(['https://[::1]'])
        self.assertIn('pt-nmp ::1', lines)
        self.assertIn('pt-fuzz-params "https://[::1]"', lines)

    def test_probe_stage_writes_next_commands_file_for_live_hosts(self):
        self.recon.joinpath('subdomains.txt').write_text('a.example.test\n')
        engine = self.make_pipeline()
        with patch.object(pipeline, 'ProbeClient') as client:
            client.return_value.probe.return_value = [{'url': 'https://a.example.test', 'status': 'response', 'target': 'a.example.test'}]
            result = engine.run_all('probe')
        self.assertEqual(result['stage_results']['probe']['next_commands_count'], 1)
        content = self.recon.joinpath('next_commands.txt').read_text()
        self.assertIn('pt-nmp a.example.test', content)
        self.assertIn('pt-fuzz-params "https://a.example.test"', content)

    def test_probe_stage_without_live_hosts_writes_empty_next_commands_file(self):
        self.recon.joinpath('subdomains.txt').write_text('a.example.test\n')
        engine = self.make_pipeline()
        with patch.object(pipeline, 'ProbeClient') as client:
            client.return_value.probe.return_value = [{'url': 'https://a.example.test', 'status': 'connection_error', 'target': 'a.example.test'}]
            engine.run_all('probe')
        self.assertEqual(self.recon.joinpath('next_commands.txt').read_text(), '')

    def test_run_all_sends_notification_with_status_on_success_and_failure(self):
        self.root.joinpath('target.yaml').write_text('scope:\n  in_scope:\n    ips: ["10.0.0.1"]\n' + AUTHORIZATION_YAML)
        with patch.object(pipeline, 'send_notification') as notify:
            self.make_pipeline().run_all('subdomains')
            notify.assert_called_once()
            self.assertIn('completed', notify.call_args[0][0])
            self.assertEqual(notify.call_args.kwargs['level'], 'info')

            notify.reset_mock()
            self.recon.joinpath('subdomains.txt').write_text('10.0.0.1\n')
            engine = self.make_pipeline()
            with patch.object(pipeline, 'ProbeClient') as client:
                client.return_value.probe.side_effect = OSError('fallo simulado')
                engine.run_all('probe')
            notify.assert_called_once()
            self.assertIn('failed', notify.call_args[0][0])
            self.assertEqual(notify.call_args.kwargs['level'], 'error')

    def test_run_all_does_not_send_notification_during_dry_run(self):
        self.root.joinpath('target.yaml').write_text('scope:\n  in_scope:\n    ips: ["10.0.0.1"]\n' + AUTHORIZATION_YAML)
        with patch.object(pipeline, 'send_notification') as notify:
            self.make_pipeline(dry_run=True).run_all('all')
        notify.assert_not_called()

    def test_dry_run_does_not_modify_files_or_invent_results(self):
        self.recon.joinpath('subdomains.txt').write_text('example.test\nevil.test\n')
        self.root.joinpath('terminal.log').write_text('unchanged')
        before = {str(path.relative_to(self.root)): path.read_bytes() for path in self.root.rglob('*') if path.is_file()}
        with patch.object(pipeline.subprocess, 'run', side_effect=AssertionError('Dry run cannot execute tools')), \
             patch.object(pipeline, 'ProbeClient', side_effect=AssertionError('Dry run cannot probe')):
            result = self.make_pipeline(True).run_all()
        after = {str(path.relative_to(self.root)): path.read_bytes() for path in self.root.rglob('*') if path.is_file()}
        self.assertEqual(before, after)
        self.assertEqual(result['summary']['status'], 'simulated')
        self.assertEqual(result['summary']['live_hosts_count'], 0)
        self.assertNotIn('subdomains', result['stage_results']['subdomains'])

    def test_retry_command_uses_checkpoint_or_selected_stage_and_quotes_project_path(self):
        summary = {'resumable_from': 'subdomains'}
        self.assertEqual(shlex.split(pipeline.retry_command(self.root, summary)), ['pt-recon', str(self.root), '--stage', 'subdomains'])
        self.recon.joinpath('.checkpoint.json').write_text('{}')
        self.assertEqual(shlex.split(pipeline.retry_command(self.root, summary)), ['pt-recon', str(self.root), '--resume'])
        other = self.root / 'path with spaces'
        self.assertEqual(shlex.split(pipeline.retry_command(other, summary)), ['pt-recon', str(other), '--stage', 'subdomains'])

    def test_cli_failure_is_nonzero_and_status_is_read_only(self):
        result = subprocess.run([sys.executable, str(SCRIPTS / 'pt-recon-pipeline.py'), 'run', str(self.root), '--stage', 'probe', '--json'], capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(json.loads(result.stdout)['summary']['status'], 'failed')
        before = self.recon.joinpath('summary.json').read_bytes()
        status = subprocess.run([sys.executable, str(SCRIPTS / 'pt-recon-pipeline.py'), 'status', str(self.root), '--json'], capture_output=True, text=True)
        self.assertEqual(status.returncode, 0)
        self.assertEqual(self.recon.joinpath('summary.json').read_bytes(), before)

    def test_filter_uses_the_requested_file_not_other_target_in_same_folder(self):
        other = self.root / 'custom.yaml'
        other.write_text('scope:\n  in_scope:\n    domains: [other.test]\n')
        source = self.root / 'input.txt'
        source.write_text('example.test\nother.test\n')
        result = subprocess.run([sys.executable, str(SCRIPTS / 'pt-recon-pipeline.py'), 'filter', str(source), str(other)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, 'other.test\n')


class ReconNotificationTests(unittest.TestCase):
    def test_no_webhook_configured_never_calls_urlopen(self):
        env = {k: v for k, v in os.environ.items() if k != 'SECLAB_NOTIFY_WEBHOOK'}
        with patch.dict(os.environ, env, clear=True), patch.object(pipeline.urllib.request, 'urlopen') as urlopen:
            pipeline.send_notification('titulo', 'mensaje')
        urlopen.assert_not_called()

    def test_webhook_configured_posts_json_payload_with_title_message_and_level(self):
        with patch.dict(os.environ, {'SECLAB_NOTIFY_WEBHOOK': 'http://notify.example.test/hook'}):
            with patch.object(pipeline.urllib.request, 'urlopen') as urlopen:
                urlopen.return_value.close = Mock()
                pipeline.send_notification('Reconocimiento completed: demo', 'Subdominios: 3', level='info')
            urlopen.assert_called_once()
            request = urlopen.call_args[0][0]
            self.assertEqual(request.full_url, 'http://notify.example.test/hook')
            self.assertEqual(request.get_header('Content-type'), 'application/json')
            body = json.loads(request.data.decode('utf-8'))
            self.assertIn('Reconocimiento completed: demo', body['text'])
            self.assertIn('Subdominios: 3', body['text'])
            self.assertIn('[info]', body['text'])

    def test_network_failure_during_notification_is_swallowed(self):
        with patch.dict(os.environ, {'SECLAB_NOTIFY_WEBHOOK': 'http://notify.example.test/hook'}):
            with patch.object(pipeline.urllib.request, 'urlopen', side_effect=OSError('inalcanzable')):
                pipeline.send_notification('titulo', 'mensaje')  # no debe propagar la excepción


class ReconOOBCallbackNotificationTests(unittest.TestCase):
    """Ejecuta de verdad el servidor HTTP embebido de pt-callback (extraido del
    plugin zsh) para probar la notificacion webhook opcional end-to-end, no solo
    que el texto exista en el archivo."""

    def extract_callback_server_script(self):
        plugin_path = SCRIPTS.parent / 'shell' / 'pentest-lab' / 'pentest-lab.plugin.zsh'
        content = plugin_path.read_text(encoding='utf-8')
        match = re.search(r'python3 -c "\n(.*?)\n" "\$port" "\$log_file"', content, re.DOTALL)
        self.assertIsNotNone(match, 'No se encontro el script embebido de pt-callback en el plugin zsh')
        return match.group(1)

    def free_port(self):
        probe_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        probe_socket.bind(('127.0.0.1', 0))
        port = probe_socket.getsockname()[1]
        probe_socket.close()
        return port

    def start_callback_server(self, tmp_dir, env):
        script_path = pathlib.Path(tmp_dir) / 'callback_server.py'
        script_path.write_text(self.extract_callback_server_script(), encoding='utf-8')
        log_path = pathlib.Path(tmp_dir) / 'callback.log'
        port = self.free_port()
        proc = subprocess.Popen([sys.executable, str(script_path), str(port), str(log_path)], env=env)
        self.addCleanup(lambda: (proc.terminate(), proc.wait(timeout=5)))
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            try:
                with socket.create_connection(('127.0.0.1', port), timeout=0.2):
                    break
            except OSError:
                time.sleep(0.05)
        else:
            self.fail('El receptor de callbacks no abrio el puerto a tiempo')
        return port, log_path

    def start_fake_webhook(self):
        received = []
        class WebhookHandler(BaseHTTPRequestHandler):
            def do_POST(self):
                length = int(self.headers.get('Content-Length', 0))
                received.append(json.loads(self.rfile.read(length).decode('utf-8')))
                self.send_response(200)
                self.end_headers()
            def log_message(self, *_args):
                pass
        server = ThreadingHTTPServer(('127.0.0.1', 0), WebhookHandler)
        server.daemon_threads = True
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.shutdown)
        self.addCleanup(server.server_close)
        return server, received

    def test_oob_callback_posts_webhook_notification_when_configured(self):
        webhook_server, received = self.start_fake_webhook()
        with tempfile.TemporaryDirectory() as tmp_dir:
            env = dict(os.environ)
            env['SECLAB_NOTIFY_WEBHOOK'] = f'http://127.0.0.1:{webhook_server.server_port}/hook'
            port, log_path = self.start_callback_server(tmp_dir, env)
            urllib.request.urlopen(f'http://127.0.0.1:{port}/ssrf-test', timeout=5).read()

            deadline = time.monotonic() + 5
            while not received and time.monotonic() < deadline:
                time.sleep(0.05)

            self.assertEqual(len(received), 1)
            self.assertIn('Callback OOB recibido', received[0]['text'])
            self.assertIn('GET /ssrf-test', received[0]['text'])
            self.assertIn('127.0.0.1', received[0]['text'])
            self.assertIn('GET /ssrf-test', log_path.read_text(encoding='utf-8'))

    def test_oob_callback_without_webhook_configured_never_calls_out(self):
        webhook_server, received = self.start_fake_webhook()
        with tempfile.TemporaryDirectory() as tmp_dir:
            env = dict(os.environ)
            env.pop('SECLAB_NOTIFY_WEBHOOK', None)
            port, log_path = self.start_callback_server(tmp_dir, env)
            urllib.request.urlopen(f'http://127.0.0.1:{port}/ssrf-test', timeout=5).read()

            time.sleep(1)
            self.assertEqual(received, [])
            self.assertIn('GET /ssrf-test', log_path.read_text(encoding='utf-8'))


class ReconProbeSafetyTests(unittest.TestCase):
    def client(self):
        with patch.object(probe, 'local_network_addresses', return_value=set()):
            return probe.ProbeClient(rules(), probe.operational_limits(rules()))

    def test_scope_denial_does_not_resolve_dns_or_connect(self):
        client = self.client()
        with patch.object(probe.socket, 'getaddrinfo') as dns, patch.object(probe, 'PinnedConnection') as connection:
            self.assertEqual(client.probe_host('evil.test')[0]['status'], 'blocked')
            dns.assert_not_called()
            connection.assert_not_called()

    def test_mixed_public_and_private_dns_blocks_entire_host(self):
        client = self.client()
        records = [(socket.AF_INET, socket.SOCK_STREAM, 6, '', (address, 443)) for address in ('8.8.8.8', '10.0.0.1')]
        with patch.object(probe.socket, 'getaddrinfo', return_value=records), patch.object(probe, 'PinnedConnection') as connection:
            self.assertEqual(client.probe_host('example.test')[0]['status'], 'blocked')
            connection.assert_not_called()

    def test_tls_failure_does_not_become_an_https_service(self):
        client = self.client()
        records = [(socket.AF_INET, socket.SOCK_STREAM, 6, '', ('8.8.8.8', 443))]
        connection = Mock()
        connection.request.side_effect = ssl.SSLCertVerificationError('Untrusted fixture')
        client.limiter = Mock()
        with patch.object(probe.socket, 'getaddrinfo', return_value=records), patch.object(probe, 'PinnedConnection', return_value=connection):
            rows = client.probe_host('example.test')
        self.assertEqual(rows[0]['status'], 'tls_untrusted')
        self.assertFalse(any(row['status'] == 'response' for row in rows))

    def test_global_rate_limiter_spaces_attempts_without_initial_burst(self):
        now = [10.0]
        def advance(seconds):
            now[0] += seconds
        limiter = probe.RateLimiter(2, lambda: now[0], advance)
        starts = []
        for _ in range(5):
            limiter.wait()
            starts.append(now[0])
        self.assertEqual(starts, [10, 10.5, 11, 11.5, 12])

    def test_parallelism_limit_is_enforced(self):
        client = self.client()
        client.limits['max_parallel_threads'] = 2
        active = maximum = 0
        lock = threading.Lock()
        def observe(host):
            nonlocal active, maximum
            with lock:
                active += 1
                maximum = max(maximum, active)
            time.sleep(0.02)
            with lock:
                active -= 1
            return []
        with patch.object(client, 'probe_host', side_effect=observe):
            client.probe(['fixture'] * 8)
        self.assertEqual(maximum, 2)

    def test_expired_connection_cannot_start_later(self):
        connection = probe.PinnedConnection('example.test', '8.8.8.8', 80, 1)
        connection.expire()
        with patch.object(probe.socket, 'socket') as factory, self.assertRaises(TimeoutError):
            connection.connect()
        factory.return_value.connect.assert_not_called()
        connection.close()

    def test_total_deadline_stops_slow_headers(self):
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                try:
                    for byte in b'HTTP/1.1 200 OK\r\n\r\n':
                        self.connection.sendall(bytes([byte]))
                        time.sleep(0.15)
                except OSError:
                    pass
            def log_message(self, *_args):
                pass
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        server.daemon_threads = True
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        connection = probe.PinnedConnection('example.test', '127.0.0.1', server.server_port, 1)
        timer = threading.Timer(1, connection.expire)
        started = time.monotonic()
        timer.start()
        try:
            connection.request('GET', '/')
            with self.assertRaises((OSError, probe.http.client.HTTPException)):
                connection.getresponse()
            self.assertLess(time.monotonic() - started, 1.8)
            self.assertTrue(connection.expired.is_set())
        finally:
            timer.cancel()
            connection.close()
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

    def test_real_transport_pins_ip_and_records_redirect_without_following(self):
        observed = []
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                observed.append((self.path, self.headers['Host']))
                self.send_response(302)
                self.send_header('Location', 'https://outside.test/private')
                self.end_headers()
            def log_message(self, *_args):
                pass
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        server.daemon_threads = True
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        real_socket = socket.socket
        connects = []
        class FixtureSocket(real_socket):
            def connect(self, address):
                connects.append(address)
                return super().connect(('127.0.0.1', server.server_port))
        client = self.client()
        client.limiter = Mock()
        records = [(socket.AF_INET, socket.SOCK_STREAM, 6, '', ('8.8.8.8', 443))]
        try:
            with patch.object(probe.socket, 'getaddrinfo', return_value=records) as dns, patch.object(probe.socket, 'socket', FixtureSocket):
                rows = client.probe_host('example.test')
                dns.assert_called_once()
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)
        self.assertEqual(connects, [('8.8.8.8', 443), ('8.8.8.8', 80)])
        self.assertEqual(observed, [('/', 'example.test')])
        response = next(row for row in rows if row['status'] == 'response')
        self.assertEqual(response['location'], 'https://outside.test/private')
        self.assertFalse(response['redirect_followed'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
