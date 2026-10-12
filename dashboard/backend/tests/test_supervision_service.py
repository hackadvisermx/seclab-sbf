import pathlib
import tempfile
import unittest
from unittest.mock import patch

from app.core import database
from app.services.workspace_sync import WorkspaceSyncService


class TestSupervisionService(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.ws_dir = pathlib.Path(self.tmp.name) / "workspace"
        self.vault_db_path = pathlib.Path(self.tmp.name) / "vault.db"

        self.db_patch = patch.object(database, "VAULT_DB_PATH", self.vault_db_path)
        self.db_patch.start()
        self.addCleanup(self.db_patch.stop)
        database.init_db()

        self.ws_service = WorkspaceSyncService(self.ws_dir)
        self.eng_id = "test-sup-proj"
        self.ws_service.create_engagement(self.eng_id, domain="example.test")
        self.eng_dir = self.ws_service._resolve_dir(self.eng_id)

    def test_supervision_state_structure(self):
        from app.services.supervision_service import supervision_service

        with patch("app.services.supervision_service.workspace_service", self.ws_service), \
             patch("app.services.supervision_service.recon_service.store.history", return_value={"jobs": []}):
            state = supervision_service.get_supervision_state(self.eng_id, "engagement")

            self.assertEqual(state["engagement_id"], self.eng_id)
            self.assertEqual(state["type"], "engagement")
            self.assertIn("current_stage", state)
            self.assertIn("scope", state)
            self.assertIn("recon", state)
            self.assertIn("findings", state)
            self.assertIn("checkpoints", state)
            self.assertEqual(len(state["checkpoints"]), 4)

            # Checkpoint IDs
            cp_ids = [cp["id"] for cp in state["checkpoints"]]
            self.assertIn("cp_scope", cp_ids)
            self.assertIn("cp_recon", cp_ids)
            self.assertIn("cp_evidence", cp_ids)
            self.assertIn("cp_report", cp_ids)

    def test_supervision_api_endpoint(self):
        from app.main import app
        from app.api.endpoints import auth
        from fastapi.testclient import TestClient

        auth._attempts.clear()
        with patch.object(auth, "TESTER_PASSWORD", "test-pass"), \
             patch("app.services.supervision_service.workspace_service", self.ws_service), \
             patch("app.services.supervision_service.recon_service.store.history", return_value={"jobs": []}):
            client = TestClient(app)
            login_res = client.post("/api/v1/auth/login", json={"password": "test-pass"})
            self.assertEqual(login_res.status_code, 200)

            res = client.get(f"/api/v1/engagements/{self.eng_id}/supervision?type=engagement")
            self.assertEqual(res.status_code, 200)
            data = res.json()
            self.assertEqual(data["engagement_id"], self.eng_id)
            self.assertIn("checkpoints", data)
            client.close()


if __name__ == "__main__":
    unittest.main()
