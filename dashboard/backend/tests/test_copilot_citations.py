import datetime
import hashlib
import json
import pathlib
import tempfile
import unittest
from unittest.mock import patch

from app.core import database
from app.services.workspace_sync import WorkspaceSyncService
from app.services.citations_service import citations_service


class TestCopilotCitations(unittest.TestCase):
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
        self.eng_id = "test-cit-proj"
        self.ws_service.create_engagement(self.eng_id, domain="example.test")
        self.eng_dir = self.ws_service._resolve_dir(self.eng_id)

    def test_extract_file_references(self):
        sample_text = (
            "Basado en el análisis de `evidence/sqli-vuln.md` y los puertos en `recon/nmap.txt`, "
            "además de revisar `target.yaml` y `notes.md`. Ignorar https://external.test/evidence/fake.md "
            "y evitar traversal en `../../etc/passwd` o `../secret.txt`."
        )
        refs = citations_service.extract_file_references(sample_text)
        self.assertIn("evidence/sqli-vuln.md", refs)
        self.assertIn("recon/nmap.txt", refs)
        self.assertIn("target.yaml", refs)
        self.assertIn("notes.md", refs)
        self.assertNotIn("https://external.test/evidence/fake.md", refs)
        self.assertNotIn("../../etc/passwd", refs)
        self.assertNotIn("../secret.txt", refs)

    def test_verify_citations_existing_and_missing(self):
        # Crear archivo real
        recon_dir = self.eng_dir / "recon"
        recon_dir.mkdir(parents=True, exist_ok=True)
        subdomains = recon_dir / "subdomains.txt"
        subdomains.write_text("sub1.example.test\nsub2.example.test\n")
        expected_hash = hashlib.sha256(subdomains.read_bytes()).hexdigest()

        text = "Se encontraron subdominios en `recon/subdomains.txt` pero no en `evidence/missing.md`."

        with patch("app.services.citations_service.workspace_service", self.ws_service):
            citations = citations_service.verify_citations(text, self.eng_id, "engagement")

            cit_map = {c["path"]: c for c in citations}
            self.assertIn("recon/subdomains.txt", cit_map)
            self.assertIn("evidence/missing.md", cit_map)

            # Archivo existente
            sub_cit = cit_map["recon/subdomains.txt"]
            self.assertTrue(sub_cit["exists"])
            self.assertEqual(sub_cit["sha256"], expected_hash)
            self.assertGreater(sub_cit["size"], 0)

            # Archivo ausente
            miss_cit = cit_map["evidence/missing.md"]
            self.assertFalse(miss_cit["exists"])
            self.assertIsNone(miss_cit["sha256"])

    def test_citations_verify_endpoint(self):
        from app.main import app
        from app.api.endpoints import auth
        from fastapi.testclient import TestClient

        auth._attempts.clear()
        with patch.object(auth, "TESTER_PASSWORD", "test-pass"), \
             patch("app.services.citations_service.workspace_service", self.ws_service):
            client = TestClient(app)
            login_res = client.post("/api/v1/auth/login", json={"password": "test-pass"})
            self.assertEqual(login_res.status_code, 200)

            res = client.post(
                "/api/v1/copilot/citations/verify",
                json={
                    "text": "Revisar `target.yaml` para el alcance.",
                    "engagement_id": self.eng_id,
                    "type": "engagement",
                },
            )
            self.assertEqual(res.status_code, 200)
            data = res.json()
            self.assertIsInstance(data, list)
            self.assertEqual(len(data), 1)
            self.assertEqual(data[0]["path"], "target.yaml")
            self.assertTrue(data[0]["exists"])
            client.close()
