#!/bin/sh
set -eu
image="${1:-${LAB_IMAGE:-seclab-sbf:full}}"
docker run --rm -i --read-only --network none --user tester \
  --tmpfs /tmp:rw,nosuid,nodev,mode=1777 --entrypoint python3 "$image" - <<'CHECK'
import importlib.machinery
import importlib.util
import json
import pathlib
import subprocess
import tempfile

with tempfile.TemporaryDirectory(prefix='checklist-parity-') as temporary:
    root = pathlib.Path(temporary)
    project = root / 'fixture'
    (project / 'recon').mkdir(parents=True)
    (project / 'target.yaml').write_text(
        'engagement:\n  name: fixture\n  status: active\n'
        'scope:\n  in_scope:\n    domains: [example.test]\n'
        'authorization:\n  reference: fixture-only\n'
        '  valid_from: "2000-01-01T00:00:00Z"\n  valid_until: "2099-01-01T00:00:00Z"\n'
        '  allow_passive: true\n  allow_active: true\n')
    (project / 'recon/live_hosts.txt').write_text('https://example.test\n')
    (project / 'notes.md').write_text('## Disciplina: fuzzing\n')
    def command(name):
        result = subprocess.run(['python3', '/usr/local/bin/' + name, '-j', str(project)],
            cwd=root, capture_output=True, text=True, check=True, timeout=20)
        return json.loads(result.stdout)
    checklist = command('pt-audit-checklist')
    context = command('pt-agent-context')['coverage']
    assert checklist['coverage_score'] == 25.0, checklist
    assert context['coverage_score'] == checklist['coverage_score'], context
    assert [(row['id'], row['status']) for row in context['matrix']] == [
        (row['id'], row['status']) for row in checklist['matrix']]
    assert command('pt-next')['next_step']['id'] == 'auth'
    path = '/usr/local/bin/pt-engagement-packer'
    spec = importlib.util.spec_from_file_location('packer', path,
        loader=importlib.machinery.SourceFileLoader('packer', path))
    packer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(packer)
    readiness = checklist['readiness']
    assert packer.check_closure_readiness(project) == (
        readiness['ready_for_closure'], readiness['blocking_issues'], readiness['recommendations'])
    (project / 'evidence').mkdir()
    (project / 'evidence/README.md').write_text('Fixture documentation')
    (project / 'evidence/.hidden.md').write_text('Fixture hidden file')
    (project / 'REPORT.md').write_text('Fixture report')
    (project / 'notes.md').write_text(''.join('## Disciplina: ' + row['id'] + '\n' for row in checklist['matrix']))
    target = project / 'target.yaml'
    original_target = target.read_text()
    finding = project / 'evidence/fixture.md'
    for status, pending, normalized in [
        (None, True, 'CANDIDATE'), ('CANDIDATE', True, 'CANDIDATE'),
        ('UNVERIFIED', True, 'DRAFT'), ('BLOCKED', True, 'BLOCKED'),
        ('UNKNOWN', True, 'UNKNOWN'), ('PROVEN', False, 'PROVEN'),
        ('Confirmado', False, 'PROVEN'), ('DISPROVED', False, 'DISPROVED'),
        ('REMEDIATED', False, 'MITIGATED')]:
        content = '---\nid: FIXTURE\n' + ('status: "' + status + '" # fixture\n' if status else '') + '---\nstatus: draft in body'
        finding.write_text(content)
        result = command('pt-audit-checklist')
        assert result['total_findings'] == 1, result
        assert result['findings_summary']['unverified'] == int(pending), result
        assert result['findings_summary']['verified'] == int(normalized == 'PROVEN'), result
        assert result['readiness']['ready_for_closure'] == (not pending), result
        assert result['matrix'][-1]['status'] == ('IN_PROGRESS' if pending else 'COMPLETED'), result
        context = command('pt-agent-context')
        assert context['findings']['items'][0]['status'] == normalized, context
        next_steps = command('pt-next')
        assert next_steps['next_step']['id'] == ('verify_findings' if pending else 'pack_and_close'), next_steps
        assert packer.check_closure_readiness(project)[0] == (not pending)
        if pending:
            closed = subprocess.run(['python3', path, 'close', '-j', str(project)],
                cwd=root, capture_output=True, text=True, timeout=20)
            assert json.loads(closed.stdout)['status'] == 'blocked', closed.stdout
            assert target.read_text() == original_target
        assert finding.read_text() == content
CHECK
printf '%s\n' "installed_checklist=ok imagen=$image coverage=25 next=auth closure=shared triage=consistent"
