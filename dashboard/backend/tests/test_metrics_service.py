import json
import pathlib
import tempfile
import unittest
from unittest.mock import patch

from app.core import database
from app.services.workspace_sync import WorkspaceSyncService


class TestMetricsService(unittest.TestCase):
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
        self.eng_id = "test-metrics-proj"
        self.ws_service.create_engagement(self.eng_id, domain="example.test")
        self.eng_dir = self.ws_service._resolve_dir(self.eng_id)

    def test_metrics_structure(self):
        from app.services.metrics_service import metrics_service

        with patch("app.services.metrics_service.workspace_service", self.ws_service):
            metrics = metrics_service.get_metrics(self.eng_id, "engagement")

            self.assertEqual(metrics["engagement_id"], self.eng_id)
            self.assertIn("audit_readiness_score", metrics)
            self.assertIn("is_fully_audited", metrics)
            self.assertIn("scope", metrics)
            self.assertIn("recon", metrics)
            self.assertIn("findings", metrics)
            self.assertIn("report", metrics)

    def test_metrics_api_endpoint(self):
        from app.main import app
        from app.api.endpoints import auth
        from fastapi.testclient import TestClient

        auth._attempts.clear()
        with patch.object(auth, "TESTER_PASSWORD", "test-pass"), \
             patch("app.services.metrics_service.workspace_service", self.ws_service):
            client = TestClient(app)
            login_res = client.post("/api/v1/auth/login", json={"password": "test-pass"})
            self.assertEqual(login_res.status_code, 200)

            res = client.get(f"/api/v1/engagements/{self.eng_id}/metrics?type=engagement")
            self.assertEqual(res.status_code, 200)
            data = res.json()
            self.assertEqual(data["engagement_id"], self.eng_id)
            self.assertIn("audit_readiness_score", data)
            client.close()

    def test_export_metrics_report(self):
        from app.services.metrics_service import metrics_service

        with patch("app.services.metrics_service.workspace_service", self.ws_service):
            # JSON format
            json_out = metrics_service.export_metrics_report(self.eng_id, "engagement", format="json")
            data = json.loads(json_out)
            self.assertEqual(data["engagement_id"], self.eng_id)
            self.assertIn("audit_readiness_score", data)

            # Markdown format
            md_out = metrics_service.export_metrics_report(self.eng_id, "engagement", format="markdown")
            self.assertIn("# Informe de Métricas Operacionales de Auditoría", md_out)
            self.assertIn("Puntuación de Madurez de Auditoría", md_out)
            self.assertIn("Alcance y Autorización", md_out)

    def test_export_metrics_endpoint(self):
        from app.main import app
        from app.api.endpoints import auth
        from fastapi.testclient import TestClient

        auth._attempts.clear()
        with patch.object(auth, "TESTER_PASSWORD", "test-pass"), \
             patch("app.services.metrics_service.workspace_service", self.ws_service):
            client = TestClient(app)
            login_res = client.post("/api/v1/auth/login", json={"password": "test-pass"})
            self.assertEqual(login_res.status_code, 200)

            # Export JSON
            res_json = client.get(f"/api/v1/engagements/{self.eng_id}/metrics/export?format=json&type=engagement")
            self.assertEqual(res_json.status_code, 200)
            self.assertEqual(res_json.headers["content-type"], "application/json")
            self.assertIn(f"metrics_{self.eng_id}.json", res_json.headers["content-disposition"])

            # Export Markdown
            res_md = client.get(f"/api/v1/engagements/{self.eng_id}/metrics/export?format=markdown&type=engagement")
            self.assertEqual(res_md.status_code, 200)
            self.assertIn("text/markdown", res_md.headers["content-type"])
            self.assertIn(f"metrics_{self.eng_id}.md", res_md.headers["content-disposition"])
            self.assertIn("Puntuación de Madurez de Auditoría", res_md.text)

            client.close()


if __name__ == "__main__":
    unittest.main()
