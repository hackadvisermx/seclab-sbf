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
                self.assertTrue(data["content"].endswith("Respuesta copilot con modelo seleccionado"))
                self.assertIn("Validación de alcance no disponible", data["content"])

                # Verificar argumentos pasados a proxy_service
                called_req, called_profile = mock_chat.call_args[0][0], mock_chat.call_args[1].get("profile")
                self.assertEqual(called_req.provider, "openrouter")
                self.assertEqual(called_req.model, "deepseek/deepseek-r1")
                self.assertIsNone(called_profile)

    def test_copilot_chat_flags_out_of_scope_and_unknown_suggestions(self):
        """Backlog A20: el copiloto debe validar cada host/URL que sugiera contra
        pt-scope-validator.py antes de mostrar la respuesta, en vez de confiar solo
        en la instrucción de alcance del system prompt."""
        from app.main import app
        from app.api.endpoints import auth
        from fastapi.testclient import TestClient

        auth._attempts.clear()
        with patch.object(auth, "TESTER_PASSWORD", "fixture-password"):
            client = TestClient(app)
            login_resp = client.post("/api/v1/auth/login", json={"password": "fixture-password"})
            self.assertEqual(login_resp.status_code, 200)

            from app.services.workspace_sync import workspace_service
            from app.services.runner_service import runner_service

            mock_dir = pathlib.Path(self.temp.name) / "test_eng_scope"
            mock_dir.mkdir(parents=True, exist_ok=True)
            (mock_dir / "target.yaml").write_text(
                "scope:\n"
                "  in_scope:\n"
                "    domains: ['*.acme.corp']\n"
                "  out_of_scope:\n"
                "    domains: ['partner.acme.corp']\n",
                encoding="utf-8",
            )

            def chat(content):
                mock_resp = ChatCompletionResponse(
                    provider="openrouter",
                    model="deepseek/deepseek-r1",
                    content=content,
                    latency_ms=120,
                    usage={"total_tokens": 50},
                )
                with patch.object(workspace_service, "_resolve_dir", return_value=mock_dir), \
                     patch.object(runner_service, "get_agent_context", return_value="# Mock context"), \
                     patch.object(self.proxy_service, "chat_completion", new_callable=AsyncMock) as mock_chat:
                    mock_chat.return_value = mock_resp
                    post_data = {
                        "engagement_id": "test_eng_scope",
                        "type": "engagement",
                        "agent_id": "triage-agent",
                        "provider": "openrouter",
                        "model": "deepseek/deepseek-r1",
                        "messages": [{"role": "user", "content": "¿Qué pruebo?"}],
                    }
                    res = client.post("/api/v1/copilot/chat", json=post_data)
                    self.assertEqual(res.status_code, 200, res.text)
                    return res.json()["content"]

            # Sugerencia que menciona un host excluido explícitamente: debe advertirse.
            flagged = chat("Prueba https://partner.acme.corp/admin para validar el acceso.")
            self.assertIn("Validación de Alcance (Scope Guard)", flagged)
            self.assertIn("partner.acme.corp", flagged)
            self.assertIn("Prueba https://partner.acme.corp/admin para validar el acceso.", flagged, "el texto original no debe reescribirse, solo anteponerse el aviso")

            # Sugerencia completamente dentro del alcance declarado: sin aviso.
            clean = chat("Prueba https://api.acme.corp/v1/users para validar el acceso.")
            self.assertNotIn("Scope Guard", clean)
            self.assertEqual(clean, "Prueba https://api.acme.corp/v1/users para validar el acceso.")

    def test_normalize_endpoint_url(self):
        from app.services.vault_service import normalize_endpoint_url
        self.assertIsNone(normalize_endpoint_url(None))
        self.assertIsNone(normalize_endpoint_url("   "))
        self.assertEqual(
            normalize_endpoint_url("  https://openrouter.ai/api/v1  "),
            "https://openrouter.ai/api/v1",
        )
        self.assertEqual(
            normalize_endpoint_url("openrouter.ai/api/v1/"),
            "https://openrouter.ai/api/v1",
        )
        self.assertEqual(
            normalize_endpoint_url("localhost:11434/v1/"),
            "http://localhost:11434/v1",
        )
        self.assertEqual(
            normalize_endpoint_url("http://127.0.0.1:8000"),
            "http://127.0.0.1:8000",
        )

    def test_custom_llm_pointing_to_openrouter_probes_auth_key(self):
        from app.models.schemas import ApiKeyCreate
        mock_token = "mock" + "-fixture-token"
        self.vault_service.upsert_key(
            ApiKeyCreate(
                provider="custom_llm",
                label="Custom OpenRouter Endpoint",
                service_type="llm",
                api_key=mock_token,
                base_url="   https://openrouter.ai/api/v1   ",
                model_name="anthropic/claude-3.5-sonnet",
                is_active=True,
            )
        )

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "data": {
                "label": "SecLab-Key",
                "usage": 0.0125,
            }
        }

        async def run_test():
            with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
                mock_get.return_value = mock_resp
                health = await self.vault_service.check_health("custom_llm")
                self.assertEqual(health.provider, "custom_llm")
                self.assertEqual(health.status, "online")
                self.assertIn("vía custom_llm", health.message)
                self.assertIn("0.0125", health.message)

                # Verificar URL limpia enviada
                call_args, call_kwargs = mock_get.call_args
                url = call_args[0]
                self.assertEqual(url, "https://openrouter.ai/api/v1/auth/key")
                headers = call_kwargs["headers"]
                self.assertEqual(headers["Authorization"], f"Bearer {mock_token}")
                self.assertEqual(headers["HTTP-Referer"], "http://localhost:8080")

        import asyncio
        asyncio.run(run_test())

    def test_vault_update_key_modifies_endpoint_and_model(self):
        from app.models.schemas import ApiKeyCreate, ApiKeyUpdate
        mock_token = "mock" + "-fixture-token"
        self.vault_service.upsert_key(
            ApiKeyCreate(
                provider="custom_llm",
                label="Antiguo Label",
                service_type="llm",
                api_key=mock_token,
                base_url="http://localhost:11434",
                model_name="mistral",
                is_active=True,
            )
        )

        # Actualizar base_url y model_name
        updated = self.vault_service.update_key(
            "custom_llm",
            ApiKeyUpdate(
                label="Open Router Actualizado",
                base_url="  https://openrouter.ai/api/v1  ",
                model_name="anthropic/claude-3.5-sonnet",
                is_active=True,
            )
        )
        self.assertIsNotNone(updated)
        self.assertEqual(updated.label, "Open Router Actualizado")
        self.assertEqual(updated.base_url, "https://openrouter.ai/api/v1")
        self.assertEqual(updated.model_name, "anthropic/claude-3.5-sonnet")
        self.assertEqual(updated.status, "untested")
        self.assertIn("pendiente de verificación", updated.status_message)

    def test_openrouter_request_resolves_when_stored_under_custom_llm(self):
        from app.models.schemas import ApiKeyCreate
        mock_token = "mock" + "-fixture-token"
        # La clave fue guardada como 'custom_llm' con base_url de openrouter
        self.vault_service.upsert_key(
            ApiKeyCreate(
                provider="custom_llm",
                label="Open Router",
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
            "choices": [{"message": {"content": "Respuesta vía OpenRouter interoperable"}}],
            "usage": {"total_tokens": 55},
        }

        # La petición explícitamente solicita provider="openrouter" (como hace ChatView.vue)
        req = ChatCompletionRequest(
            messages=[ChatMessage(role="user", content="Hola")],
            provider="openrouter",
            model="anthropic/claude-3.5-sonnet",
        )

        async def run_test():
            with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
                mock_post.return_value = mock_resp
                res = await self.proxy_service.chat_completion(req)
                self.assertEqual(res.provider, "openrouter")
                self.assertEqual(res.content, "Respuesta vía OpenRouter interoperable")

                # Verificar llamada
                call_args, call_kwargs = mock_post.call_args
                url = call_args[0]
                self.assertEqual(url, "https://openrouter.ai/api/v1/chat/completions")
                headers = call_kwargs["headers"]
                self.assertEqual(headers["Authorization"], f"Bearer {mock_token}")
                self.assertEqual(headers["HTTP-Referer"], "http://localhost:8080")

        import asyncio
        asyncio.run(run_test())


    def test_user_catalog_is_authenticated_complete_and_uses_saved_key(self):
        import asyncio
        from app.models.schemas import ApiKeyCreate
        self.vault_service.upsert_key(ApiKeyCreate(provider="custom_llm", label="Router", service_type="llm", api_key="fixture-token", base_url=" https://openrouter.ai/api/v1/chat/completions ", model_name="vendor/new"))
        response = MagicMock(status_code=200)
        response.json.return_value = {"data": [{"id": f"vendor/model-{i}", "name": f"Model {i}"} for i in range(150)]}
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=response) as get:
            result = asyncio.run(self.vault_service.list_models("openrouter"))
        self.assertEqual(len(result["models"]), 150)
        self.assertEqual(result["default_model"], "vendor/new")
        self.assertEqual(get.call_args.args[0], "https://openrouter.ai/api/v1/models/user")
        self.assertEqual(get.call_args.kwargs["headers"]["Authorization"], "Bearer fixture-token")
        self.assertNotIn("fixture-token", str(result))
        self.assertEqual(self.vault_service.list_keys()[0].provider, "custom_llm")

    def test_catalog_preview_does_not_store_key_or_change_default(self):
        import asyncio
        response = MagicMock(status_code=200)
        response.json.return_value = {"data": [{"id": "vendor/new", "name": "Nuevo"}]}
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=response):
            result = asyncio.run(self.vault_service.list_models("openrouter", "fixture-preview"))
        self.assertEqual(result["models"][0]["id"], "vendor/new")
        self.assertEqual(self.vault_service.list_keys(), [])

    def test_catalog_rejects_misleading_hosts_before_sending_key(self):
        import asyncio
        from app.services.vault_service import is_openrouter_url
        for url in ("https://openrouter.ai.evil.example", "https://evil.example/openrouter.ai", "http://openrouter.ai", "https://user@openrouter.ai"):
            with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as get:
                with self.assertRaises(ValueError):
                    asyncio.run(self.vault_service.list_models("openrouter", "fixture-token", url))
                get.assert_not_called()
        self.assertFalse(is_openrouter_url("https://evil.example/openrouter.ai"))

    def test_catalog_denied_or_malformed_does_not_show_public_presets(self):
        import asyncio
        for status, data in ((403, {}), (200, {"data": "invalid"})):
            response = MagicMock(status_code=status)
            response.json.return_value = data
            with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=response):
                with self.assertRaises(RuntimeError):
                    asyncio.run(self.vault_service.list_models("openrouter", "fixture-token"))

    def test_openai_catalog_uses_v1_models_and_falls_back_id_as_name(self):
        """El catálogo de OpenAI no es exclusivo de OpenRouter (backlog: poder
        probar/precargar modelos para 'cualquier proveedor', no solo OpenRouter)."""
        import asyncio
        response = MagicMock(status_code=200)
        response.json.return_value = {"data": [{"id": "gpt-4o"}, {"id": "gpt-4o-mini"}]}
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=response) as get:
            result = asyncio.run(self.vault_service.list_models("openai", "fixture-token"))
        self.assertEqual(get.call_args.args[0], "https://api.openai.com/v1/models")
        self.assertEqual(get.call_args.kwargs["headers"]["Authorization"], "Bearer fixture-token")
        ids = [m["id"] for m in result["models"]]
        self.assertIn("gpt-4o", ids)
        self.assertIn("gpt-4o-mini", ids)
        # Sin "name" en la respuesta real de OpenAI: debe usar el id como nombre.
        self.assertEqual(next(m for m in result["models"] if m["id"] == "gpt-4o")["name"], "gpt-4o")

    def test_openai_catalog_respects_custom_base_url(self):
        import asyncio
        response = MagicMock(status_code=200)
        response.json.return_value = {"data": [{"id": "gpt-4o"}]}
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=response) as get:
            asyncio.run(self.vault_service.list_models("openai", "fixture-token", "https://proxy.internal/v1/"))
        self.assertEqual(get.call_args.args[0], "https://proxy.internal/v1/models")

    def test_anthropic_catalog_uses_x_api_key_and_display_name(self):
        import asyncio
        response = MagicMock(status_code=200)
        response.json.return_value = {"data": [{"id": "claude-3-5-sonnet-20241022", "display_name": "Claude 3.5 Sonnet"}]}
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=response) as get:
            result = asyncio.run(self.vault_service.list_models("anthropic", "fixture-token"))
        self.assertEqual(get.call_args.args[0], "https://api.anthropic.com/v1/models")
        headers = get.call_args.kwargs["headers"]
        self.assertEqual(headers["x-api-key"], "fixture-token")
        self.assertEqual(headers["anthropic-version"], "2023-06-01")
        self.assertNotIn("Authorization", headers, "Anthropic usa x-api-key, no Bearer")
        self.assertEqual(result["models"][0], {"id": "claude-3-5-sonnet-20241022", "name": "Claude 3.5 Sonnet"})

    def test_gemini_catalog_strips_models_prefix_and_drops_non_chat_models(self):
        import asyncio
        response = MagicMock(status_code=200)
        response.json.return_value = {
            "models": [
                {"name": "models/gemini-2.0-flash", "displayName": "Gemini 2.0 Flash", "supportedGenerationMethods": ["generateContent"]},
                {"name": "models/embedding-001", "displayName": "Embedding 001", "supportedGenerationMethods": ["embedContent"]},
            ]
        }
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=response) as get:
            result = asyncio.run(self.vault_service.list_models("gemini", "fixture-key"))
        self.assertEqual(get.call_args.args[0], "https://generativelanguage.googleapis.com/v1beta/models")
        self.assertEqual(get.call_args.kwargs["params"], {"key": "fixture-key"})
        self.assertEqual(len(result["models"]), 1, "El modelo de solo-embeddings no sirve como modelo de chat inicial")
        self.assertEqual(result["models"][0], {"id": "gemini-2.0-flash", "name": "Gemini 2.0 Flash"})

    def test_custom_llm_catalog_requires_base_url_and_uses_openai_compatible_endpoint(self):
        import asyncio
        with self.assertRaises(ValueError):
            asyncio.run(self.vault_service.list_models("custom_llm", "fixture-token", ""))

        response = MagicMock(status_code=200)
        response.json.return_value = {"data": [{"id": "llama3:latest"}]}
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=response) as get:
            result = asyncio.run(self.vault_service.list_models("custom_llm", "fixture-token", "http://localhost:11434/v1"))
        self.assertEqual(get.call_args.args[0], "http://localhost:11434/v1/models")
        self.assertEqual(result["models"][0]["id"], "llama3:latest")

    def test_custom_llm_pointing_at_openrouter_still_uses_openrouter_catalog(self):
        """Un custom_llm cuyo base_url es openrouter.ai debe seguir usando el
        catálogo real de OpenRouter (/models/user), no el genérico /models."""
        import asyncio
        response = MagicMock(status_code=200)
        response.json.return_value = {"data": [{"id": "vendor/model", "name": "Modelo"}]}
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=response) as get:
            asyncio.run(self.vault_service.list_models("custom_llm", "fixture-token", "https://openrouter.ai/api/v1"))
        self.assertEqual(get.call_args.args[0], "https://openrouter.ai/api/v1/models/user")

    def test_unsupported_provider_raises_clear_error(self):
        import asyncio
        with self.assertRaises(ValueError):
            asyncio.run(self.vault_service.list_models("shodan", "fixture-token"))

    def test_local_label_does_not_alias_to_router_and_inactive_key_is_rejected(self):
        import asyncio
        from app.models.schemas import ApiKeyCreate, ApiKeyUpdate
        self.vault_service.upsert_key(ApiKeyCreate(provider="custom_llm", label="Open Router", service_type="llm", api_key="fixture-token", base_url="http://localhost:11434/v1"))
        self.assertIsNone(self.vault_service.get_key_entry("openrouter"))
        self.vault_service.update_key("custom_llm", ApiKeyUpdate(base_url="https://openrouter.ai/api/v1", is_active=False))
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as post:
            with self.assertRaises(ValueError):
                asyncio.run(self.proxy_service._dispatch_single_provider("openrouter", ChatCompletionRequest(messages=[ChatMessage(role="user", content="Hola")], model="vendor/new")))
            post.assert_not_called()

    def test_openrouter_profile_never_sends_ollama_model(self):
        import asyncio
        from app.models.schemas import ApiKeyCreate
        self.vault_service.upsert_key(ApiKeyCreate(provider="custom_llm", label="Router", service_type="llm", api_key="fixture-token", base_url="https://openrouter.ai/api/v1", model_name="llama3:latest"))
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as post:
            with self.assertRaisesRegex(RuntimeError, "catálogo"):
                asyncio.run(self.proxy_service.chat_completion(ChatCompletionRequest(messages=[ChatMessage(role="user", content="Hola")]), profile="quick"))
            post.assert_not_called()

    def test_embedded_upstream_error_and_empty_reply_are_reported_without_key(self):
        import asyncio
        from app.models.schemas import ApiKeyCreate
        self.vault_service.upsert_key(ApiKeyCreate(provider="openrouter", label="Router", service_type="llm", api_key="fixture-token", model_name="vendor/new"))
        req = ChatCompletionRequest(messages=[ChatMessage(role="user", content="Hola")], provider="openrouter")
        for data, expected in (({"error": {"message": "saldo insuficiente fixture-token"}}, "saldo insuficiente"), ({"choices": [{"message": {"content": None}}]}, "sin contenido")):
            response = MagicMock(status_code=200)
            response.json.return_value = data
            with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=response):
                with self.assertRaisesRegex(RuntimeError, expected) as exc:
                    asyncio.run(self.proxy_service.chat_completion(req))
            self.assertNotIn("fixture-token", str(exc.exception))

    def test_update_key_reclassifies_provider_and_rejects_collision(self):
        # Fase 102: ApiKeyUpdate.provider permite mover una clave existente a
        # otro nombre de proveedor (p. ej. custom_llm -> openrouter) sin
        # borrar y volver a crearla.
        from app.models.schemas import ApiKeyCreate, ApiKeyUpdate

        self.vault_service.upsert_key(
            ApiKeyCreate(
                provider="custom_llm",
                label="Open Router",
                service_type="llm",
                api_key="fixture-token-a",
                base_url="https://openrouter.ai/api/v1",
                model_name="vendor/a",
                is_active=True,
            )
        )
        updated = self.vault_service.update_key("custom_llm", ApiKeyUpdate(provider="openrouter"))
        self.assertEqual(updated.provider, "openrouter")
        self.assertIsNone(self.vault_service.get_key_entry("custom_llm"))
        self.assertEqual(self.vault_service.get_key_entry("openrouter")["label"], "Open Router")

        # Colision: ya existe una fila 'openrouter', reclasificar otra clave
        # hacia ese mismo proveedor debe rechazarse con un error claro (no un
        # error de sqlite por operar sobre la conexion ya cerrada).
        self.vault_service.upsert_key(
            ApiKeyCreate(
                provider="custom_llm",
                label="Otra clave",
                service_type="llm",
                api_key="fixture-token-b",
                model_name="vendor/b",
                is_active=True,
            )
        )
        with self.assertRaisesRegex(ValueError, "Ya existe una clave para el proveedor elegido"):
            self.vault_service.update_key("custom_llm", ApiKeyUpdate(provider="openrouter"))
        # La clave 'custom_llm' original debe seguir intacta tras el rechazo.
        self.assertEqual(self.vault_service.get_key_entry("custom_llm")["label"], "Otra clave")

    def test_explicit_custom_llm_without_key_does_not_use_openrouter(self):
        import asyncio
        from app.models.schemas import ApiKeyCreate

        self.vault_service.upsert_key(
            ApiKeyCreate(
                provider="openrouter",
                label="OpenRouter nativo",
                service_type="llm",
                api_key="fixture-token",
                model_name="vendor/native",
                is_active=True,
            )
        )
        self.assertIsNone(self.vault_service.get_key_entry("custom_llm"))

        mock_resp = MagicMock(status_code=200)
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": "Respuesta via fallback a openrouter"}}],
            "usage": {"total_tokens": 12},
        }
        req = ChatCompletionRequest(messages=[ChatMessage(role="user", content="Hola")], provider="custom_llm")

        async def run_test():
            with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_resp) as mock_post:
                with self.assertRaises(RuntimeError):
                    await self.proxy_service.chat_completion(req)
                mock_post.assert_not_called()

        asyncio.run(run_test())
