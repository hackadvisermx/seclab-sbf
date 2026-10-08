import datetime
import importlib.util
import json
import pathlib
import sys
import tempfile
import unittest
from unittest.mock import patch
from authorization_fixture import AUTHORIZATION_FIXTURE, AUTHORIZATION_YAML

SCRIPTS = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
import seclab_scope as scope
import seclab_recon_probe as probe
spec = importlib.util.spec_from_file_location('authorization_pipeline', SCRIPTS / 'pt-recon-pipeline.py')
pipeline = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pipeline)


class AuthorizationTests(unittest.TestCase):
    def data(self):
        return {'scope': {'in_scope': {'domains': ['example.test']}, 'out_of_scope': {}},
                'authorization': dict(AUTHORIZATION_FIXTURE)}

    def test_default_denies_both_kinds_without_blocking_local_or_simulation(self):
        data = self.data()
        data.pop('authorization')
        self.assertEqual(scope.authorization_contract(data), scope.default_authorization())
        for kind in ['passive', 'active']:
            with self.assertRaisesRegex(scope.ScopeError, 'Falta permiso explícito'):
                scope.require_authorization(data, kind)
        for kind in ['local', 'simulation']:
            scope.require_authorization(data, kind)

    def test_permission_kinds_are_independent(self):
        data = self.data()
        data['authorization']['allow_active'] = False
        scope.require_authorization(data, 'passive')
        with self.assertRaisesRegex(scope.ScopeError, 'activa'):
            scope.require_authorization(data, 'active')
        data['authorization']['allow_active'] = True
        data['authorization']['allow_passive'] = False
        scope.require_authorization(data, 'active')
        with self.assertRaisesRegex(scope.ScopeError, 'pasiva'):
            scope.require_authorization(data, 'passive')

    def test_reference_validity_types_timezone_and_unknown_fields_are_validated(self):
        for field, value in [('reference', ''), ('valid_from', ''), ('valid_until', ''),
                             ('valid_from', '2026-01-01T00:00:00'), ('valid_from', '0001-01-01T00:00:00+01:00'), ('valid_until', 'invalid'),
                             ('allow_active', 'false'), ('allow_passive', 1), ('unknown', True)]:
            with self.subTest(field=field, value=value):
                data = self.data()
                data['authorization'][field] = value
                with self.assertRaises(scope.ScopeError):
                    scope.validate_scope(data)
        data = self.data()
        data['authorization']['valid_until'] = data['authorization']['valid_from']
        with self.assertRaisesRegex(scope.ScopeError, 'posterior'):
            scope.validate_scope(data)

    def test_window_start_inclusive_end_exclusive_and_timezone_equivalence(self):
        data = self.data()
        data['authorization'].update(valid_from='2026-10-07T18:00:00-06:00', valid_until='2026-10-08T01:00:00Z')
        for value, allowed in [('2026-10-07T23:59:59+00:00', False), ('2026-10-08T00:00:00+00:00', True),
                               ('2026-10-08T00:59:59+00:00', True), ('2026-10-08T01:00:00+00:00', False)]:
            with self.subTest(value=value):
                now = datetime.datetime.fromisoformat(value)
                if allowed:
                    scope.require_authorization(data, 'active', now)
                else:
                    with self.assertRaisesRegex(scope.ScopeError, 'vigencia'):
                        scope.require_authorization(data, 'active', now)

    def test_yaml_without_pyyaml_preserves_authorization_and_rejects_quoted_booleans(self):
        text = 'scope:\n  in_scope:\n    domains: [example.test]\n' + AUTHORIZATION_YAML
        parsed = scope.parse_simple_yaml_lists(text)
        self.assertEqual(scope.authorization_contract(parsed), AUTHORIZATION_FIXTURE)
        scope.require_authorization(parsed, 'active')
        for invalid in [text.replace('allow_active: true', 'allow_active: "true"'),
                        text.replace('allow_active: true', 'allow_active: true\n  allow_active: false')]:
            with self.assertRaises(scope.ScopeError):
                scope.parse_simple_yaml_lists(invalid)

    def test_no_permission_blocks_pipeline_and_direct_client_before_network(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = pathlib.Path(temporary)
            (root / 'target.yaml').write_text('scope:\n  in_scope:\n    domains: [example.test]\n')
            (root / 'recon').mkdir()
            (root / 'recon/subdomains.txt').write_text('example.test\n')
            with patch.object(pipeline, 'detect_tools', return_value={'subfinder': 'fixture'}):
                engine = pipeline.ReconPipeline(root)
            with patch.object(pipeline.subprocess, 'run') as run, patch.object(pipeline, 'ProbeClient') as client:
                result = engine.run_all('subdomains')
                self.assertEqual(result['summary']['status'], 'failed')
                self.assertIn('pasiva', result['stage_results']['subdomains']['error'])
                result = engine.run_all('probe')
                self.assertIn('activa', result['stage_results']['probe']['error'])
                run.assert_not_called()
                client.assert_not_called()
            with patch.object(probe, 'local_network_addresses', return_value=set()):
                client = probe.ProbeClient(engine.scope_data, engine.limits)
            with patch.object(probe.socket, 'getaddrinfo') as dns:
                with self.assertRaises(scope.ScopeError):
                    client.probe_host('example.test')
                dns.assert_not_called()
            with patch.object(pipeline, 'detect_tools', return_value={}):
                simulation = pipeline.ReconPipeline(root, dry_run=True).run_all('probe')
            self.assertEqual(simulation['summary']['status'], 'simulated')
            self.assertFalse(simulation['summary']['scope_contract']['authorization']['allow_active'])

    def test_expiry_during_rate_limit_wait_blocks_connection(self):
        data = self.data()
        times = iter([datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc),
                      datetime.datetime(2099, 1, 1, tzinfo=datetime.timezone.utc)])
        with patch.object(probe, 'local_network_addresses', return_value=set()):
            client = probe.ProbeClient(data, probe.operational_limits(data))
        with patch.object(probe, 'require_authorization', side_effect=lambda data, kind: scope.require_authorization(data, kind, next(times))), \
             patch.object(probe.socket, 'getaddrinfo', return_value=[(None, None, None, None, ('8.8.8.8', 443))]), \
             patch.object(client.limiter, 'wait'), patch.object(probe, 'PinnedConnection') as connection:
            with self.assertRaisesRegex(scope.ScopeError, 'vigencia'):
                client.probe_host('example.test')
            connection.assert_not_called()


if __name__ == '__main__':
    unittest.main()
