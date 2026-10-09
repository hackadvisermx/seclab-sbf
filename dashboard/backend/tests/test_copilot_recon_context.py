import pathlib
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient
from app.api.endpoints import auth, copilot
from app.core.recon_jobs import ReconJobStore
from app.main import app
from app.models.schemas import ChatCompletionResponse
from app.services import runner_service as runner_module


class TestCopilotReconContext(unittest.TestCase):
    def test_configured_job_state_reaches_context_endpoint_and_provider_without_raw_metadata(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = pathlib.Path(temporary)
            workspace = root/'workspace'
            project = workspace/'engagements/fixture'
            (project/'recon').mkdir(parents=True)
            (project/'target.yaml').write_text('scope:\n  in_scope:\n    domains: [example.test]\n')
            (project/'recon/live_hosts.txt').write_text('https://example.test\n')
            data = root/'data'
            store = ReconJobStore(data/'recon-jobs.db')
            key = ('engagement','fixture')
            client = TestClient(app)
            app.dependency_overrides[auth.require_operator] = lambda: 'fixture-only'
            try:
                with patch.object(runner_module, 'WORKSPACE_DIR', workspace), \
                        patch.object(runner_module, 'DATA_DIR', data), \
                        patch.object(copilot.workspace_service, '_resolve_dir', return_value=project), \
                        patch.object(copilot.proxy_service, 'chat_completion', new_callable=AsyncMock) as chat:
                    chat.return_value = ChatCompletionResponse(provider='fixture', model='fixture-model', content='Revisa el estado local.', latency_ms=12)
                    for status in ('running','cancelling','blocked','failed','cancelled','interrupted','completed','simulated','reviewed'):
                        with self.subTest(status=status):
                            store.delete(key)
                            job = store.begin(key,'probe',status=='simulated')
                            actual = 'blocked' if status=='reviewed' else status
                            if actual=='cancelling':
                                store.request_cancel(key)
                            elif actual!='running':
                                store.finish(key,job['run_id'],actual,'SECRET fixture-private-error')
                            if status=='reviewed':
                                store.review_outcome(key,job['run_id'],store.get(key)['outcome_revision'])
                            before = (data/'recon-jobs.db').read_bytes()
                            result = client.get('/api/v1/copilot/context/fixture?agent=general')
                            self.assertEqual(result.status_code,200,result.text)
                            markdown = result.json()['context']
                            self.assertIn(job['run_id'],markdown)
                            self.assertIn(f'**Estado:** `{actual}`',markdown)
                            self.assertIn('sin atribución a este job',markdown)
                            self.assertNotIn('SECRET',markdown)
                            if actual not in ('completed','simulated'):
                                self.assertNotIn('Listo para cerrar',markdown)
                            if status=='reviewed':
                                self.assertIn('Preparar otro plan tras revisar el resultado',markdown)
                                self.assertIn('Revisar no confirma resultados ni concede permisos',markdown)
                            response = client.post('/api/v1/copilot/chat',json={'engagement_id':'fixture','agent_id':'general','messages':[{'role':'user','content':'¿Cómo continúo?'}]})
                            self.assertEqual(response.status_code,200,response.text)
                            prompt = chat.call_args.args[0].messages[0].content
                            self.assertIn(job['run_id'],prompt)
                            self.assertIn(f'**Estado:** `{actual}`',prompt)
                            self.assertIn('sin atribución a este job',prompt)
                            self.assertNotIn('SECRET',prompt)
                            self.assertEqual((data/'recon-jobs.db').read_bytes(),before)
            finally:
                client.close()
                app.dependency_overrides.pop(auth.require_operator,None)
