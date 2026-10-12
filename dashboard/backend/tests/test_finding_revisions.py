import hashlib
import pathlib
import tempfile
import unittest
from unittest.mock import patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.api.endpoints import findings
from app.models.schemas import FindingCreate
from app.services.workspace_sync import WorkspaceSyncService


class TestFindingRevisions(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.service = WorkspaceSyncService(pathlib.Path(temporary.name))
        self.service.create_engagement('test_eng', domain='example.test')
        app = FastAPI()
        app.include_router(findings.router)
        self.client = TestClient(app, base_url="http://localhost")
        self.addCleanup(self.client.close)
        patcher = patch.object(findings, 'workspace_service', self.service)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_revisions_logged_on_create_update_and_delete(self):
        # 1. Crear hallazgo
        create_res = self.client.post('/findings/test_eng', json={
            "slug": "sqli_test",
            "title": "SQL Injection en Login",
            "severity": "CRITICAL",
            "status": "CANDIDATE",
            "asset": "example.test"
        })
        self.assertEqual(create_res.status_code, 200, create_res.text)
        created_finding = create_res.json()
        sha1 = created_finding["source_sha256"]

        # Consultar revisiones
        rev_res1 = self.client.get('/findings/test_eng/sqli_test/revisions')
        self.assertEqual(rev_res1.status_code, 200)
        data1 = rev_res1.json()
        self.assertEqual(data1["total_revisions"], 1)
        rev1 = data1["revisions"][0]
        self.assertEqual(rev1["action"], "create")
        self.assertIsNone(rev1["previous_sha256"])
        self.assertEqual(rev1["new_sha256"], sha1)
        self.assertEqual(rev1["title"], "SQL Injection en Login")
        self.assertEqual(rev1["severity"], "CRITICAL")

        # 2. Actualizar hallazgo
        update_res = self.client.post('/findings/test_eng', json={
            "slug": "sqli_test",
            "title": "SQL Injection en Login (Actualizado)",
            "severity": "CRITICAL",
            "status": "CANDIDATE",
            "asset": "example.test",
            "body": "## Descripción\nActualizado con nuevos detalles técnicos.",
            "expected_source_sha256": sha1
        })
        self.assertEqual(update_res.status_code, 200, update_res.text)
        updated_finding = update_res.json()
        sha2 = updated_finding["source_sha256"]
        self.assertNotEqual(sha1, sha2)

        # Consultar revisiones tras update
        rev_res2 = self.client.get('/findings/test_eng/sqli_test/revisions')
        self.assertEqual(rev_res2.status_code, 200)
        data2 = rev_res2.json()
        self.assertEqual(data2["total_revisions"], 2)
        rev2 = data2["revisions"][1]
        self.assertEqual(rev2["action"], "update")
        self.assertEqual(rev2["previous_sha256"], sha1)
        self.assertEqual(rev2["new_sha256"], sha2)
        self.assertEqual(rev2["title"], "SQL Injection en Login (Actualizado)")
        self.assertEqual(rev2["severity"], "CRITICAL")
        self.assertIn("severity", rev2["modified_fields"])

        # 3. Eliminar hallazgo
        del_res = self.client.delete(f'/findings/test_eng/sqli_test?expected_source_sha256={sha2}')
        self.assertEqual(del_res.status_code, 200)

        # Consultar revisiones tras delete (conserva auditoría)
        rev_res3 = self.client.get('/findings/test_eng/sqli_test/revisions')
        self.assertEqual(rev_res3.status_code, 200)
        data3 = rev_res3.json()
        self.assertEqual(data3["total_revisions"], 3)
        rev3 = data3["revisions"][2]
        self.assertEqual(rev3["action"], "delete")
        self.assertEqual(rev3["previous_sha256"], sha2)
        self.assertIsNone(rev3["new_sha256"])

        # 4. Asegurar que list_findings no se corrompe por .revisions
        findings_list = self.client.get('/findings/test_eng').json()
        self.assertEqual(len(findings_list), 0)


if __name__ == "__main__":
    unittest.main()
