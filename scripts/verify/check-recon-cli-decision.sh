#!/bin/sh
set -eu
image="${1:-${LAB_IMAGE:-seclab-sbf:full}}"
docker run --rm -i --read-only --network none --user tester \
  --tmpfs /tmp:rw,nosuid,nodev,mode=1777 --entrypoint python3 "$image" - <<'CHECK'
import hashlib
import json
import os
import pathlib
import subprocess
import sys
import tempfile

with tempfile.TemporaryDirectory(prefix='recon-cli-decision-') as temporary:
    root=pathlib.Path(temporary)
    workspace=root/'workspace'
    project=workspace/'engagements/fixture'
    project.mkdir(parents=True)
    data=root/'data'
    os.environ.update(WORKSPACE_DIR=str(workspace), SECLAB_DATA_DIR=str(data), NO_COLOR='1')
    sys.path.insert(0,'/usr/local/share/seclab/dashboard/backend')
    from app.core.recon_jobs import ReconJobStore
    from app.core.recon_decision import recon_decision
    store=ReconJobStore(data/'recon-jobs.db')
    key=('engagement','fixture')
    (project/'target.yaml').write_text('scope:\n  in_scope:\n    domains: [example.test]\nauthorization:\n  reference: fixture-only\n  valid_from: "2000-01-01T00:00:00Z"\n  valid_until: "2099-01-01T00:00:00Z"\n  allow_passive: true\n  allow_active: true\n')
    target_hash=hashlib.sha256((project/'target.yaml').read_bytes()).hexdigest()
    def cli():
        result=subprocess.run(['python3','/usr/local/bin/pt-next',str(project),'-j','-p','-a','-c'], capture_output=True,text=True,check=True,timeout=10)
        return json.loads(result.stdout)
    for status in ('failed','blocked','running','cancelling','cancelled','interrupted'):
        store.delete(key)
        job=store.begin(key,'probe',False)
        if status=='cancelling':
            store.request_cancel(key)
        elif status!='running':
            store.finish(key,job['run_id'],status,'SECRET fixture-only')
        before=(data/'recon-jobs.db').read_bytes()
        result=cli()
        assert result['next_step']['id']=='recon_'+status, result
        assert result['decision_job']==recon_decision(store.get(key))['decision_job'], result
        assert result['next_step']['command'] is None and result['prompt']=='' and not result['prompt_available'], result
        assert len(result['roadmap'])==1 and 'SECRET' not in str(result), result
        context_run=subprocess.run(['python3','/usr/local/bin/pt-agent-context',str(project),'-j'],capture_output=True,text=True,check=True,timeout=10)
        context=json.loads(context_run.stdout)
        state=context['recon_state']
        assert state['job']['run_id']==job['run_id'] and state['job']['status']==status, state
        assert state['decision']==recon_decision(store.get(key))['next_step'], state
        assert state['artifacts_origin']=='workspace_unattributed' and 'SECRET' not in str(state), state
        assert (data/'recon-jobs.db').read_bytes()==before
        if status not in ('running','cancelling'):
            current=store.get(key)
            store.review_outcome(key,job['run_id'],current['outcome_revision'])
            reviewed=cli()
            assert reviewed['next_step']['id']=='recon_prepare_plan', reviewed
            assert reviewed['outcome_review']==store.get(key)['outcome_review'], reviewed
            reviewed_context=json.loads(subprocess.run(['python3','/usr/local/bin/pt-agent-context',str(project),'-j'],capture_output=True,text=True,check=True,timeout=10).stdout)['recon_state']
            assert reviewed_context['decision']['id']=='recon_prepare_plan', reviewed_context
            assert reviewed_context['job']['status']==status and reviewed_context['outcome_review']['decision']=='prepare_new_plan', reviewed_context
            assert store.get(key)['status']==status
        assert hashlib.sha256((project/'target.yaml').read_bytes()).hexdigest()==target_hash
CHECK
printf '%s\n' "installed_recon_cli=ok imagen=$image decision=shared context=shared read_only=yes commands=none prompts=none"
