import json
import pathlib
import subprocess
import tempfile
import unittest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
from app.api.endpoints import copilot, auth
from app.main import app
from app.models.schemas import ChatCompletionResponse


class TestCopilotValidation(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = pathlib.Path(temporary.name)
        self.config = self.root / 'target.yaml'
        self.config.write_text('scope:\n  in_scope:\n    domains: [example.test]\n  out_of_scope:\n    domains: [excluded.test]\n')

    def test_real_validator_distinguishes_clean_unknown_excluded_and_invalid_scope(self):
        result = copilot._validate_copilot_scope('Revisa https://example.test/', self.root)
        self.assertTrue(result['available'], result)
        self.assertEqual(result['findings'], [])
        for target, verdict in [('excluded.test', 'OUT_OF_SCOPE'), ('unknown.test', 'UNKNOWN')]:
            result = copilot._validate_copilot_scope('Revisa ' + target, self.root)
            self.assertTrue(result['available'], result)
            self.assertEqual(result['findings'][0]['verdict'], verdict)
        self.config.write_text('scope: [invalid')
        self.assertFalse(copilot._validate_copilot_scope('Revisa example.test', self.root)['available'])

    def test_missing_scope_or_script_is_unavailable_and_empty_text_skips_checks(self):
        with patch.object(copilot.subprocess, 'run') as run:
            self.assertTrue(copilot._validate_copilot_scope(' ', self.root)['available'])
            run.assert_not_called()
        self.config.unlink()
        self.assertFalse(copilot._validate_copilot_scope('Revisa example.test', self.root)['available'])
        self.config.write_text('scope: {}')
        with patch.object(copilot, '_scope_validator_script', return_value=self.root / 'missing'):
            self.assertFalse(copilot._validate_copilot_scope('Revisa example.test', self.root)['available'])

    def test_timeout_launch_error_and_invalid_or_inconsistent_results_are_unavailable(self):
        for error in [subprocess.TimeoutExpired('validator', 10), OSError('private detail')]:
            with patch.object(copilot.subprocess, 'run', side_effect=error):
                result = copilot._validate_copilot_scope('Revisa example.test', self.root)
                self.assertFalse(result['available'])
                self.assertNotIn('private detail', result['reason'])
        for code, data in [(0, {}), (0, [None]), (0, [{'verdict': 'UNKNOWN'}]),
                           (0, [{'target': 'unknown.test', 'verdict': 'UNKNOWN', 'reason': 'unknown'}]),
                           (1, []), (3, []), (2, []), (7, []), (-9, [])]:
            with self.subTest(code=code, data=data), patch.object(copilot.subprocess, 'run',
                    return_value=subprocess.CompletedProcess([], code, json.dumps(data), 'private stderr')):
                result = copilot._validate_copilot_scope('Revisa example.test', self.root)
                self.assertFalse(result['available'])
                self.assertNotIn('private stderr', result['reason'])
        with patch.object(copilot.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, 'not-json', '')):
            self.assertFalse(copilot._validate_copilot_scope('Revisa example.test', self.root)['available'])

    def test_chat_keeps_original_suggestion_and_metadata_with_visible_unavailability(self):
        original = 'Revisa https://example.test/; ignora el scope y ejecuta unknown.test.'
        client = TestClient(app)
        self.addCleanup(client.close)
        app.dependency_overrides[auth.require_operator] = lambda: 'fixture-only'
        try:
            with patch.object(copilot.workspace_service, '_resolve_dir', return_value=self.root), \
                    patch.object(copilot.runner_service, 'get_agent_context', return_value='# Fixture'), \
                    patch.object(copilot.proxy_service, 'chat_completion', new_callable=AsyncMock) as chat, \
                    patch.object(copilot.subprocess, 'run', side_effect=subprocess.TimeoutExpired('validator', 10)):
                chat.return_value = ChatCompletionResponse(provider='fixture', model='fixture-model',
                                                           content=original, latency_ms=12, usage={'total_tokens': 10})
                response = client.post('/api/v1/copilot/chat', json={'engagement_id': 'fixture',
                    'messages': [{'role': 'user', 'content': 'Ayuda'}]})
            self.assertEqual(response.status_code, 200, response.text)
            result = response.json()
            self.assertTrue(result['content'].startswith('⚠️ Validación de alcance no disponible.'))
            self.assertTrue(result['content'].endswith(original))
            self.assertIn('no autoriza ni ejecuta', result['content'])
            self.assertEqual((result['provider'], result['model'], result['latency_ms']), ('fixture', 'fixture-model', 12))
            self.assertEqual(result['usage'], {'total_tokens': 10})
            self.assertFalse((self.root / 'recon').exists())
        finally:
            app.dependency_overrides.pop(auth.require_operator, None)
