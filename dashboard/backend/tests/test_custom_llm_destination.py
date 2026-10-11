import asyncio
import pathlib
import tempfile
import unittest
from unittest.mock import patch

from app.core import database
from app.models.schemas import ApiKeyCreate, ChatCompletionRequest, ChatMessage
from app.services.vault_service import vault_service
from app.services.proxy_service import proxy_service
from seclab_network import classify_endpoint


class TestCustomLLMDestinationSecurity(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db_path = pathlib.Path(self.temp.name) / "vault_dest_test.db"
        self.db_patch = patch.object(database, "VAULT_DB_PATH", self.db_path)
        self.db_patch.start()
        self.addCleanup(self.db_patch.stop)
        database.init_db()

        self.vault_service = vault_service
        self.proxy_service = proxy_service

    def test_classify_endpoint_loopback(self):
        loopback_urls = [
            "http://localhost:11434",
            "http://127.0.0.1:8000/v1",
            "http://127.0.0.2:11434",
            "http://0.0.0.0:11434",
            "http://ai.localhost:11434",
            "http://[::1]:11434",
            "localhost:11434",
        ]
        for url in loopback_urls:
            info = classify_endpoint(url)
            self.assertEqual(info["classification"], "LOCAL_LOOPBACK", f"Failed for {url}")
            self.assertTrue(info["is_local"])
            self.assertFalse(info["is_insecure_transport"])
            self.assertIsNone(info["transport_warning"])

    def test_classify_endpoint_private_network(self):
        private_urls = [
            ("http://192.168.1.100:11434", True),
            ("https://192.168.1.100:11434", False),
            ("http://10.0.1.20:8000", True),
            ("http://172.20.0.5:11434", True),
            ("http://host.docker.internal:11434", True),
            ("http://llm-server.local:11434", True),
            ("http://inference.lan:8000", True),
        ]
        for url, expect_insecure in private_urls:
            info = classify_endpoint(url)
            self.assertEqual(info["classification"], "PRIVATE_NETWORK", f"Failed for {url}")
            self.assertTrue(info["is_local"])
            self.assertEqual(info["is_insecure_transport"], expect_insecure)
            if expect_insecure:
                self.assertIsNotNone(info["transport_warning"])

    def test_classify_endpoint_public_remote(self):
        public_urls = [
            ("https://api.openai.com/v1", False),
            ("https://openrouter.ai/api/v1", False),
            ("https://my-company-llm.com/v1", False),
            ("http://external-llm.example.org/v1", True),
            ("http://93.184.216.34:8000/v1", True),
        ]
        for url, expect_insecure in public_urls:
            info = classify_endpoint(url)
            self.assertEqual(info["classification"], "PUBLIC_REMOTE", f"Failed for {url}")
            self.assertFalse(info["is_local"])
            self.assertEqual(info["is_insecure_transport"], expect_insecure)
            if expect_insecure:
                self.assertIn("seguridad crítica", info["transport_warning"])

    def test_vault_list_keys_includes_destination_classification(self):
        self.vault_service.upsert_key(
            ApiKeyCreate(
                provider="custom_llm",
                label="Local Ollama",
                service_type="llm",
                api_key="sk-local-token",
                base_url="http://localhost:11434/v1",
                model_name="llama3:latest",
                is_active=True,
            )
        )
        self.vault_service.upsert_key(
            ApiKeyCreate(
                provider="openai",
                label="OpenAI Cloud",
                service_type="llm",
                api_key="sk-openai-token",
                is_active=True,
            )
        )

        keys = self.vault_service.list_keys()
        key_map = {k.provider: k for k in keys}

        self.assertIn("custom_llm", key_map)
        custom_key = key_map["custom_llm"]
        self.assertEqual(custom_key.destination_classification, "LOCAL_LOOPBACK")
        self.assertFalse(custom_key.is_insecure_transport)

        self.assertIn("openai", key_map)
        openai_key = key_map["openai"]
        self.assertEqual(openai_key.destination_classification, "PUBLIC_REMOTE")
        self.assertFalse(openai_key.is_insecure_transport)

    def test_local_profile_blocks_public_remote_destination(self):
        self.vault_service.upsert_key(
            ApiKeyCreate(
                provider="custom_llm",
                label="Remote Public Endpoint",
                service_type="llm",
                api_key="sk-remote",
                base_url="https://remote-llm.example.com/v1",
                model_name="remote-model",
                is_active=True,
            )
        )

        req = ChatCompletionRequest(
            messages=[ChatMessage(role="user", content="Test prompt")],
        )

        with self.assertRaises(ValueError) as ctx:
            asyncio.run(self.proxy_service.chat_completion(req, profile="local"))

        self.assertIn("destino público remoto", str(ctx.exception))
