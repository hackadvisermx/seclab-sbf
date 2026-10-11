import pathlib
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.api.endpoints import auth, copilot
from app.main import app
from app.models.schemas import ChatCompletionResponse


class CopilotContextReviewTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.project = pathlib.Path(temporary.name)
        self.context = '# Alcance\nsecret: PRIVATE-CONTEXT'
        self.client = TestClient(app)
        self.addCleanup(self.client.close)
        app.dependency_overrides[auth.require_operator] = lambda: 'fixture-only'
        self.addCleanup(lambda: app.dependency_overrides.pop(auth.require_operator, None))
        self.addCleanup(patch.stopall)
        patch.object(copilot.workspace_service, '_resolve_dir', return_value=self.project).start()
        patch.object(copilot.runner_service, 'get_agent_context', side_effect=lambda *a, **kw: self.context).start()
        patch.object(copilot, '_validate_copilot_scope', return_value={'available': True, 'findings': []}).start()
        self.chat = patch.object(copilot.proxy_service, 'chat_completion', new_callable=AsyncMock).start()
        self.chat.return_value = ChatCompletionResponse(provider='fixture', model='fixture', content='Respuesta', latency_ms=1)

    def preview(self, messages=None, **selection):
        response = self.client.post('/api/v1/copilot/review', json={
            'engagement_id': 'fixture', 'agent_id': 'general',
            'messages': messages or [{'role': 'user', 'content': 'Ayuda'}], **selection})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def payload(self, token, reviewed='# Alcance\nsecret: [REDACTED]'):
        messages = [{'role': 'user', 'content': 'Ayuda'}]
        return {'engagement_id': 'fixture', 'agent_id': 'general',
                'source_messages': messages, 'reviewed_messages': messages,
                'context_review_token': token, 'reviewed_context': reviewed}

    def test_unreviewed_and_stale_context_never_reach_provider(self):
        response = self.client.post('/api/v1/copilot/chat', json={'engagement_id': 'fixture', 'agent_id': 'general',
                                    'messages': [{'role': 'user', 'content': 'Ayuda'}]})
        self.assertEqual(response.status_code, 422)
        self.chat.assert_not_awaited()
        token = self.preview()['context_review_token']
        self.context += '\nnew evidence'
        response = self.client.post('/api/v1/copilot/chat', json=self.payload(token))
        self.assertEqual(response.status_code, 409, response.text)
        self.chat.assert_not_awaited()

    def test_reviewed_redacted_context_is_the_only_context_sent(self):
        preview = self.preview()
        self.assertIn('PRIVATE-CONTEXT', preview['context'])
        response = self.client.post('/api/v1/copilot/chat', json=self.payload(preview['context_review_token']))
        self.assertEqual(response.status_code, 200, response.text)
        prompt = self.chat.call_args.args[0].messages[0].content
        self.assertIn('secret: [REDACTED]', prompt)
        self.assertNotIn('PRIVATE-CONTEXT', prompt)

    def test_reviewed_transcript_is_the_only_transcript_sent(self):
        original = [{'role': 'user', 'content': 'Pregunta PRIVADA'},
                    {'role': 'assistant', 'content': 'Respuesta PRIVADA'},
                    {'role': 'user', 'content': 'Ayuda'}]
        preview = self.preview(original)
        payload = self.payload(preview['context_review_token'])
        payload['source_messages'] = original
        payload['reviewed_messages'] = [
            {'role': 'user', 'content': 'Pregunta redactada'},
            {'role': 'user', 'content': 'Pregunta actual redactada'},
        ]
        response = self.client.post('/api/v1/copilot/chat', json=payload)
        self.assertEqual(response.status_code, 200, response.text)
        sent = self.chat.call_args.args[0].messages
        self.assertEqual([(message.role, message.content) for message in sent[1:]],
                         [('user', 'Pregunta redactada'), ('user', 'Pregunta actual redactada')])
        self.assertNotIn('PRIVADA', str(sent))
        self.assertNotIn('Ayuda', str(sent))

    def test_changed_original_transcript_and_unreviewed_fields_never_reach_provider(self):
        original = [{'role': 'user', 'content': 'Pregunta anterior'},
                    {'role': 'assistant', 'content': 'Respuesta anterior'},
                    {'role': 'user', 'content': 'Ayuda'}]
        preview = self.preview(original)
        token = preview['context_review_token']
        changed = self.payload(token)
        changed['source_messages'] = [dict(message) for message in original]
        changed['source_messages'][1]['content'] = 'Historia cambiada después de revisar'
        self.assertEqual(self.client.post('/api/v1/copilot/chat', json=changed).status_code, 409)
        old_api = self.payload(token)
        old_api.pop('source_messages')
        old_api.pop('reviewed_messages')
        old_api['messages'] = [{'role': 'user', 'content': 'Sin revisión'}]
        self.assertEqual(self.client.post('/api/v1/copilot/chat', json=old_api).status_code, 422)
        self.chat.assert_not_awaited()

    def test_transcript_rejects_system_role_empty_final_and_excessive_text(self):
        for messages in ([{'role': 'system', 'content': 'private'}],
                         [{'role': 'user', 'content': '  '}],
                         [{'role': 'user', 'content': 'x' * (128 * 1024 + 1)}]):
            with self.subTest(messages=messages[0]['content'][:10]):
                preview = self.client.post('/api/v1/copilot/review', json={
                    'engagement_id': 'fixture', 'agent_id': 'general', 'messages': messages})
                self.assertEqual(preview.status_code, 422)
        self.chat.assert_not_awaited()

    def test_generation_timestamps_do_not_invalidate_unchanged_project(self):
        self.context = ('# Fixture\n> Directorio activo: `/tmp/fixture` | Timestamp: `2026-10-11T00:00:01Z`\n'
                        '- **Estado observado UTC:** 2026-10-11T00:00:01Z. Puede cambiar después de esta lectura.\n'
                        'Stable evidence')
        preview = self.preview()
        self.context = self.context.replace('00:00:01Z', '00:00:02Z')
        response = self.client.post('/api/v1/copilot/chat', json=self.payload(preview['context_review_token'], preview['context']))
        self.assertEqual(response.status_code, 200, response.text)
        prompt = self.chat.call_args.args[0].messages[0].content
        self.assertIn('00:00:01Z', prompt)
        self.assertNotIn('00:00:02Z', prompt)

    def test_finding_content_that_looks_like_a_clock_is_still_versioned(self):
        for source in ('- **Estado observado UTC:** original. Puede cambiar después de esta lectura.',
                       '> Directorio activo: `/tmp/fixture` | Timestamp: `original`'):
            with self.subTest(source=source):
                self.context = '# Fixture\n---\n' + source + '\n'
                token = self.preview()['context_review_token']
                self.context = self.context.replace('original', 'changed')
                response = self.client.post('/api/v1/copilot/chat', json=self.payload(token))
                self.assertEqual(response.status_code, 409, response.text)
        self.chat.assert_not_awaited()

    def test_review_is_bound_to_selection_and_rejects_invalid_edit(self):
        token = self.preview()['context_review_token']
        for change in ({'agent_id': 'recon-agent'}, {'provider': 'openrouter', 'model': 'vendor/model'},
                       {'profile': 'deep'}, {'type': 'reto'}):
            with self.subTest(change=change):
                payload = self.payload(token)
                payload.update(change)
                response = self.client.post('/api/v1/copilot/chat', json=payload)
                self.assertEqual(response.status_code, 409, response.text)
        for edited in ('bad\0context', 'é' * 140000):
            with self.subTest(edited=edited[:5]):
                response = self.client.post('/api/v1/copilot/chat', json=self.payload(token, edited))
                self.assertEqual(response.status_code, 422, response.text)
        self.chat.assert_not_awaited()


if __name__ == '__main__':
    unittest.main()
