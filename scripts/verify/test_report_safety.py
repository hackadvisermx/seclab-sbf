import importlib.util
import importlib.machinery
import json
import os
import pathlib
import subprocess
import sys
import tarfile
import hashlib
import re
import uuid
import tempfile
import unittest
from unittest.mock import patch

SCRIPTS = pathlib.Path(os.environ.get('REPORT_SAFETY_SCRIPTS', pathlib.Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(SCRIPTS))


def load(name, filename):
    path = SCRIPTS / filename
    if not path.is_file():
        path = path.with_suffix('')
    spec = importlib.util.spec_from_file_location(name, path,
        loader=importlib.machinery.SourceFileLoader(name, str(path)))
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
        artifact = self.root / 'recon/confirmation.txt'
        artifact.parent.mkdir(exist_ok=True)
        artifact.write_bytes(b'Fixture de verificacion')
        refs = json.dumps([{'path': 'recon/confirmation.txt', 'sha256': hashlib.sha256(artifact.read_bytes()).hexdigest()}])
        (self.root / 'evidence/finding.md').write_text(
            f'---\nid: VULN-TEST\ntitle: Fixture\nasset: {asset}\nstatus: PROVEN\nartifact_refs: {refs}\nverification_rationale: "Operador reviso el fixture sintetico"\n---\n'
            '## 2. Pasos\nFixture de reproducción.\n## 5. Remediación\nFixture.\n', encoding='utf-8')

    def cli(self, action, output=None):
        args = [sys.executable, str(SCRIPTS / 'pt-report-compiler.py'), action, str(self.root)]
        if output:
            args.append(str(output))
        return subprocess.run(args, capture_output=True, text=True)

    def link_fixture(self, path='recon/raw.txt', payload=b'fixture artifact'):
        artifact = self.root / path
        artifact.parent.mkdir(parents=True, exist_ok=True)
        artifact.write_bytes(payload)
        reference = {'path': path, 'sha256': hashlib.sha256(payload).hexdigest()}
        finding = self.root / 'evidence/finding.md'
        finding.write_text(re.sub(r'^artifact_refs: .*$', 'artifact_refs: ' + json.dumps([reference]), finding.read_text(), flags=re.M))
        return artifact, reference

    def test_finding_identity_survives_rename_and_blocks_corruption_or_collision(self):
        identity = uuid.uuid4().hex
        finding = self.root / 'evidence/finding.md'
        finding.write_text(finding.read_text().replace('id: VULN-TEST', 'id: VULN-TEST\nfinding_id: "' + identity + '"'))
        self.assertIn(identity, report.build_report(self.root).read_text())
        finding = finding.rename(finding.with_name('renamed.md'))
        self.assertIn(identity, report.build_report(self.root).read_text())
        previous = (self.root / 'REPORT.md').read_bytes()
        duplicate = finding.with_name('copy.md')
        duplicate.write_bytes(finding.read_bytes())
        self.assertFalse(report.check_findings(self.root)[0])
        with self.assertRaises(report.ReportValidationError):
            report.build_report(self.root)
        self.assertEqual((self.root / 'REPORT.md').read_bytes(), previous)
        duplicate.unlink()
        finding.write_text(finding.read_text().replace(identity, 'bad-id'))
        self.assertFalse(report.check_findings(self.root)[0])
        with self.assertRaises(report.ReportValidationError):
            report.build_report(self.root)
        self.assertEqual((self.root / 'REPORT.md').read_bytes(), previous)

    def test_finding_manifest_links_identity_source_and_selected_versions_in_both_formats(self):
        import zipfile
        identity = uuid.uuid4().hex
        finding = self.root / 'evidence/finding.md'
        text = finding.read_text().replace('id: VULN-TEST', 'id: VULN-TEST\nfinding_id: "' + identity + '"')
        finding.write_bytes((text + '\nAuthorization: Bearer fixture-private-token\n').replace('\n', '\r\n').encode())
        originals = {path: (self.root / path).read_bytes() for path in ['evidence/finding.md', 'recon/confirmation.txt']}
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
                    manifest = json.loads(contents['finding-manifest.json'])
                    self.assertEqual(manifest['schema_version'], 1)
                    self.assertEqual(manifest['sanitized'], sanitize)
                    self.assertEqual(len(manifest['findings']), 1)
                    row = manifest['findings'][0]
                    self.assertEqual(row['finding_id'], identity)
                    self.assertEqual(row['identity_status'], 'recorded')
                    self.assertEqual(row['source']['path'], 'evidence/finding.md')
                    self.assertEqual([ref['path'] for ref in row['artifact_refs']], ['recon/confirmation.txt'])
                    for source in [row['source'], *row['artifact_refs']]:
                        self.assertEqual(source['original_sha256'], hashlib.sha256(originals[source['path']]).hexdigest())
                        self.assertEqual(source['export_sha256'], hashlib.sha256(contents[source['path']]).hexdigest())
                    self.assertEqual(row['artifact_refs'][0]['expected_sha256'], row['artifact_refs'][0]['original_sha256'])
                    self.assertEqual(manifest['report']['export_sha256'], hashlib.sha256(contents['REPORT.md']).hexdigest())
                    self.assertEqual(manifest['report']['original_sha256'], hashlib.sha256((self.root / 'REPORT.md').read_bytes()).hexdigest())
                    self.assertIn('./evidence/finding.md#sha256=' + row['source']['original_sha256'], contents['REPORT.md'].decode())
                    self.assertIn(identity, contents['REPORT.md'].decode())
                    if sanitize:
                        self.assertNotIn(b'fixture-private-token', contents['finding-manifest.json'])
                        self.assertNotIn(b'fixture-private-token', contents['evidence/finding.md'])
                    for path, payload in originals.items():
                        self.assertEqual((self.root / path).read_bytes(), payload)
                    digest = hashlib.sha256(contents['finding-manifest.json']).hexdigest()
                    self.assertIn(digest + '  finding-manifest.json', contents['manifest.sha256'].decode())

    def test_changed_finding_after_compile_blocks_export_without_replacing_prior_bundle(self):
        destination = self.root / 'prior.tar.gz'
        destination.write_bytes(b'prior bundle')
        original_build = packer.ensure_report_built
        def mutate_after_compile(*args, **kwargs):
            result = original_build(*args, **kwargs)
            finding = self.root / 'evidence/finding.md'
            finding.write_text(finding.read_text() + '\nChanged after compilation')
            return result
        with patch.object(packer, 'ensure_report_built', side_effect=mutate_after_compile):
            with self.assertRaisesRegex(ValueError, 'ficha.*cambi|Ficha.*cambi'):
                packer.pack_engagement(self.root, destination)
        self.assertEqual(destination.read_bytes(), b'prior bundle')
        self.assertFalse(list(self.root.glob('.staging_pack*')))

    def test_changed_report_after_compile_blocks_export_without_replacing_prior_bundle(self):
        destination = self.root / 'prior.zip'
        destination.write_bytes(b'prior bundle')
        original = packer.ensure_report_built
        def changed(*args, **kwargs):
            result = original(*args, **kwargs)
            result.write_text('Replaced report')
            return result
        with patch.object(packer, 'ensure_report_built', side_effect=changed):
            with self.assertRaisesRegex(ValueError, 'reporte cambió'):
                packer.pack_engagement(self.root, destination, archive_format='zip')
        self.assertEqual(destination.read_bytes(), b'prior bundle')
        self.assertFalse(list(self.root.glob('.staging_pack_*')))

    def test_finding_manifest_marks_legacy_identity_missing_and_handles_empty_report(self):
        for empty in [False, True]:
            if empty:
                (self.root / 'evidence/finding.md').unlink()
            result = packer.pack_engagement(self.root)
            with tarfile.open(result['archive_path']) as archive:
                path = next(name for name in archive.getnames() if name.endswith('/finding-manifest.json'))
                manifest = json.load(archive.extractfile(path))
            self.assertEqual(len(manifest['findings']), 0 if empty else 1)
            if not empty:
                self.assertIsNone(manifest['findings'][0]['finding_id'])
                self.assertEqual(manifest['findings'][0]['identity_status'], 'unregistered')

    def test_legacy_report_does_not_invent_identity_or_modify_finding(self):
        finding = self.root / 'evidence/finding.md'
        before = finding.read_bytes()
        text = report.build_report(self.root).read_text()
        self.assertIn('Identidad persistente:** no registrada', text)
        self.assertEqual(finding.read_bytes(), before)

    def test_linked_version_is_rendered_and_changed_missing_or_invalid_refs_block(self):
        artifact, reference = self.link_fixture()
        text = report.build_report(self.root).read_text()
        self.assertIn('[recon/raw.txt](./recon/raw.txt#sha256=' + reference['sha256'] + ')', text)
        self.assertIn(reference['sha256'], text)
        previous = (self.root / 'REPORT.md').read_bytes()
        for state in ['changed', 'missing']:
            if state == 'changed':
                artifact.write_bytes(b'changed')
            else:
                artifact.unlink()
            self.assertEqual(self.cli('check').returncode, 1)
            self.assertEqual(self.cli('build').returncode, 1)
            self.assertEqual((self.root / 'REPORT.md').read_bytes(), previous)
        for value in ['null', '{}', '[{}]', 'not-json', json.dumps([reference, reference]),
                      json.dumps([dict(reference, path='../outside')]), json.dumps([dict(reference, sha256='wrong')])]:
            self.finding('example.test')
            path = self.root / 'evidence/finding.md'
            path.write_text(re.sub(r'^artifact_refs: .*$', 'artifact_refs: ' + value, path.read_text(), flags=re.M))
            self.assertEqual(self.cli('check').returncode, 1, value)

    def test_selected_artifact_is_exported_with_hashes_and_sanitization(self):
        payload = b'Authorization: Bearer fixture-private-token\nResponse: fixture\n'
        artifact, reference = self.link_fixture('fuzzing/response.txt', payload)
        for sanitize in [False, True]:
            destination = self.root / ('safe.tar.gz' if sanitize else 'original.tar.gz')
            packer.pack_engagement(self.root, destination, sanitize=sanitize)
            with tarfile.open(destination) as archive:
                copied = archive.extractfile(f'{self.root.name}/fuzzing/response.txt').read()
                manifest = json.load(archive.extractfile(f'{self.root.name}/source-manifest.json'))
                row = next(row for row in manifest['files'] if row['path'] == reference['path'])
                self.assertEqual(row['original_sha256'], reference['sha256'])
                self.assertEqual(row['export_sha256'], hashlib.sha256(copied).hexdigest())
                self.assertEqual(row['content_changed'], sanitize)
                if sanitize:
                    self.assertNotIn(b'fixture-private-token', copied)
                else:
                    self.assertEqual(copied, payload)
            self.assertEqual(artifact.read_bytes(), payload)

    def test_binary_selected_export_is_explicit_and_sanitized_export_fails_closed(self):
        for relative, payload in [('screenshots/raw.bin', b'\0\xffbinary'), ('recon/subdomains.txt', b'\0binary')]:
            with self.subTest(relative=relative):
                self.finding('example.test')
                artifact, _ = self.link_fixture(relative, payload)
                destination = self.root / 'binary.tar.gz'
                packer.pack_engagement(self.root, destination)
                before = destination.read_bytes()
                with self.assertRaisesRegex(ValueError, 'binario'):
                    packer.pack_engagement(self.root, destination, sanitize=True)
                self.assertEqual(destination.read_bytes(), before)
                self.assertEqual(artifact.read_bytes(), payload)
                self.assertFalse(list(self.root.glob('.staging_pack*')))

    def test_change_after_report_validation_blocks_pack_and_preserves_prior_bundle(self):
        artifact, _ = self.link_fixture()
        destination = self.root / 'prior.tar.gz'
        destination.write_bytes(b'prior bundle')
        real_build = packer.ensure_report_built
        def build_and_change(*args, **kwargs):
            result = real_build(*args, **kwargs)
            artifact.write_bytes(b'changed after validation')
            return result
        with patch.object(packer, 'ensure_report_built', side_effect=build_and_change), self.assertRaises(ValueError):
            packer.pack_engagement(self.root, destination)
        self.assertEqual(destination.read_bytes(), b'prior bundle')
        self.assertFalse(list(self.root.glob('.staging_pack*')))

    def test_every_confirmed_alias_requires_review_and_preserves_prior_report_and_bundle(self):
        prior = report.build_report(self.root).read_bytes()
        destination = self.root / 'prior.tar.gz'
        destination.write_bytes(b'prior bundle')
        for status in ['PROVEN', 'VERIFIED', 'CONFIRMADO']:
            for field, value in [('artifact_refs', '[]'), ('verification_rationale', '"  "'), ('verification_rationale', 'null')]:
                with self.subTest(status=status, field=field):
                    self.finding('example.test')
                    path = self.root / 'evidence/finding.md'
                    text = path.read_text().replace('status: PROVEN', 'status: ' + status)
                    path.write_text(re.sub(r'^' + field + r': .*$', lambda _: field + ': ' + value, text, flags=re.M))
                    self.assertFalse(report.check_findings(self.root)[0])
                    self.assertEqual(self.cli('build').returncode, 1)
                    with self.assertRaises(ValueError):
                        packer.pack_engagement(self.root, destination)
                    self.assertEqual((self.root / 'REPORT.md').read_bytes(), prior)
                    self.assertEqual(destination.read_bytes(), b'prior bundle')

    def test_unconfirmed_states_remain_supported_without_refs_or_review(self):
        path = self.root / 'evidence/finding.md'
        for status in ['CANDIDATE', 'DISPROVED', 'MITIGATED', 'DRAFT']:
            self.finding('example.test')
            text = path.read_text().replace('status: PROVEN', 'status: ' + status)
            path.write_text(re.sub(r'^(artifact_refs|verification_rationale): .*\n', '', text, flags=re.M))
            self.assertIn('**0 hallazgos confirmados activos**', report.build_report(self.root).read_text())
            self.assertEqual(path.read_text(), re.sub(r'^(artifact_refs|verification_rationale): .*\n', '', text, flags=re.M))

    def test_verification_rationale_json_preserves_quotes_unicode_and_newlines_and_rejects_invalid_types(self):
        path = self.root / 'evidence/finding.md'
        rationale = 'Revisión humana: "á"\nComparación con control sintético.'
        for value in [json.dumps(rationale), '[]', '{}', '"' + 'a' * 4001 + '"', 'invalid-json']:
            self.finding('example.test')
            path.write_text(re.sub(r'^verification_rationale: .*$', lambda _: 'verification_rationale: ' + value, path.read_text(), flags=re.M))
            if value == json.dumps(rationale):
                self.assertIn(rationale, report.build_report(self.root).read_text())
            else:
                self.assertFalse(report.check_findings(self.root)[0])

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
