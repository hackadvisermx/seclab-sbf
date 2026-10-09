import pathlib
import tarfile
import tempfile
import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.api.endpoints import reports


class TestReportExports(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = pathlib.Path(temporary.name)
        (self.root / 'evidence').mkdir()
        (self.root / 'target.yaml').write_text(
            'scope:\n  in_scope:\n    domains: [example.test]\n'
            '  out_of_scope:\n    domains: [excluded.example.test]\n')
        self.finding('example.test')
        app = FastAPI()
        app.include_router(reports.router)
        self.client = TestClient(app)
        self.addCleanup(self.client.close)
        resolver = patch.object(reports.workspace_service, '_resolve_dir', return_value=self.root)
        resolver.start()
        self.addCleanup(resolver.stop)

    def finding(self, asset):
        (self.root / 'evidence/finding.md').write_text(
            f'---\nid: VULN-TEST\ntitle: Fixture\nasset: {asset}\n---\n'
            '## 2. Pasos\nFixture\n## 5. Remediación\nFixture\n')

    def test_real_compile_and_pack_fail_without_exposing_existing_bundle(self):
        self.assertTrue(self.client.post('/reports/fixture/compile').json()['success'])
        self.assertTrue(self.client.post('/reports/fixture/pack').json()['success'])
        prior = {path.name: path.read_bytes() for path in (self.root / 'exports').iterdir()}
        self.finding('excluded.example.test')
        result = self.client.post('/reports/fixture/compile').json()
        self.assertFalse(result['success'])
        self.assertEqual(result['content'], '')
        self.assertIn('FUERA DE ALCANCE', result['log'])
        result = self.client.post('/reports/fixture/pack').json()
        self.assertFalse(result['success'])
        self.assertIsNone(result['latest_bundle'])
        download = self.client.get('/reports/fixture/download')
        self.assertEqual(download.status_code, 409)
        self.assertIn('FUERA DE ALCANCE', download.json()['detail'])
        self.assertEqual(prior, {path.name: path.read_bytes() for path in (self.root / 'exports').iterdir()})

    def test_download_refreshes_stale_bundle_from_current_valid_findings(self):
        exports = self.root / 'exports'
        exports.mkdir()
        (exports / 'old.tar.gz').write_bytes(b'old invalid bundle')
        import os
        os.utime(exports / 'old.tar.gz', (4102444800, 4102444800))
        (self.root / 'REPORT.md').write_text('stale outside.test')
        result = self.client.get('/reports/fixture/download')
        self.assertEqual(result.status_code, 200, result.text)
        self.assertNotEqual(result.content, b'old invalid bundle')
        import io
        with tarfile.open(fileobj=io.BytesIO(result.content)) as archive:
            content = archive.extractfile(self.root.name + '/REPORT.md').read().decode()
            self.assertIn('example.test', content)
            self.assertNotIn('stale outside.test', content)
