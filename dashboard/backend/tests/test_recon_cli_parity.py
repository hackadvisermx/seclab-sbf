import pathlib
import tempfile
import unittest
from unittest.mock import patch

from app.core.recon_jobs import ReconJobStore
from app.core.recon_decision import recon_decision
from app.services import runner_service as runner_module


class TestReconCliParity(unittest.TestCase):
    def test_real_store_cli_and_api_share_decisions_reviews_and_new_jobs(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=pathlib.Path(temporary)
            ws=root/'workspace'; project=ws/'engagements/fixture'; project.mkdir(parents=True)
            data=root/'data'; store=ReconJobStore(data/'recon-jobs.db')
            (project/'target.yaml').write_text('scope:\n  in_scope:\n    domains: [example.test]\nauthorization:\n  reference: fixture\n  valid_from: "2000-01-01T00:00:00Z"\n  valid_until: "2099-01-01T00:00:00Z"\n  allow_passive: true\n  allow_active: true\n')
            key=('engagement','fixture')
            with patch.object(runner_module,'WORKSPACE_DIR',ws), patch.object(runner_module,'DATA_DIR',data):
                for status in ('running','cancelling','failed','blocked','cancelled','interrupted','completed','simulated'):
                    store.delete(key)
                    job=store.begin(key,'probe',status=='simulated', reviewed_plan={'schema_version':1,'scope_revision':'a'*64})
                    if status=='cancelling':
                        store.request_cancel(key)
                    elif status!='running':
                        store.finish(key,job['run_id'],status,'SECRET private error',scope_revision='a'*64)
                    current=store.get(key)
                    result=runner_module.runner_service.get_audit_next_step(str(project),prompt_mode=True)
                    expected=recon_decision(current)
                    if expected:
                        self.assertEqual(result['next_step']['id'],expected['next_step']['id'])
                        self.assertEqual(result['decision_job'],expected['decision_job'])
                        self.assertFalse(result['prompt_available'])
                        self.assertEqual(result['prompt'],'')
                        self.assertNotIn('SECRET',str(result))
                    else:
                        self.assertEqual(result['next_step']['id'],'recon')
                    if status in ('completed','simulated','failed','blocked','cancelled','interrupted'):
                        store.review_outcome(key,job['run_id'],current['outcome_revision'])
                        reviewed=runner_module.runner_service.get_audit_next_step(str(project),prompt_mode=True)
                        self.assertEqual(reviewed['next_step']['id'],'recon_prepare_plan')
                        self.assertEqual(reviewed['outcome_review'],store.get(key)['outcome_review'])
                        new=store.begin(key,'probe',False)
                        result=runner_module.runner_service.get_audit_next_step(str(project),prompt_mode=True)
                        self.assertEqual(result['next_step']['id'],'recon_running')
                        self.assertEqual(result['decision_job']['run_id'],new['run_id'])
                        self.assertIsNone(result['outcome_review'])
