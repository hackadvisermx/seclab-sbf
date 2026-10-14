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

            # B3 API: Playbook con bandera proxy no autorizada (-x evil.com) bloquea estáticamente
            pb_proxy_api = {
                "id": "pb_proxy_api",
                "title": "Playbook Proxy API",
                "version": "1.0",
                "category": "recon",
                "description": "Prueba API B3 proxy",
                "steps": [
                    {
                        "id": "step_proxy_call",
                        "title": "Paso Proxy",
                        "objective": "Verificar bloqueo de proxy fuera de alcance",
                        "interaction_type": "active_low",
                        "command_template": "curl -x evil.com https://target.local",
                        "timeout_seconds": 30,
                    }
                ],
            }
            res_val_proxy = client.post(
                "/api/v1/playbooks/validate",
                json={"playbook": pb_proxy_api, "engagement_id": "test-eng"},
            )
            self.assertEqual(res_val_proxy.status_code, 200)
            self.assertFalse(res_val_proxy.json()["scope_evaluation"]["can_execute"])
            self.assertEqual(res_val_proxy.json()["scope_evaluation"]["steps_evaluation"][0]["status"], "BLOCKED")

            # M4 API: Playbook mixto ({domain} sin valor + target.local autorizado)
            pb_mixed_api = {
                "id": "pb_mixed_api",
                "title": "Playbook Mixto API",
                "version": "1.0",
                "category": "recon",
                "description": "Prueba API M4 placeholders mixtos",
                "steps": [
                    {
                        "id": "step_mixed_call",
                        "title": "Paso Mixto",
                        "objective": "Verificar bloqueo de placeholder no expandido",
                        "interaction_type": "active_low",
                        "command_template": "curl https://{domain} target.local",
                        "timeout_seconds": 30,
                    }
                ],
            }
            # Sin parámetro domain: DEBE bloquear
            res_val_mixed = client.post(
                "/api/v1/playbooks/validate",
                json={"playbook": pb_mixed_api, "engagement_id": "test-eng"},
            )
            self.assertEqual(res_val_mixed.status_code, 200)
            self.assertFalse(res_val_mixed.json()["scope_evaluation"]["can_execute"])
            self.assertEqual(res_val_mixed.json()["scope_evaluation"]["steps_evaluation"][0]["status"], "BLOCKED")

            # Con parámetro domain autorizado: DEBE autorizar
            res_val_mixed_ok = client.post(
                "/api/v1/playbooks/validate",
                json={
                    "playbook": pb_mixed_api,
                    "engagement_id": "test-eng",
                    "parameters": {"domain": "target.local"},
                },
            )
            self.assertEqual(res_val_mixed_ok.status_code, 200)
            self.assertTrue(res_val_mixed_ok.json()["scope_evaluation"]["can_execute"])
            self.assertEqual(res_val_mixed_ok.json()["scope_evaluation"]["steps_evaluation"][0]["status"], "AUTHORIZED")

            # B3 API: Sensibilidad a mayúsculas con -X POST no extrae POST como host y autoriza
            pb_method_api = {
                "id": "pb_method_api",
                "title": "Playbook Method POST API",
                "version": "1.0",
                "category": "recon",
                "description": "Prueba API método POST",
                "steps": [
                    {
                        "id": "step_post_call",
                        "title": "Paso POST",
                        "objective": "Verificar que POST no sea host",
                        "interaction_type": "active_low",
                        "command_template": "curl -X POST https://target.local",
                        "timeout_seconds": 30,
                    }
                ],
            }
            res_val_method = client.post(
                "/api/v1/playbooks/validate",
                json={"playbook": pb_method_api, "engagement_id": "test-eng"},
            )
            self.assertEqual(res_val_method.status_code, 200)
            self.assertTrue(res_val_method.json()["scope_evaluation"]["can_execute"])
            self.assertEqual(res_val_method.json()["scope_evaluation"]["steps_evaluation"][0]["status"], "AUTHORIZED")

            # B3 API: Proxy compacto (-xevil.com) y agrupado (-sSxevil.com) bloquean estáticamente
            for compact_cmd in ["curl -xevil.com https://target.local", "curl -sSxevil.com https://target.local"]:
                pb_compact = {
                    "id": "pb_compact_proxy",
                    "title": "Playbook Compact Proxy",
                    "version": "1.0",
                    "category": "recon",
                    "description": "Prueba API proxy compacto",
                    "steps": [
                        {
                            "id": "step_cproxy",
                            "title": "Paso Compact Proxy",
                            "objective": "Verificar bloqueo",
                            "interaction_type": "active_low",
                            "command_template": compact_cmd,
                            "timeout_seconds": 30,
                        }
                    ],
                }
                res_c = client.post(
                    "/api/v1/playbooks/validate",
                    json={"playbook": pb_compact, "engagement_id": "test-eng"},
                )
                self.assertEqual(res_c.status_code, 200)
                self.assertFalse(res_c.json()["scope_evaluation"]["can_execute"])
                self.assertEqual(res_c.json()["scope_evaluation"]["steps_evaluation"][0]["status"], "BLOCKED")

            # M4 API: Placeholder bajo bandera de destino (openssl s_client -connect {peer}:443)
            pb_connect = {
                "id": "pb_connect_ph",
                "title": "Playbook Connect Placeholder",
                "version": "1.0",
                "category": "recon",
                "description": "Prueba API placeholder bajo flag",
                "steps": [
                    {
                        "id": "step_conn",
                        "title": "Paso Connect",
                        "objective": "Verificar bloqueo de peer",
                        "interaction_type": "active_low",
                        "command_template": "openssl s_client -connect {peer}:443 -servername target.local",
                        "timeout_seconds": 30,
                    }
                ],
            }
            # Sin peer: bloquea
            res_conn_no = client.post(
                "/api/v1/playbooks/validate",
                json={"playbook": pb_connect, "engagement_id": "test-eng"},
            )
            self.assertEqual(res_conn_no.status_code, 200)
            self.assertFalse(res_conn_no.json()["scope_evaluation"]["can_execute"])
            self.assertEqual(res_conn_no.json()["scope_evaluation"]["steps_evaluation"][0]["status"], "BLOCKED")

            # Con peer autorizado: autoriza
            res_conn_ok = client.post(
                "/api/v1/playbooks/validate",
                json={
                    "playbook": pb_connect,
                    "engagement_id": "test-eng",
                    "parameters": {"peer": "target.local"},
                },
            )
            self.assertEqual(res_conn_ok.status_code, 200)
            self.assertTrue(res_conn_ok.json()["scope_evaluation"]["can_execute"])
            self.assertEqual(res_conn_ok.json()["scope_evaluation"]["steps_evaluation"][0]["status"], "AUTHORIZED")

            # B3: Parámetro posicional no canónico {asset}
            pb_asset = {
                "id": "pb_asset_api_test",
                "title": "Playbook Asset API Test",
                "version": "1.0",
                "category": "recon",
                "description": "Prueba API placeholder posicional no canónico",
                "steps": [
                    {
                        "id": "step_asset",
                        "title": "Paso Asset",
                        "objective": "Verificar bloqueo de asset",
                        "interaction_type": "active_low",
                        "command_template": "curl {asset} target.local",
                        "timeout_seconds": 30,
                    }
                ],
            }
            # Con asset=evil.com fuera de alcance: bloquea
            res_asset_evil = client.post(
                "/api/v1/playbooks/validate",
                json={
                    "playbook": pb_asset,
                    "engagement_id": "test-eng",
                    "parameters": {"asset": "evil.com"},
                },
            )
            self.assertEqual(res_asset_evil.status_code, 200)
            self.assertFalse(res_asset_evil.json()["scope_evaluation"]["can_execute"])
            self.assertEqual(res_asset_evil.json()["scope_evaluation"]["steps_evaluation"][0]["status"], "BLOCKED")
            self.assertIn("evil.com", res_asset_evil.json()["scope_evaluation"]["steps_evaluation"][0]["reason"])

            # Sin asset: bloquea por placeholder no expandido
            res_asset_none = client.post(
                "/api/v1/playbooks/validate",
                json={
                    "playbook": pb_asset,
                    "engagement_id": "test-eng",
                    "parameters": {},
                },
            )
            self.assertEqual(res_asset_none.status_code, 200)
            self.assertFalse(res_asset_none.json()["scope_evaluation"]["can_execute"])
            self.assertEqual(res_asset_none.json()["scope_evaluation"]["steps_evaluation"][0]["status"], "BLOCKED")

            # Con asset=target.local en alcance: autoriza
            res_asset_ok = client.post(
                "/api/v1/playbooks/validate",
                json={
                    "playbook": pb_asset,
                    "engagement_id": "test-eng",
                    "parameters": {"asset": "target.local"},
                },
            )
            self.assertEqual(res_asset_ok.status_code, 200)
            self.assertTrue(res_asset_ok.json()["scope_evaluation"]["can_execute"])
            self.assertEqual(res_asset_ok.json()["scope_evaluation"]["steps_evaluation"][0]["status"], "AUTHORIZED")

            client.close()

    def test_playbooks_api_b1_target_flag_precedence_over_non_target_name(self):
        """B1: En /validate, las banderas de destino prevalecen sobre nombres de placeholders y FQDNs con punto terminal fallan cerrado."""
        from app.main import app
        from app.api.endpoints import auth, playbooks
        from fastapi.testclient import TestClient

        ws_dir = pathlib.Path(self.tmp.name) / "workspace"
        eng_dir = ws_dir / "engagements" / "test-eng-b1"
        eng_dir.mkdir(parents=True, exist_ok=True)
        (ws_dir / "retos").mkdir(parents=True, exist_ok=True)

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

        auth._attempts.clear()
        with patch.object(auth, "TESTER_PASSWORD", "test-pass"), \
             patch.object(playbooks, "WORKSPACE_DIR", ws_dir):
            client = TestClient(app)
            login_res = client.post("/api/v1/auth/login", json={"password": "test-pass"})
            self.assertEqual(login_res.status_code, 200)

            pb_proxy = {
                "id": "pb_proxy_api_test",
                "title": "Playbook Proxy API Test",
                "version": "1.0",
                "category": "recon",
                "description": "Prueba API bandera proxy con placeholder method y FQDN con punto terminal",
                "steps": [
                    {
                        "id": "step_proxy",
                        "title": "Paso Proxy",
                        "objective": "Verificar bloqueo de proxy fuera de alcance con punto terminal",
                        "interaction_type": "active_low",
                        "command_template": "curl --proxy {method} https://target.local",
                        "timeout_seconds": 30,
                    }
                ],
            }

            # 1. /validate con method="evil.com." (fuera de alcance): bloqueado
            res_evil = client.post(
                "/api/v1/playbooks/validate",
                json={
                    "playbook": pb_proxy,
                    "engagement_id": "test-eng-b1",
                    "parameters": {"method": "evil.com."},
                },
            )
            self.assertEqual(res_evil.status_code, 200)
            self.assertFalse(res_evil.json()["scope_evaluation"]["can_execute"])
            self.assertEqual(res_evil.json()["scope_evaluation"]["steps_evaluation"][0]["status"], "BLOCKED")
            self.assertIn("evil.com", res_evil.json()["scope_evaluation"]["steps_evaluation"][0]["reason"])

            # 2. /validate sin method: bloqueado por placeholder sin resolver
            res_none = client.post(
                "/api/v1/playbooks/validate",
                json={
                    "playbook": pb_proxy,
                    "engagement_id": "test-eng-b1",
                    "parameters": {},
                },
            )
            self.assertEqual(res_none.status_code, 200)
            self.assertFalse(res_none.json()["scope_evaluation"]["can_execute"])
            self.assertEqual(res_none.json()["scope_evaluation"]["steps_evaluation"][0]["status"], "BLOCKED")

            # 3. /validate con method="target.local" (en alcance): autorizado
            res_ok = client.post(
                "/api/v1/playbooks/validate",
                json={
                    "playbook": pb_proxy,
                    "engagement_id": "test-eng-b1",
                    "parameters": {"method": "target.local"},
                },
            )
            self.assertEqual(res_ok.status_code, 200)
            self.assertTrue(res_ok.json()["scope_evaluation"]["can_execute"])
            self.assertEqual(res_ok.json()["scope_evaluation"]["steps_evaluation"][0]["status"], "AUTHORIZED")

            client.close()

    def test_playbooks_api_m1_non_target_payload_url_authorized(self):
        """M1: En /validate, URLs en payloads de datos bajo banderas no-objetivo (-d, -H) son autorizadas y no bloquean el paso."""
        from app.main import app
        from app.api.endpoints import auth, playbooks
        from fastapi.testclient import TestClient

        ws_dir = pathlib.Path(self.tmp.name) / "workspace"
        eng_dir = ws_dir / "engagements" / "test-eng-m1"
        eng_dir.mkdir(parents=True, exist_ok=True)
        (ws_dir / "retos").mkdir(parents=True, exist_ok=True)

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
            "    domains: ['client.example']\n"
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

        auth._attempts.clear()
        with patch.object(auth, "TESTER_PASSWORD", "test-pass"), \
             patch.object(playbooks, "WORKSPACE_DIR", ws_dir):
            client = TestClient(app)
            login_res = client.post("/api/v1/auth/login", json={"password": "test-pass"})
            self.assertEqual(login_res.status_code, 200)

            # Paso con URL externa dentro de payload bajo -d
            pb_payload = {
                "id": "pb_oauth_callback_api_test",
                "title": "Playbook OAuth Callback API Test",
                "version": "1.0",
                "category": "api",
                "description": "Prueba API payload no-objetivo con URL",
                "steps": [
                    {
                        "id": "step_oauth_callback",
                        "title": "Paso OAuth Callback",
                        "objective": "Enviar callback URL a destino en alcance",
                        "interaction_type": "active_low",
                        "command_template": "curl -d '{payload}' https://target.local",
                        "timeout_seconds": 30,
                    }
                ],
            }

            # 1. /validate con payload conteniendo URL externa: autorizado (target.local es el destino real)
            res_payload = client.post(
                "/api/v1/playbooks/validate",
                json={
                    "playbook": pb_payload,
                    "engagement_id": "test-eng-m1",
                    "parameters": {"payload": "https://client.example/callback"},
                },
            )
            self.assertEqual(res_payload.status_code, 200)
            self.assertTrue(res_payload.json()["scope_evaluation"]["can_execute"])
            self.assertEqual(res_payload.json()["scope_evaluation"]["steps_evaluation"][0]["status"], "AUTHORIZED")

            # 2. Control de seguridad: la MISMA URL externa como destino real en /validate es bloqueada
            pb_direct_url = {
                "id": "pb_direct_url_test",
                "title": "Playbook Direct URL Test",
                "version": "1.0",
                "category": "api",
                "description": "Prueba de control con URL directa fuera de alcance",
                "steps": [
                    {
                        "id": "step_direct_url",
                        "title": "Paso Direct URL",
                        "objective": "Verificar bloqueo de URL directa fuera de alcance",
                        "interaction_type": "active_low",
                        "command_template": "curl https://client.example/callback",
                        "timeout_seconds": 30,
                    }
                ],
            }
            res_direct = client.post(
                "/api/v1/playbooks/validate",
                json={
                    "playbook": pb_direct_url,
                    "engagement_id": "test-eng-m1",
                },
            )
            self.assertEqual(res_direct.status_code, 200)
            self.assertFalse(res_direct.json()["scope_evaluation"]["can_execute"])
            self.assertEqual(res_direct.json()["scope_evaluation"]["steps_evaluation"][0]["status"], "BLOCKED")
            self.assertIn("client.example", res_direct.json()["scope_evaluation"]["steps_evaluation"][0]["reason"])

            client.close()

    def test_playbooks_api_b2_nmap_fast_mode_blocked_vs_curl_form_authorized(self):
        """B2: En /validate, nmap -F no descarta objetivos fuera de alcance (bloquea) mientras curl -F autoriza formularios legítimos."""
        from app.main import app
        from app.api.endpoints import auth, playbooks
        from fastapi.testclient import TestClient

        ws_dir = pathlib.Path(self.tmp.name) / "workspace"
        eng_dir = ws_dir / "engagements" / "test-eng-b2"
        eng_dir.mkdir(parents=True, exist_ok=True)
        (ws_dir / "retos").mkdir(parents=True, exist_ok=True)

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
            "    domains: ['evil.com', 'client.example']\n"
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

        auth._attempts.clear()
        with patch.object(auth, "TESTER_PASSWORD", "test-pass"), \
             patch.object(playbooks, "WORKSPACE_DIR", ws_dir):
            client = TestClient(app)
            login_res = client.post("/api/v1/auth/login", json={"password": "test-pass"})
            self.assertEqual(login_res.status_code, 200)

            # 1. nmap -F con objetivo fuera de alcance: bloquea
            pb_nmap = {
                "id": "pb_nmap_b2_test",
                "title": "Playbook Nmap B2 Test",
                "version": "1.0",
                "category": "recon",
                "description": "Prueba API nmap -F",
                "steps": [
                    {
                        "id": "step_nmap",
                        "title": "Paso Nmap Fast",
                        "objective": "Escanear puertos con -F",
                        "interaction_type": "active_low",
                        "command_template": "nmap -F evil.com target.local",
                        "timeout_seconds": 30,
                    }
                ],
            }
            res_nmap = client.post(
                "/api/v1/playbooks/validate",
                json={"playbook": pb_nmap, "engagement_id": "test-eng-b2"},
            )
            self.assertEqual(res_nmap.status_code, 200)
            self.assertFalse(res_nmap.json()["scope_evaluation"]["can_execute"])
            self.assertEqual(res_nmap.json()["scope_evaluation"]["steps_evaluation"][0]["status"], "BLOCKED")
            self.assertIn("evil.com", res_nmap.json()["scope_evaluation"]["steps_evaluation"][0]["reason"])

            # 2. curl -F con payload que contiene URL externa: autoriza
            pb_curl = {
                "id": "pb_curl_b2_test",
                "title": "Playbook Curl B2 Test",
                "version": "1.0",
                "category": "api",
                "description": "Prueba API curl -F",
                "steps": [
                    {
                        "id": "step_curl",
                        "title": "Paso Curl Form",
                        "objective": "Enviar form con -F",
                        "interaction_type": "active_low",
                        "command_template": "curl -F 'data=https://client.example/callback' https://target.local",
                        "timeout_seconds": 30,
                    }
                ],
            }
            res_curl = client.post(
                "/api/v1/playbooks/validate",
                json={"playbook": pb_curl, "engagement_id": "test-eng-b2"},
            )
            self.assertEqual(res_curl.status_code, 200)
            self.assertTrue(res_curl.json()["scope_evaluation"]["can_execute"])
            self.assertEqual(res_curl.json()["scope_evaluation"]["steps_evaluation"][0]["status"], "AUTHORIZED")

            client.close()


if __name__ == "__main__":
    unittest.main()
