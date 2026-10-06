import importlib.util
import json
import pathlib
import socket
import ssl
import subprocess
import sys
import tempfile
import threading
import time
import unittest
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
    return {'scope': {'in_scope': {'domains': ['example.test', '*.example.test']},
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
        self.root.joinpath('target.yaml').write_text('scope:\n  in_scope:\n    domains: [example.test, "*.example.test"]\n  out_of_scope:\n    domains: [excluded.example.test]\n')
        self.recon = self.root / 'recon'
        self.recon.mkdir()

    def make_pipeline(self, dry_run=False):
        with patch.object(pipeline, 'detect_tools', return_value={}):
            return pipeline.ReconPipeline(self.root, dry_run)

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

    def test_subdomains_new_file_tracks_only_items_absent_from_previous_run(self):
        self.root.joinpath('target.yaml').write_text('scope:\n  in_scope:\n    ips: ["10.0.0.1"]\n')
        result = self.make_pipeline().run_all('subdomains')
        self.assertEqual(result['summary']['subdomains_new_count'], 1)
        self.assertEqual(self.recon.joinpath('subdomains_new.txt').read_text(), '10.0.0.1\n')

        self.root.joinpath('target.yaml').write_text('scope:\n  in_scope:\n    ips: ["10.0.0.1", "10.0.0.2"]\n')
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
