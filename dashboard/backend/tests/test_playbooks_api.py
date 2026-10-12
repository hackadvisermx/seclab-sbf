import pathlib
import tempfile
import unittest
from unittest.mock import patch

from app.core import database


class TestPlaybooksAPI(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.vault_db_path = pathlib.Path(self.tmp.name) / "vault.db"

        self.db_patch = patch.object(database, "VAULT_DB_PATH", self.vault_db_path)
        self.db_patch.start()
        self.addCleanup(self.db_patch.stop)
        database.init_db()

    def test_playbooks_api_endpoints(self):
        from app.main import app
        from app.api.endpoints import auth
        from fastapi.testclient import TestClient

        auth._attempts.clear()
        with patch.object(auth, "TESTER_PASSWORD", "test-pass"):
            client = TestClient(app)
            login_res = client.post("/api/v1/auth/login", json={"password": "test-pass"})
            self.assertEqual(login_res.status_code, 200)

            # 1. GET /playbooks
            res = client.get("/api/v1/playbooks")
            self.assertEqual(res.status_code, 200)
            data = res.json()
            self.assertIsInstance(data, list)
            self.assertGreater(len(data), 0)
            pb_ids = [pb["id"] for pb in data]
            self.assertIn("pb_web_recon", pb_ids)

            # 2. GET /playbooks/pb_web_recon
            res = client.get("/api/v1/playbooks/pb_web_recon")
            self.assertEqual(res.status_code, 200)
            pb_data = res.json()
            self.assertTrue(pb_data["is_valid"])
            self.assertEqual(pb_data["playbook"]["id"], "pb_web_recon")
            self.assertGreater(len(pb_data["playbook"]["steps"]), 0)

            # 3. POST /playbooks/validate
            sample_pb = {
                "id": "pb_custom",
                "title": "Custom Test Playbook",
                "version": "1.0",
                "category": "recon",
                "description": "Test",
                "steps": [
                    {
                        "id": "step_1",
                        "title": "Step 1",
                        "objective": "Test",
                        "interaction_type": "passive",
                        "command_template": "echo test",
                        "timeout_seconds": 30,
                    }
                ],
            }
            res = client.post("/api/v1/playbooks/validate", json={"playbook": sample_pb})
            self.assertEqual(res.status_code, 200)
            val_data = res.json()
            self.assertTrue(val_data["is_valid"])
            self.assertEqual(len(val_data["errors"]), 0)

            client.close()


if __name__ == "__main__":
    unittest.main()
