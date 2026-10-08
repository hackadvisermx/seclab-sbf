import hashlib
import importlib.util
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest
from authorization_fixture import AUTHORIZATION_FIXTURE, AUTHORIZATION_YAML
from unittest.mock import Mock, patch

SCRIPTS = pathlib.Path(os.environ.get('SCOPE_REVISION_SCRIPTS', pathlib.Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(SCRIPTS))


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


pipeline = load('revision_pipeline', 'pt-recon-pipeline.py')
probe = load('revision_probe', 'seclab_recon_probe.py')


class ScopeRevisionTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = pathlib.Path(temporary.name)
        self.scope = self.root / 'target.yaml'
        self.scope.write_text('scope:\n  in_scope:\n    domains: [example.test]\n  out_of_scope:\n    domains: []\n' + AUTHORIZATION_YAML)
        (self.root / 'recon').mkdir()
        (self.root / 'recon/subdomains.txt').write_text('example.test\n')
        with patch.object(pipeline, 'detect_tools', return_value={'subfinder': 'fixture'}):
            self.engine = pipeline.ReconPipeline(self.root)

    def revoke(self):
        self.scope.write_text('scope:\n  in_scope:\n    domains: []\n  out_of_scope:\n    domains: [example.test]\n' + AUTHORIZATION_YAML)

    def test_scope_changed_after_plan_blocks_probe_before_constructor(self):
        self.revoke()
        with patch.object(pipeline, 'ProbeClient') as client:
            result = self.engine.run_all('probe')
        client.assert_not_called()
        self.assertEqual(result['summary']['status'], 'failed')
        self.assertIn('cambiaron', result['stage_results']['probe']['error'])

    def test_scope_deleted_invalid_or_limits_changed_blocks_external_process(self):
        original = self.scope.read_text()
        for content in [None, 'scope: invalid\n', original + 'operational_limits:\n  max_parallel_threads: 2\n']:
            with self.subTest(content=content):
                if content is None:
                    self.scope.unlink()
                else:
                    self.scope.write_text(content)
                with patch.object(pipeline.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, '', '')) as run:
                    with self.assertRaises((ValueError, OSError)):
                        self.engine._tool('subfinder', ['-d', 'example.test'])
                    run.assert_not_called()
                self.scope.write_text(original)

    def test_active_host_revalidation_precedes_dns(self):
        with patch.object(probe, 'local_network_addresses', return_value=set()):
            client = probe.ProbeClient(self.engine.scope_data, self.engine.limits, before_request=self.engine.revalidate_scope)
        self.revoke()
        with patch.object(probe.socket, 'getaddrinfo') as dns, patch.object(probe, 'PinnedConnection') as connection:
            with self.assertRaises(ValueError):
                client.probe_host('example.test')
            dns.assert_not_called()
            connection.assert_not_called()

    def test_scope_change_between_https_and_http_prevents_second_request(self):
        with patch.object(probe, 'local_network_addresses', return_value=set()):
            client = probe.ProbeClient(self.engine.scope_data, self.engine.limits, before_request=self.engine.revalidate_scope)
        connection = Mock()
        connection.expired.is_set.return_value = False
        connection.getresponse.return_value.status = 200
        connection.getresponse.return_value.getheader.return_value = None
        connection.request.side_effect = lambda *args, **kwargs: self.revoke()
        with patch.object(probe.socket, 'getaddrinfo', return_value=[(None, None, None, None, ('8.8.8.8', 443))]), \
             patch.object(probe, 'PinnedConnection', return_value=connection) as factory, \
             patch.object(client.limiter, 'wait'):
            with self.assertRaises(ValueError):
                client.probe_host('example.test')
        self.assertEqual(factory.call_count, 1)
        self.assertEqual(connection.request.call_count, 1)
        connection.close.assert_called_once()

    def test_scope_change_while_waiting_for_rate_limit_blocks_connection(self):
        with patch.object(probe, 'local_network_addresses', return_value=set()):
            client = probe.ProbeClient(self.engine.scope_data, self.engine.limits, before_request=self.engine.revalidate_scope)
        with patch.object(probe.socket, 'getaddrinfo', return_value=[(None, None, None, None, ('8.8.8.8', 443))]), \
             patch.object(client.limiter, 'wait', side_effect=self.revoke), \
             patch.object(probe, 'PinnedConnection') as connection:
            with self.assertRaises(ValueError):
                client.probe_host('example.test')
            connection.assert_not_called()

    def test_checkpoint_rejects_new_scope_and_legacy_unversioned_state(self):
        checkpoint = self.root / 'recon/.checkpoint.json'
        with patch.object(self.engine, 'run_subdomain_enumeration', return_value={'status': 'completed'}), \
             patch.object(self.engine, 'run_live_probing', side_effect=pipeline.StageError('fixture')), \
             patch.object(pipeline, 'send_notification'):
            self.engine.run_all()
        saved = json.loads(checkpoint.read_text())
        self.assertEqual(saved['scope_revision'], self.engine.scope_revision)
        self.revoke()
        with patch.object(pipeline, 'detect_tools', return_value={}):
            next_engine = pipeline.ReconPipeline(self.root)
        with self.assertRaisesRegex(ValueError, 'checkpoint'):
            next_engine.run_all(resume=True)
        saved.pop('scope_revision')
        checkpoint.write_text(json.dumps(saved))
        with self.assertRaisesRegex(ValueError, 'checkpoint'):
            self.engine.run_all(resume=True)

    def test_simulation_records_scope_revision_without_writes_or_network(self):
        with patch.object(pipeline, 'detect_tools', return_value={}), patch.dict(os.environ, {'SECLAB_RECON_RUN_ID': 'fixture-job-id'}):
            engine = pipeline.ReconPipeline(self.root, dry_run=True)
        before = {path.relative_to(self.root).as_posix(): path.read_bytes() for path in self.root.rglob('*') if path.is_file()}
        self.scope.write_text('# comentario\n' + self.scope.read_text())
        before['target.yaml'] = self.scope.read_bytes()
        with patch.object(pipeline, 'ProbeClient') as client, patch.object(pipeline.subprocess, 'run') as run:
            result = engine.run_all('probe')
        client.assert_not_called()
        run.assert_not_called()
        self.assertEqual(result['summary']['status'], 'simulated')
        self.assertEqual(len(result['summary']['scope_revision']), 64)
        self.assertEqual(result['summary']['run_id'], 'fixture-job-id')
        contract = result['summary']['scope_contract']
        revision = hashlib.sha256(json.dumps(contract, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()
        self.assertEqual(result['summary']['scope_revision'], revision)
        after = {path.relative_to(self.root).as_posix(): path.read_bytes() for path in self.root.rglob('*') if path.is_file()}
        self.assertEqual(before, after)


if __name__ == '__main__':
    unittest.main()
