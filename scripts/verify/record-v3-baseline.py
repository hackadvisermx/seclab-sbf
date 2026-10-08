#!/usr/bin/env python3
"""Registra comportamiento técnico con fixtures temporales, sin objetivos reales."""
import contextlib
import hashlib
import importlib.util
import io
import json
import os
import pathlib
import socket
import sys
import tarfile
import tempfile
from unittest.mock import Mock, patch

SCRIPTS = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
import seclab_scope


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


pipeline = load('v3_pipeline', 'pt-recon-pipeline.py')
report = load('v3_report', 'pt-report-compiler.py')
packer = load('v3_packer', 'pt-engagement-packer.py')


def project(root, name):
    directory = root / name
    directory.mkdir()
    (directory / 'target.yaml').write_text(
        'engagement:\n  name: fixture\n  status: active\n'
        'scope:\n  in_scope:\n    domains: [example.test]\n'
        '  out_of_scope:\n    domains: [excluded.example.test]\n', encoding='utf-8')
    (directory / 'recon').mkdir()
    (directory / 'evidence').mkdir()
    return directory


def snapshot(directory):
    return {path.relative_to(directory).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in directory.rglob('*') if path.is_file()}


def simulation(root):
    directory = project(root, 'simulation')
    (directory / 'recon/subdomains.txt').write_text(
        'example.test\nchild.example.test\nexcluded.example.test\n', encoding='utf-8')
    before = snapshot(directory)
    with patch.object(pipeline, 'detect_tools', return_value={}):
        engine = pipeline.ReconPipeline(directory, dry_run=True)
    result = engine.run_all()
    return {
        'status': result['summary']['status'],
        'planned_probe_targets': result['stage_results']['probe']['planned_targets'],
        'discarded_probe_candidates': len(result['stage_results']['probe']['discarded']),
        'workspace_unchanged': before == snapshot(directory),
        'matcher': {target: seclab_scope.check_scope(target, engine.scope_data)[0] for target in (
            'example.test', 'child.example.test', 'excluded.example.test', 'other.test')},
    }


def resumption(root):
    directory = project(root, 'resumption')
    tools = {'subfinder': 'fixture', 'gau': 'fixture', 'gf': 'fixture'}
    calls = []

    def first_tool(name, arguments, timeout=180):
        calls.append(name)
        if name == 'gau':
            raise pipeline.StageError('Fallo deliberado del proveedor de fixture.')
        return ['example.test']

    with patch.object(pipeline, 'detect_tools', return_value=tools):
        first = pipeline.ReconPipeline(directory)
        with patch.object(first, '_tool', side_effect=first_tool), patch.object(pipeline, 'ProbeClient') as client:
            client.return_value.probe.return_value = [
                {'host': 'example.test', 'url': 'https://example.test', 'status': 'response', 'http_status': 200}]
            initial = first.run_all()
        checkpoint = json.loads((directory / 'recon/.checkpoint.json').read_text())
        calls.clear()
        second = pipeline.ReconPipeline(directory)

        def resumed_tool(name, arguments, timeout=180):
            calls.append(name)
            return ['https://example.test/path'] if name == 'gau' else []

        with patch.object(second, '_tool', side_effect=resumed_tool), patch.object(pipeline, 'ProbeClient') as client:
            resumed = second.run_all(resume=True)
            probe_repeated = client.called
    return {
        'initial_status': initial['summary']['status'],
        'checkpoint_completed_stages': sorted(checkpoint['completed']),
        'resumed_status': resumed['summary']['status'],
        'subdomains_repeated': 'subfinder' in calls,
        'probe_repeated': probe_repeated,
        'checkpoint_remaining': (directory / 'recon/.checkpoint.json').exists(),
        'probe_output_origin': 'fixture; no se ejecutó sondeo real',
    }


def reporting(root):
    directory = project(root, 'reporting')
    evidence = directory / 'evidence/finding.md'

    def finding(asset):
        evidence.write_text(
            '---\nid: VULN-FIXTURE\ntitle: Hallazgo sintético\nstatus: PROVEN\n'
            f'severity: High\nasset: {asset}\n---\n'
            '## 2. Pasos\nTexto de fixture sin artefacto original.\n'
            '## 5. Remediación\nRecomendación de fixture.\n', encoding='utf-8')

    def cli(action):
        with patch.object(sys, 'argv', ['pt-report-compiler', action, str(directory)]), \
                contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return report.main()

    finding('https://other.test')
    unknown_check = cli('check')
    finding('https://excluded.example.test')
    excluded_check = cli('check')
    excluded_build = cli('build')
    content = (directory / 'REPORT.md').read_text()
    raw_paths = ['recon/probe_observations.jsonl', 'recon/recon.log']
    for name in raw_paths:
        (directory / name).write_text('fixture de salida original\n', encoding='utf-8')
    bundle = packer.pack_engagement(directory, sanitize=True)
    with tarfile.open(bundle['archive_path']) as archive:
        manifest = archive.extractfile('reporting/manifest.sha256').read().decode()
        hashes_valid = all(
            hashlib.sha256(archive.extractfile('reporting/' + name).read()).hexdigest() == digest
            for digest, name in (line.split('  ', 1) for line in manifest.splitlines()))
        included = {name.removeprefix('reporting/') for name in archive.getnames()}
    closure = packer.close_engagement(directory)
    return {
        'check_unknown_asset_exit': unknown_check,
        'check_excluded_asset_exit': excluded_check,
        'build_excluded_asset_exit': excluded_build,
        'excluded_asset_in_report': 'https://excluded.example.test' in content,
        'original_artifact_link_in_finding': any(name in evidence.read_text() for name in raw_paths),
        'report_claims_terminal_log_without_file': 'permanece archivado en' in content
            and not (directory / 'terminal.log').exists(),
        'export_manifest_hashes_valid': hashes_valid,
        'original_outputs_omitted_by_export': sorted(set(raw_paths) - included),
        'closure_status': closure['status'],
    }


def main():
    def denied(*args, **kwargs):
        raise RuntimeError('El recorder de fixtures intentó utilizar la red.')

    with tempfile.TemporaryDirectory(prefix='seclab-v3-baseline-') as folder, \
            patch.dict(os.environ, {'SECLAB_NOTIFY_WEBHOOK': ''}), \
            patch.object(socket, 'socket', side_effect=denied), \
            patch.object(socket, 'getaddrinfo', side_effect=denied):
        root = pathlib.Path(folder)
        result = {'fixture_only': True, 'human_usability_measured': False,
                  'simulation': simulation(root), 'resumption': resumption(root),
                  'reporting': reporting(root)}
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
