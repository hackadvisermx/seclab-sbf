import os
import pathlib
import tempfile
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from app.models.schemas import ChatMessage, ChatCompletionRequest, ChatCompletionResponse


class TestOpenRouterProxy(unittest.TestCase):
    def setUp(self):
        from app.core import database
        from app.services.vault_service import vault_service
        from app.services.proxy_service import proxy_service

        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db_path = pathlib.Path(self.temp.name) / "vault_test.db"
        self.db_patch = patch.object(database, "VAULT_DB_PATH", self.db_path)
        self.db_patch.start()
        self.addCleanup(self.db_patch.stop)
        database.init_db()

        self.vault_service = vault_service
        self.proxy_service = proxy_service

    def test_openrouter_dispatch_uses_custom_headers_and_model(self):
        # Insert key into Vault
        from app.models.schemas import ApiKeyCreate
        mock_token = "mock" + "-fixture-token"
        self.vault_service.upsert_key(
            ApiKeyCreate(
                provider="openrouter",
                label="OpenRouter Key",
                service_type="llm",
                api_key=mock_token,
                base_url="https://openrouter.ai/api/v1",
                model_name="anthropic/claude-3.5-sonnet",
                is_active=True,
            )
        )

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": "Respuesta táctica desde Claude 3.5 Sonnet"}}],
            "usage": {"total_tokens": 142},
        }

        req = ChatCompletionRequest(
            messages=[ChatMessage(role="user", content="Explica SSRF en 1 línea.")],
            provider="openrouter",
            model="anthropic/claude-3.5-sonnet",
            temperature=0.2,
        )

        async def run_test():
            with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
                mock_post.return_value = mock_resp
                res = await self.proxy_service._dispatch_single_provider("openrouter", req)
                self.assertEqual(res.provider, "openrouter")
                self.assertEqual(res.model, "anthropic/claude-3.5-sonnet")
                self.assertEqual(res.content, "Respuesta táctica desde Claude 3.5 Sonnet")
                self.assertEqual(res.usage["total_tokens"], 142)

                # Verificar cabeceras y payload enviados a OpenRouter
                call_args, call_kwargs = mock_post.call_args
                url = call_args[0]
                self.assertEqual(url, "https://openrouter.ai/api/v1/chat/completions")
                headers = call_kwargs["headers"]
                self.assertEqual(headers["Authorization"], f"Bearer {mock_token}")
                self.assertEqual(headers["HTTP-Referer"], "http://localhost:8080")
                self.assertEqual(headers["X-Title"], "SecLab Tactical Dashboard")
                payload = call_kwargs["json"]
                self.assertEqual(payload["model"], "anthropic/claude-3.5-sonnet")
                self.assertEqual(payload["temperature"], 0.2)

        import asyncio
        asyncio.run(run_test())

    def test_model_with_slash_routes_to_openrouter_when_active(self):
        from app.models.schemas import ApiKeyCreate
        mock_token = "mock" + "-fixture-token"
        self.vault_service.upsert_key(
            ApiKeyCreate(
                provider="openrouter",
                label="OpenRouter Key",
                service_type="llm",
                api_key=mock_token,
                base_url="https://openrouter.ai/api/v1",
                model_name="anthropic/claude-3.5-sonnet",
                is_active=True,
            )
        )

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": "Respuesta desde DeepSeek R1"}}],
            "usage": {"total_tokens": 85},
        }

        # req sin provider, pero con model="deepseek/deepseek-r1"
        req = ChatCompletionRequest(
            messages=[ChatMessage(role="user", content="Prueba")],
            model="deepseek/deepseek-r1",
        )

        async def run_test():
            with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
                mock_post.return_value = mock_resp
                res = await self.proxy_service.chat_completion(req)
                self.assertEqual(res.provider, "openrouter")
                self.assertEqual(res.model, "deepseek/deepseek-r1")
                self.assertEqual(res.content, "Respuesta desde DeepSeek R1")

        import asyncio
        asyncio.run(run_test())

    def test_vault_health_check_openrouter(self):
        from app.models.schemas import ApiKeyCreate
        mock_token = "mock" + "-fixture-token"
        self.vault_service.upsert_key(
            ApiKeyCreate(
                provider="openrouter",
                label="OpenRouter Key",
                service_type="llm",
                api_key=mock_token,
                base_url="https://openrouter.ai/api/v1",
                is_active=True,
            )
        )

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "data": {
                "label": "SecLab-Key",
                "usage": 0.0452,
                "limit": 10.0,
                "is_free_tier": False,
            }
        }

        async def run_test():
            with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
                mock_get.return_value = mock_resp
                health = await self.vault_service.check_health("openrouter")
                self.assertEqual(health.provider, "openrouter")
                self.assertEqual(health.status, "online")
                self.assertIn("0.0452", health.message)
                self.assertIn("$10.00", health.message)

        import asyncio
        asyncio.run(run_test())

    def test_copilot_endpoint_accepts_provider_and_model(self):
        from app.main import app
        from app.api.endpoints import auth
        from fastapi.testclient import TestClient

        auth._attempts.clear()
        with patch.object(auth, "TESTER_PASSWORD", "fixture-password"):
            client = TestClient(app)
            login_resp = client.post("/api/v1/auth/login", json={"password": "fixture-password"})
            self.assertEqual(login_resp.status_code, 200)

            # Mock workspace_service y runner_service
            from app.services.workspace_sync import workspace_service
            from app.services.runner_service import runner_service

            mock_dir = pathlib.Path(self.temp.name) / "test_eng"
            mock_dir.mkdir(parents=True, exist_ok=True)

            mock_resp = ChatCompletionResponse(
                provider="openrouter",
                model="deepseek/deepseek-r1",
                content="Respuesta copilot con modelo seleccionado",
                latency_ms=120,
                usage={"total_tokens": 50},
            )

            with patch.object(workspace_service, "_resolve_dir", return_value=mock_dir), \
                 patch.object(runner_service, "get_agent_context", return_value="# Mock context"), \
                 patch.object(self.proxy_service, "chat_completion", new_callable=AsyncMock) as mock_chat:
                mock_chat.return_value = mock_resp

                post_data = {
                    "engagement_id": "test_eng",
                    "type": "engagement",
                    "agent_id": "triage-agent",
                    "provider": "openrouter",
                    "model": "deepseek/deepseek-r1",
                    "messages": [{"role": "user", "content": "Analizar alcance"}],
                }
                res = client.post("/api/v1/copilot/chat", json=post_data)
                self.assertEqual(res.status_code, 200, res.text)
                data = res.json()
                self.assertEqual(data["provider"], "openrouter")
                self.assertEqual(data["model"], "deepseek/deepseek-r1")
                self.assertEqual(data["content"], "Respuesta copilot con modelo seleccionado")

                # Verificar argumentos pasados a proxy_service
                called_req, called_profile = mock_chat.call_args[0][0], mock_chat.call_args[1].get("profile")
                self.assertEqual(called_req.provider, "openrouter")
                self.assertEqual(called_req.model, "deepseek/deepseek-r1")
                self.assertIsNone(called_profile)
