import importlib.util
import json
import os
import pathlib
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

SCRIPTS = pathlib.Path(os.environ.get('REPORT_SAFETY_SCRIPTS', pathlib.Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(SCRIPTS))


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


report = load('report_safety_compiler', 'pt-report-compiler.py')
packer = load('report_safety_packer', 'pt-engagement-packer.py')


class ReportSafetyTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = pathlib.Path(temporary.name)
        (self.root / 'evidence').mkdir()
        (self.root / 'target.yaml').write_text(
            'scope:\n  in_scope:\n    domains: [example.test]\n'
            '  out_of_scope:\n    domains: [excluded.example.test]\n', encoding='utf-8')
        self.finding('example.test')

    def finding(self, asset):
        (self.root / 'evidence/finding.md').write_text(
            f'---\nid: VULN-TEST\ntitle: Fixture\nasset: {asset}\nstatus: PROVEN\n---\n'
            '## 2. Pasos\nFixture de reproducción.\n## 5. Remediación\nFixture.\n', encoding='utf-8')

    def cli(self, action, output=None):
        args = [sys.executable, str(SCRIPTS / 'pt-report-compiler.py'), action, str(self.root)]
        if output:
            args.append(str(output))
        return subprocess.run(args, capture_output=True, text=True)

    def test_missing_empty_or_null_status_never_confirms_a_finding(self):
        path = self.root / 'evidence/finding.md'
        for declaration in ['', 'status: ""\n', 'status: null\n', 'status: "  "\n']:
            with self.subTest(declaration=declaration):
                self.finding('example.test')
                path.write_text(path.read_text().replace('status: PROVEN\n', declaration))
                self.assertEqual(report.parse_evidence_file(path)['status'], 'CANDIDATE')
                text = report.build_report(self.root).read_text()
                self.assertIn('**0 hallazgos confirmados activos**', text)
                self.assertIn('| CANDIDATE |', text)
        for status in ['PROVEN', 'VERIFIED', 'Confirmado']:
            self.finding('example.test')
            path.write_text(path.read_text().replace('status: PROVEN', 'status: ' + status))
            self.assertEqual(report.parse_evidence_file(path)['status'], 'PROVEN')
            self.assertIn('**1 hallazgos confirmados activos**', report.build_report(self.root).read_text())

    def test_cli_blocks_excluded_and_unknown_without_overwriting_reports(self):
        for asset, message in [('excluded.example.test', 'FUERA DE ALCANCE'), ('outside.test', 'sin alcance confirmado')]:
            self.finding(asset)
            for output in [self.root / 'REPORT.md', self.root / 'custom.md']:
                with self.subTest(asset=asset, output=output.name):
                    output.write_bytes(b'reporte previo')
                    result = self.cli('build', output)
                    self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                    self.assertIn(message, result.stderr)
                    self.assertNotIn('compilado exitosamente', result.stdout)
                    self.assertEqual(output.read_bytes(), b'reporte previo')
                    output.unlink()
                    self.assertEqual(self.cli('build', output).returncode, 1)
                    self.assertFalse(output.exists())
            self.assertEqual(self.cli('check').returncode, 1)

    def test_missing_invalid_scope_and_missing_asset_block(self):
        for target in [None, 'scope: invalid\n', 'scope:\n  in_scope:\n    ips: [bad-ip]\n']:
            with self.subTest(target=target):
                path = self.root / 'target.yaml'
                if target is None:
                    path.unlink()
                else:
                    path.write_text(target)
                ok, issues, _ = report.check_findings(self.root)
                self.assertFalse(ok)
                self.assertTrue(any('target.yaml' in issue for issue in issues), issues)
                self.assertEqual(self.cli('build').returncode, 1)
        (self.root / 'target.yaml').write_text('scope:\n  in_scope:\n    domains: [example.test]\n')
        for asset in ['', 'N/A']:
            self.finding(asset)
            self.assertEqual(self.cli('build').returncode, 1)
            self.assertIn('Falta el activo', self.cli('check').stderr)

    def test_unavailable_scope_validator_blocks_python_api(self):
        with patch.object(report, 'load_scope_validator', return_value=None):
            self.assertFalse(report.check_findings(self.root)[0])
            with self.assertRaisesRegex(ValueError, 'Scope Guard'):
                report.build_report(self.root)
        self.assertFalse((self.root / 'REPORT.md').exists())

    def test_unreadable_finding_and_missing_poc_block(self):
        (self.root / 'evidence/finding.md').write_bytes(b'\xff')
        self.assertEqual(self.cli('build').returncode, 1)
        self.assertIn('No se pudo leer la ficha', self.cli('check').stderr)
        self.finding('example.test')
        path = self.root / 'evidence/finding.md'
        path.write_text(path.read_text().replace('## 2. Pasos', 'Sin reproducción'))
        self.assertEqual(self.cli('build').returncode, 1)
        self.assertFalse((self.root / 'REPORT.md').exists())

    def test_pack_revalidates_scope_even_with_existing_report_and_archive(self):
        report.build_report(self.root)
        prior = (self.root / 'REPORT.md').read_bytes()
        self.finding('excluded.example.test')
        archive = self.root / 'exports/prior.tar.gz'
        archive.parent.mkdir()
        archive.write_bytes(b'archivo previo')
        result = subprocess.run([sys.executable, str(SCRIPTS / 'pt-engagement-packer.py'),
                                 'pack', str(self.root), '-j', '-o', str(archive)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertEqual(json.loads(result.stdout)['status'], 'blocked')
        self.assertEqual(archive.read_bytes(), b'archivo previo')
        self.assertEqual((self.root / 'REPORT.md').read_bytes(), prior)
        self.assertFalse(list(self.root.glob('.staging_pack*')))

    def test_valid_pack_refreshes_stale_report_and_has_valid_manifest(self):
        (self.root / 'REPORT.md').write_text('stale outside.test')
        result = packer.pack_engagement(self.root, sanitize=True)
        self.assertEqual(result['status'], 'success')
        with tarfile.open(result['archive_path']) as archive:
            prefix = self.root.name + '/'
            content = archive.extractfile(prefix + 'REPORT.md').read().decode()
            self.assertIn('example.test', content)
            self.assertNotIn('stale outside.test', content)
            manifest = archive.extractfile(prefix + 'manifest.sha256').read().decode()
            import hashlib
            for line in manifest.splitlines():
                digest, name = line.split('  ', 1)
                self.assertEqual(hashlib.sha256(archive.extractfile(prefix + name).read()).hexdigest(), digest)

    def test_zero_findings_report_remains_supported_with_valid_scope(self):
        (self.root / 'evidence/finding.md').unlink()
        self.assertTrue(report.check_findings(self.root)[0])
        self.assertIn('**0 hallazgos confirmados activos**', report.build_report(self.root).read_text())
        (self.root / 'target.yaml').unlink()
        self.assertEqual(self.cli('build').returncode, 1)

    def test_report_describes_only_available_records_and_declared_validation(self):
        content = report.build_report(self.root).read_text()
        self.assertIn("No hay un registro local `terminal.log` disponible", content)
        self.assertNotIn("Registro sellado", content)
        self.assertNotIn("se llevaron a cabo pruebas técnicas autorizadas", content)
        self.assertIn("requieren revisión humana", content)
        (self.root / 'terminal.log').write_text('fixture')
        content = report.build_report(self.root).read_text()
        self.assertIn("está disponible en el engagement", content)
        self.assertIn("no se acredita que sea completo ni sellado", content)

    def test_source_manifest_tracks_original_and_sanitized_outputs_in_both_formats(self):
        import hashlib
        import zipfile
        names = ['terminal.log', 'recon/recon.log', 'recon/probe_observations.jsonl',
                 'recon/urls_all.txt', 'recon/js_files.txt']
        originals = {}
        for name in names:
            path = self.root / name
            path.parent.mkdir(exist_ok=True)
            text = '{"output": "Authorization: Bearer fixture-private-token"}\r\n'
            path.write_bytes(text.encode('utf-8'))
            originals[name] = path.read_bytes()
        for archive_format in ['tar.gz', 'zip']:
            for sanitize in [True, False]:
                with self.subTest(archive_format=archive_format, sanitize=sanitize):
                    result = packer.pack_engagement(self.root, sanitize=sanitize, archive_format=archive_format)
                    if archive_format == 'zip':
                        with zipfile.ZipFile(result['archive_path']) as archive:
                            contents = {name.split('/', 1)[1]: archive.read(name) for name in archive.namelist()}
                    else:
                        with tarfile.open(result['archive_path']) as archive:
                            contents = {name.split('/', 1)[1]: archive.extractfile(name).read() for name in archive.getnames()}
                    manifest = json.loads(contents['source-manifest.json'])
                    records = {row['path']: row for row in manifest['files']}
                    self.assertEqual(manifest['schema_version'], 1)
                    self.assertEqual(manifest['sanitized'], sanitize)
                    for name in names:
                        self.assertEqual(records[name]['original_sha256'], hashlib.sha256(originals[name]).hexdigest())
                        self.assertEqual(records[name]['export_sha256'], hashlib.sha256(contents[name]).hexdigest())
                        self.assertEqual(records[name]['content_changed'], sanitize)
                        self.assertEqual((self.root / name).read_bytes(), originals[name])
                        if sanitize:
                            self.assertNotIn(b'fixture-private-token', contents[name])
                        else:
                            self.assertEqual(contents[name], originals[name])
                    for line in contents['manifest.sha256'].decode().splitlines():
                        digest, name = line.split('  ', 1)
                        self.assertEqual(digest, hashlib.sha256(contents[name]).hexdigest())

    def test_export_rejects_external_symlink_sources_without_creating_bundle(self):
        external = self.root / 'outside.txt'
        external.write_text('private fixture')
        for name in ['terminal.log', 'REPORT.md', 'evidence/finding.md']:
            with self.subTest(source=name):
                path = self.root / name
                if path.exists():
                    path.unlink()
                path.symlink_to(external)
                with self.assertRaises(ValueError):
                    packer.pack_engagement(self.root)
                self.assertEqual(external.read_text(), 'private fixture')
                self.assertFalse(list(self.root.glob('exports/*.tar.gz')))
                self.assertFalse(list(self.root.glob('.staging_pack*')))
                path.unlink()
                self.finding('example.test')


if __name__ == '__main__':
    unittest.main()
