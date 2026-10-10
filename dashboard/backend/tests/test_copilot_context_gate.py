import pathlib
import subprocess
import tempfile
import unittest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
from app.api.endpoints import auth, copilot
from app.main import app
from app.models.schemas import ChatCompletionResponse
from app.services import runner_service as runner_module


class TestCopilotContextGate(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = pathlib.Path(temporary.name)
        self.script = self.root / 'private-context.py'
        self.script.write_text('print("# Contexto fixture")\n')
        self.client = TestClient(app)
        self.addCleanup(self.client.close)
        app.dependency_overrides[auth.require_operator] = lambda: 'fixture-only'
        self.addCleanup(lambda: app.dependency_overrides.pop(auth.require_operator, None))
        self.addCleanup(patch.stopall)
        patch.object(copilot.workspace_service, '_resolve_dir', return_value=self.root).start()
        patch.object(copilot.runner_service, '_script', return_value=self.script).start()
        patch.object(copilot, '_validate_copilot_scope', return_value={'available': True, 'findings': []}).start()
        self.chat = patch.object(copilot.proxy_service, 'chat_completion', new_callable=AsyncMock).start()
        self.chat.return_value = ChatCompletionResponse(provider='fixture',model='fixture',content='Sugerencia fixture',latency_ms=1)

    def assert_blocked(self):
        before = sorted(path.name for path in self.root.iterdir())
        preview = self.client.get('/api/v1/copilot/context/fixture?agent=general')
        response = self.client.post('/api/v1/copilot/chat', json={'engagement_id': 'fixture', 'agent_id': 'general', 'messages': [{'role': 'user', 'content': 'Ayuda'}]})
        for result in [preview, response]:
            self.assertEqual(result.status_code, 503, result.text)
            self.assertIn('Contexto no disponible',result.json()['detail'])
            for secret in ['fixture-private', str(self.root), 'Traceback']:
                self.assertNotIn(secret,result.text)
        self.chat.assert_not_awaited()
        self.assertEqual(sorted(path.name for path in self.root.iterdir()),before)

    def test_real_nonzero_generator_never_sends_partial_stdout_or_stderr(self):
        self.script.write_text('import sys\nprint("fixture-private partial stdout")\nprint("fixture-private stderr",file=sys.stderr)\nraise SystemExit(7)\n')
        self.assert_blocked()

    def test_missing_generator_is_blocked_without_starting_process(self):
        self.script.unlink()
        with patch.object(runner_module.subprocess,'run') as run:
            self.assert_blocked()
            run.assert_not_called()

    def test_timeout_launch_and_decoding_errors_are_safe_and_block_provider(self):
        for error in [subprocess.TimeoutExpired('fixture-private command',15,output=b'fixture-private'), OSError('fixture-private launch'), UnicodeDecodeError('utf-8',b'\xff',0,1,'fixture-private')]:
            with self.subTest(error=type(error).__name__), patch.object(runner_module.subprocess,'run',side_effect=error):
                self.assert_blocked()

    def test_empty_binary_or_oversize_context_is_blocked(self):
        for output in ['', ' \n', 'fixture-private\0binary', '😀' * 65537]:
            with self.subTest(size=len(output)), patch.object(runner_module.subprocess,'run',return_value=subprocess.CompletedProcess([],0,output,'fixture-private stderr')):
                self.assert_blocked()

    def test_valid_context_is_preserved_and_diagnostics_never_reach_provider(self):
        self.script.write_text('import sys\nprint("# Contexto fixture á",end="")\nprint("fixture-private warning",file=sys.stderr)\n')
        preview = self.client.get('/api/v1/copilot/context/fixture?agent=general')
        self.assertEqual(preview.status_code,200,preview.text)
        self.assertEqual(preview.json()['context'],'# Contexto fixture á')
        response = self.client.post('/api/v1/copilot/chat',json={'engagement_id':'fixture','agent_id':'general','messages':[{'role':'user','content':'Ayuda'}]})
        self.assertEqual(response.status_code,200,response.text)
        prompt=self.chat.call_args.args[0].messages[0].content
        self.assertIn('# Contexto fixture á',prompt)
        self.assertNotIn('fixture-private',prompt)
        with patch.object(runner_module.subprocess,'run',return_value=subprocess.CompletedProcess([],0,'# Contexto fixture','')) as run:
            self.assertEqual(copilot.runner_service.get_agent_context(str(self.root)),'# Contexto fixture')
            self.assertEqual(run.call_args.kwargs['timeout'],15)
            self.assertEqual(run.call_args.kwargs['encoding'],'utf-8')
