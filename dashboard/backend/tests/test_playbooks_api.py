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

            # 4. POST /playbooks/pb_web_recon/run (dry-run)
            res = client.post(
                "/api/v1/playbooks/pb_web_recon/run",
                json={"dry_run": True, "parameters": {"target": "example.com"}},
            )
            self.assertEqual(res.status_code, 200)
            run_data = res.json()
            self.assertEqual(run_data["playbook_id"], "pb_web_recon")
            self.assertTrue(run_data["dry_run"])
            self.assertEqual(run_data["status"], "SIMULATED")
            self.assertGreater(len(run_data["steps_results"]), 0)

            client.close()

    def test_playbooks_api_security_enforcement(self):
        from app.main import app
        from app.api.endpoints import auth, playbooks
        from fastapi.testclient import TestClient

        ws_dir = pathlib.Path(self.tmp.name) / "workspace"
        eng_dir = ws_dir / "engagements" / "test-eng"
        eng_dir.mkdir(parents=True)
        (ws_dir / "retos").mkdir(parents=True)

        auth._attempts.clear()
        with patch.object(auth, "TESTER_PASSWORD", "test-pass"), \
             patch.object(playbooks, "WORKSPACE_DIR", ws_dir):
            client = TestClient(app)
            login_res = client.post("/api/v1/auth/login", json={"password": "test-pass"})
            self.assertEqual(login_res.status_code, 200)

            # B1: Ejecución real sin engagement_id rechazada
            res = client.post("/api/v1/playbooks/pb_web_recon/run", json={"dry_run": False})
            self.assertEqual(res.status_code, 400)
            self.assertIn("engagement_id", res.json()["detail"])

            # B1: Ejecución de paso real sin engagement_id rechazada
            res = client.post(
                "/api/v1/playbooks/pb_web_recon/step/run",
                json={"step_id": "step_01_subdomain_discovery", "dry_run": False},
            )
            self.assertEqual(res.status_code, 400)
            self.assertIn("engagement_id", res.json()["detail"])

            # M2: Path traversal en engagement_id rechazado (400)
            res = client.post(
                "/api/v1/playbooks/pb_web_recon/run",
                json={"engagement_id": "../../etc", "dry_run": False},
            )
            self.assertEqual(res.status_code, 400)

            res = client.get("/api/v1/playbooks?engagement_id=../../etc")
            self.assertEqual(res.status_code, 400)

            # B1: Ejecución real con engagement sin target.yaml rechazada
            res = client.post(
                "/api/v1/playbooks/pb_web_recon/run",
                json={"engagement_id": "test-eng", "dry_run": False},
            )
            self.assertEqual(res.status_code, 400)
            self.assertIn("target.yaml", res.json()["detail"])

            # B3: target_selector con parámetro fuera de alcance bloqueado por Scope Guard
            target_yaml = eng_dir / "target.yaml"
            target_yaml.write_text(
                "version: '1.0'\n"
                "scope:\n"
                "  in_scope:\n"
                "    domains: ['target.local']\n"
                "    ips: []\n"
                "    cidrs: []\n"
                "    endpoints: []\n"
                "  out_of_scope:\n"
                "    domains: ['evil.com']\n"
                "    ips: []\n"
                "    cidrs: []\n"
                "    notes: []\n"
                "authorization:\n"
                "  reference: 'AUT-001'\n"
                "  valid_from: '2026-10-01T00:00:00.000Z'\n"
                "  valid_until: '2026-10-31T23:59:59.000Z'\n"
                "  allow_passive: true\n"
                "  allow_active: true\n"
            )

            # Ejecutar playbook con domain fuera de alcance (evil.com) -> Bloqueado a nivel playbook
            res = client.post(
                "/api/v1/playbooks/pb_web_recon/run",
                json={
                    "engagement_id": "test-eng",
                    "parameters": {"domain": "evil.com"},
                    "dry_run": False,
                },
            )
            self.assertEqual(res.status_code, 200)
            run_res = res.json()
            self.assertEqual(run_res["status"], "BLOCKED")
            self.assertFalse(run_res["can_execute"])

            # Ejecutar paso individual con domain fuera de alcance (evil.com) -> Bloqueado a nivel paso
            res_step = client.post(
                "/api/v1/playbooks/pb_web_recon/step/run",
                json={
                    "engagement_id": "test-eng",
                    "step_id": "step_01_subdomain_discovery",
                    "parameters": {"domain": "evil.com"},
                    "dry_run": False,
                },
            )
            self.assertEqual(res_step.status_code, 200)
            step_res = res_step.json()["step_result"]
            self.assertEqual(step_res["status"], "BLOCKED")
            self.assertEqual(step_res["exit_code"], 126)
            self.assertIn("evil.com", step_res["output"])
            self.assertIn("Scope Guard", step_res["output"])

            # B3: Selector basado en archivo (recon/subdomains.txt) con destino fuera de alcance
            recon_dir = eng_dir / "recon"
            recon_dir.mkdir(parents=True, exist_ok=True)
            (recon_dir / "subdomains.txt").write_text("evil.com\n", encoding="utf-8")
            res_file_step = client.post(
                "/api/v1/playbooks/pb_web_recon/step/run",
                json={
                    "engagement_id": "test-eng",
                    "step_id": "step_02_web_probing",
                    "dry_run": False,
                },
            )
            self.assertEqual(res_file_step.status_code, 200)
            file_step_res = res_file_step.json()["step_result"]
            self.assertEqual(file_step_res["status"], "BLOCKED")
            self.assertEqual(file_step_res["exit_code"], 126)
            self.assertIn("evil.com", file_step_res["output"])

            # B2: Autorización incompleta (falta reference y vigencia) bloquea la ejecución
            target_yaml.write_text(
                "version: '1.0'\n"
                "scope:\n"
                "  in_scope:\n"
                "    domains: ['target.local']\n"
                "    ips: []\n"
                "    cidrs: []\n"
                "    endpoints: []\n"
                "  out_of_scope:\n"
                "    domains: []\n"
                "    ips: []\n"
                "    cidrs: []\n"
                "    notes: []\n"
                "authorization:\n"
                "  allow_passive: true\n"
                "  allow_active: true\n"
            )
            res_incomp = client.post(
                "/api/v1/playbooks/pb_web_recon/run",
                json={
                    "engagement_id": "test-eng",
                    "parameters": {"domain": "target.local"},
                    "dry_run": False,
                },
            )
            self.assertEqual(res_incomp.status_code, 200)
            self.assertEqual(res_incomp.json()["status"], "BLOCKED")
            self.assertFalse(res_incomp.json()["can_execute"])

            # B3: Autorización válida pero sin sección scope bloquea ejecución real (/run y /step/run)
            target_yaml.write_text(
                "authorization:\n"
                "  reference: 'AUT-VALID'\n"
                "  valid_from: '2026-10-01T00:00:00.000Z'\n"
                "  valid_until: '2026-10-31T23:59:59.000Z'\n"
                "  allow_passive: true\n"
                "  allow_active: true\n"
            )
            res_no_scope_run = client.post(
                "/api/v1/playbooks/pb_web_recon/run",
                json={
                    "engagement_id": "test-eng",
                    "parameters": {"domain": "target.local"},
                    "dry_run": False,
                },
            )
            self.assertEqual(res_no_scope_run.status_code, 200)
            self.assertEqual(res_no_scope_run.json()["status"], "BLOCKED")
            self.assertFalse(res_no_scope_run.json()["can_execute"])

            res_no_scope_step = client.post(
                "/api/v1/playbooks/pb_web_recon/step/run",
                json={
                    "engagement_id": "test-eng",
                    "step_id": "step_01_subdomain_discovery",
                    "parameters": {"domain": "target.local"},
                    "dry_run": False,
                },
            )
            self.assertEqual(res_no_scope_step.status_code, 200)
            step_blocked = res_no_scope_step.json()["step_result"]
            self.assertEqual(step_blocked["status"], "BLOCKED")
            self.assertEqual(step_blocked["exit_code"], 126)

            # B3: Autorización válida pero scope malformado bloquea ejecución real
            target_yaml.write_text(
                "scope: 'not-a-valid-dict'\n"
                "authorization:\n"
                "  reference: 'AUT-VALID'\n"
                "  valid_from: '2026-10-01T00:00:00.000Z'\n"
                "  valid_until: '2026-10-31T23:59:59.000Z'\n"
                "  allow_passive: true\n"
                "  allow_active: true\n"
            )
            # M4: Endpoint /validate, /run y /step/run con {domain} sin parámetros falla cerrado
            target_yaml.write_text(
                "version: '1.0'\n"
                "scope:\n"
                "  in_scope:\n"
                "    domains: ['target.local']\n"
                "    ips: []\n"
                "    cidrs: []\n"
                "    endpoints: []\n"
                "  out_of_scope:\n"
                "    domains: []\n"
                "    ips: []\n"
                "    cidrs: []\n"
                "    notes: []\n"
                "authorization:\n"
                "  reference: 'AUT-VALID'\n"
                "  valid_from: '2026-10-01T00:00:00.000Z'\n"
                "  valid_until: '2026-10-31T23:59:59.000Z'\n"
                "  allow_passive: true\n"
                "  allow_active: true\n"
            )
            pb_active_no_param = {
                "id": "pb_active_no_param",
                "title": "Playbook Activo Sin Parámetro",
                "version": "1.0",
                "category": "recon",
                "description": "Prueba API M4",
                "steps": [
                    {
                        "id": "step_active_placeholder",
                        "title": "Paso Activo",
                        "objective": "Verificar bloqueo estático",
                        "interaction_type": "active_low",
                        "command_template": "curl https://{domain}",
                        "timeout_seconds": 30,
                    }
                ],
            }
            # /validate con engagement_id y sin parámetros
            res_val_no_param = client.post(
                "/api/v1/playbooks/validate",
                json={
                    "playbook": pb_active_no_param,
                    "engagement_id": "test-eng",
                },
            )
            self.assertEqual(res_val_no_param.status_code, 200)
            scope_eval = res_val_no_param.json()["scope_evaluation"]
            self.assertFalse(scope_eval["can_execute"])
            self.assertEqual(scope_eval["steps_evaluation"][0]["status"], "BLOCKED")

            # /step/run con paso activo sin parámetro
            res_step_no_param = client.post(
                "/api/v1/playbooks/pb_web_recon/step/run",
                json={
                    "engagement_id": "test-eng",
                    "step_id": "step_02_web_probing",
                    "parameters": {},
                    "dry_run": False,
                },
            )
            self.assertEqual(res_step_no_param.status_code, 200)
            step_res_no_param = res_step_no_param.json()["step_result"]
            self.assertEqual(step_res_no_param["status"], "BLOCKED")
            self.assertEqual(step_res_no_param["exit_code"], 126)

            client.close()


if __name__ == "__main__":
    unittest.main()
