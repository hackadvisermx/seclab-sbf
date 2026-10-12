import pathlib
import tempfile
import unittest
from unittest.mock import patch

from app.core import database


class TestCopilotRedactEndpoint(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.vault_db_path = pathlib.Path(self.tmp.name) / "vault.db"

        self.db_patch = patch.object(database, "VAULT_DB_PATH", self.vault_db_path)
        self.db_patch.start()
        self.addCleanup(self.db_patch.stop)
        database.init_db()

    def test_copilot_redact_api(self):
        from app.main import app
        from app.api.endpoints import auth
        from fastapi.testclient import TestClient

        auth._attempts.clear()
        with patch.object(auth, "TESTER_PASSWORD", "test-pass"):
            client = TestClient(app)
            login_res = client.post("/api/v1/auth/login", json={"password": "test-pass"})
            self.assertEqual(login_res.status_code, 200)

            sample_text = (
                "Host con clave OpenAI sk-abcdefghijklmnopqrstuvwxyz1234567890 y token Bearer secretToken1234567890abcdef123456. "
                "Conectar con http://admin:P@ssword123@192.168.1.1:8080/admin"
            )
            res = client.post("/api/v1/copilot/redact", json={"text": sample_text})
            self.assertEqual(res.status_code, 200)
            data = res.json()
            self.assertIn("redacted_text", data)
            self.assertIn("replacements_count", data)
            self.assertGreaterEqual(data["replacements_count"], 3)
            self.assertNotIn("sk-abcdefghijklmnopqrstuvwxyz1234567890", data["redacted_text"])
            self.assertNotIn("secretToken1234567890abcdef123456", data["redacted_text"])
            self.assertNotIn("P@ssword123", data["redacted_text"])
            self.assertIn("[REDACTED_API_KEY]", data["redacted_text"])
            self.assertIn("[REDACTED_TOKEN]", data["redacted_text"])
            self.assertIn("[REDACTED_PASSWORD]", data["redacted_text"])
            client.close()
