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
CHECK
printf '%s\n' "installed_checklist=ok imagen=$image coverage=25 next=auth closure=shared"
