import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from app.services.proxy_service import ProxyService, vault_service
from app.models.schemas import ChatCompletionRequest, ChatMessage, ChatCompletionResponse


class TestProviderBoundary(unittest.TestCase):
    def setUp(self):
        self.service = ProxyService()
        self.req = ChatCompletionRequest(messages=[ChatMessage(role='user', content='fixture context')])
        self.local = {'is_active': True, 'api_key': 'fixture', 'base_url': 'http://ollama.internal/v1', 'model_name': 'fixture-model'}

    def run_request(self, entries, profile='local', failure=None):
        reply = ChatCompletionResponse(provider='custom_llm', model='fixture-model', content='fixture', latency_ms=1)
        with patch.object(vault_service, 'get_key_entry', side_effect=lambda p: entries.get(p)), \
                patch.object(vault_service, 'list_keys', return_value=[SimpleNamespace(provider='openai', service_type='llm', is_active=True, model_name='remote')]) as keys, \
                patch.object(self.service, '_dispatch_single_provider', new=AsyncMock(side_effect=failure, return_value=reply)) as dispatch, \
                patch.object(self.service, '_log_request'):
            try:
                result = asyncio.run(self.service.chat_completion(self.req, profile=profile))
            except (ValueError, RuntimeError):
                result = None
            return result, dispatch.call_args_list, keys.call_count

    def test_missing_inactive_empty_or_openrouter_local_never_uses_cloud(self):
        for entry in (None, dict(self.local, is_active=False), dict(self.local, api_key=''),
                      dict(self.local, base_url=None), dict(self.local, base_url='https://openrouter.ai/api/v1')):
            with self.subTest(entry=entry):
                reply, calls, key_calls = self.run_request({'custom_llm': entry})
                self.assertIsNone(reply)
                self.assertEqual(calls, [])
                self.assertEqual(key_calls, 0)

    def test_local_success_and_failures_stay_on_configured_provider(self):
        for failure in (None, RuntimeError('timeout'), RuntimeError('HTTP 401'), RuntimeError('HTTP 429'),
                        RuntimeError('HTTP 500'), RuntimeError('invalid response')):
            with self.subTest(failure=failure):
                reply, calls, key_calls = self.run_request({'custom_llm': self.local}, failure=failure)
                self.assertEqual(len(calls), 1)
                self.assertEqual(calls[0].args[0], 'custom_llm')
                self.assertEqual(key_calls, 0)
                self.assertEqual(reply is None, failure is not None)

    def test_explicit_custom_provider_does_not_fallback_to_openrouter(self):
        self.req.provider = 'custom_llm'
        reply, calls, _ = self.run_request({'custom_llm': self.local, 'openrouter': self.local}, failure=RuntimeError('failed'))
        self.assertIsNone(reply)
        self.assertEqual([c.args[0] for c in calls], ['custom_llm'])

    def test_general_profile_retains_authorized_failover(self):
        _, calls, _ = self.run_request({'openrouter': self.local, 'openai': self.local}, profile='quick', failure=RuntimeError('failed'))
        self.assertEqual([c.args[0] for c in calls], ['openrouter', 'openai'])

    def test_local_with_explicit_model_stays_local_and_missing_endpoint_fails_closed(self):
        for model in ('local-model', 'vendor/model'):
            self.req.model = model
            reply, calls, key_calls = self.run_request({'custom_llm': self.local, 'openrouter': self.local})
            self.assertIsNotNone(reply)
            self.assertEqual([c.args[0] for c in calls], ['custom_llm'])
            self.assertEqual(calls[0].kwargs['model_override'], model)
            self.assertEqual(key_calls, 0)
            reply, calls, key_calls = self.run_request({'custom_llm': None, 'openrouter': self.local})
            self.assertIsNone(reply)
            self.assertEqual(calls, [])
            self.assertEqual(key_calls, 0)
