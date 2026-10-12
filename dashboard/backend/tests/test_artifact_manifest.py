import pathlib
import tempfile
import unittest
from unittest.mock import patch

from app.core import database
from app.services.workspace_sync import WorkspaceSyncService


class TestArtifactManifestEndpoint(unittest.TestCase):
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
        self.eng_id = "test-art-manifest"
        self.ws_service.create_engagement(self.eng_id, domain="example.test")
        self.eng_dir = self.ws_service._resolve_dir(self.eng_id)

        # Crear archivos de artefacto
        (self.eng_dir / "notes.md").write_text("Prueba de notas", encoding="utf-8")
        recon_dir = self.eng_dir / "recon"
        recon_dir.mkdir(parents=True, exist_ok=True)
        (recon_dir / "subdomains.txt").write_text("sub.example.test\n", encoding="utf-8")

    def test_get_artifact_manifest_service(self):
        manifest = self.ws_service.get_artifact_manifest(self.eng_id)
        self.assertEqual(manifest["schema_version"], 1)
        self.assertEqual(manifest["engagement_id"], self.eng_id)
        self.assertGreater(manifest["total_artifacts"], 0)
        self.assertGreater(manifest["total_bytes"], 0)

        paths = {a["path"] for a in manifest["artifacts"]}
        self.assertIn("target.yaml", paths)
        self.assertIn("notes.md", paths)
        self.assertIn("recon/subdomains.txt", paths)

        for a in manifest["artifacts"]:
            self.assertEqual(len(a["sha256"]), 64)
            self.assertIn("category", a)
            self.assertIn("size_bytes", a)

    def test_get_artifact_manifest_endpoint(self):
        from app.main import app
        from app.api.endpoints import auth
        from fastapi.testclient import TestClient

        auth._attempts.clear()
        with patch.object(auth, "TESTER_PASSWORD", "test-pass"), \
             patch("app.api.endpoints.loot.workspace_service", self.ws_service):
            client = TestClient(app)
            login_res = client.post("/api/v1/auth/login", json={"password": "test-pass"})
            self.assertEqual(login_res.status_code, 200)

            res = client.get(f"/api/v1/loot/{self.eng_id}/artifacts/manifest?type=engagement")
            self.assertEqual(res.status_code, 200)
            data = res.json()
            self.assertEqual(data["schema_version"], 1)
            self.assertEqual(data["engagement_id"], self.eng_id)
            self.assertGreater(data["total_artifacts"], 0)
            client.close()


if __name__ == "__main__":
    unittest.main()
