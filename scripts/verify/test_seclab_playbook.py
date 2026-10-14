#!/usr/bin/env python3
"""Pruebas unitarias para el gestor y validador de Playbooks deterministas (seclab_playbook)."""

import pathlib
import sys
import tempfile
import unittest
import unittest.mock

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))
sys.path.insert(0, str(REPO_ROOT / "scripts" / "verify"))

from authorization_fixture import AUTHORIZATION_YAML
from seclab_playbook import (
    validate_playbook_schema,
    validate_playbook_against_scope,
    load_playbook_file,
    PlaybookValidationError,
)


DEFAULT_SCOPE_YAML = (
    "scope:\n"
    "  in_scope:\n"
    "    domains: ['target.local']\n"
    "    ips: ['127.0.0.1']\n"
    "    cidrs: []\n"
    "    endpoints: []\n"
    "  out_of_scope:\n"
    "    domains: []\n"
    "    ips: []\n"
    "    cidrs: []\n"
    "    endpoints: []\n"
)


class TestSeclabPlaybook(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.tmp_path = pathlib.Path(self.tmp.name)

        self.valid_playbook = {
            "id": "pb_test_audit",
            "title": "Auditoría de Prueba",
            "version": "1.0",
            "category": "recon",
            "description": "Playbook para pruebas unitarias de validación.",
            "author": "SecLab-SBF",
            "steps": [
                {
                    "id": "step_01_passive_lookup",
                    "title": "Búsqueda Pasiva",
                    "objective": "Buscar registros sin tráfico activo.",
                    "interaction_type": "passive",
                    "required_permissions": ["allow_passive"],
                    "target_selector": "domains",
                    "command_template": "whois {target}",
                    "timeout_seconds": 60,
                    "expected_outputs": ["recon/whois.txt"],
                },
                {
                    "id": "step_02_port_scan",
                    "title": "Escaneo de Puertos",
                    "objective": "Escanear puertos TCP.",
                    "interaction_type": "active_low",
                    "required_permissions": ["allow_active"],
                    "target_selector": "live_hosts",
                    "command_template": "nmap -sT {target}",
                    "timeout_seconds": 120,
                    "expected_outputs": ["recon/ports.txt"],
                },
            ],
        }

    def test_valid_playbook_schema(self):
        is_valid, errors = validate_playbook_schema(self.valid_playbook)
        self.assertTrue(is_valid)
        self.assertEqual(len(errors), 0)

    def test_missing_required_fields(self):
        invalid_pb = {"id": "pb_incomplete"}
        is_valid, errors = validate_playbook_schema(invalid_pb)
        self.assertFalse(is_valid)
        self.assertTrue(any("steps" in err for err in errors))

    def test_duplicate_step_ids(self):
        dup_pb = dict(self.valid_playbook)
        dup_pb["steps"] = [
            self.valid_playbook["steps"][0],
            dict(self.valid_playbook["steps"][0]),
        ]
        is_valid, errors = validate_playbook_schema(dup_pb)
        self.assertFalse(is_valid)
        self.assertTrue(any("duplicado" in err for err in errors))

    def test_invalid_interaction_type(self):
        bad_type_pb = dict(self.valid_playbook)
        bad_type_pb["steps"] = [dict(self.valid_playbook["steps"][0])]
        bad_type_pb["steps"][0]["interaction_type"] = "aggressive_exploit"
        is_valid, errors = validate_playbook_schema(bad_type_pb)
        self.assertFalse(is_valid)
        self.assertTrue(any("interaction_type" in err for err in errors))

    def test_scope_validation_allows_authorized_steps(self):
        from authorization_fixture import AUTHORIZATION_YAML
        target_yaml = self.tmp_path / "target.yaml"
        target_yaml.write_text(DEFAULT_SCOPE_YAML + AUTHORIZATION_YAML)
        res = validate_playbook_against_scope(self.valid_playbook, target_yaml, parameters={"target": "target.local"})
        self.assertTrue(res["can_execute"])
        self.assertEqual(res["blocked_steps_count"], 0)
        for s in res["steps_evaluation"]:
            self.assertEqual(s["status"], "AUTHORIZED")

    def test_scope_validation_blocks_active_when_disallowed(self):
        from authorization_fixture import AUTHORIZATION_YAML
        target_yaml = self.tmp_path / "target.yaml"
        target_yaml.write_text(
            DEFAULT_SCOPE_YAML + AUTHORIZATION_YAML.replace("allow_active: true", "allow_active: false")
        )
        res = validate_playbook_against_scope(self.valid_playbook, target_yaml)
        self.assertFalse(res["can_execute"])
        self.assertEqual(res["blocked_steps_count"], 1)

        step_map = {s["step_id"]: s for s in res["steps_evaluation"]}
        self.assertEqual(step_map["step_01_passive_lookup"]["status"], "AUTHORIZED")
        self.assertEqual(step_map["step_02_port_scan"]["status"], "BLOCKED")
        self.assertIn("target.yaml", step_map["step_02_port_scan"]["reason"])

    def test_load_builtin_playbook_templates(self):
        playbook_files = [
            "web_recon.yaml",
            "port_discovery.yaml",
            "ssl_tls_audit.yaml",
            "dns_zone_recon.yaml",
            "api_endpoint_discovery.yaml",
            "api_graphql_audit.yaml",
            "oauth_jwt_audit.yaml",
            "smb_shares_recon.yaml",
            "internal_pivot_audit.yaml",
        ]
        for name in playbook_files:
            pb_path = REPO_ROOT / "workspace-seed" / "playbooks" / name
            self.assertTrue(pb_path.is_file(), f"Falta archivo {name}")
            pb = load_playbook_file(pb_path)
            is_valid, errors = validate_playbook_schema(pb)
            self.assertTrue(is_valid, f"Errores en {name}: {errors}")
            self.assertGreaterEqual(len(pb.get("steps", [])), 1)

    def test_load_builtin_playbook_templates_without_pyyaml(self):
        import seclab_playbook
        orig_yaml = seclab_playbook.yaml
        try:
            seclab_playbook.yaml = None
            playbook_files = [
                "web_recon.yaml",
                "port_discovery.yaml",
                "ssl_tls_audit.yaml",
                "dns_zone_recon.yaml",
                "api_endpoint_discovery.yaml",
                "api_graphql_audit.yaml",
                "oauth_jwt_audit.yaml",
                "smb_shares_recon.yaml",
                "internal_pivot_audit.yaml",
            ]
            for name in playbook_files:
                pb_path = REPO_ROOT / "workspace-seed" / "playbooks" / name
                pb = load_playbook_file(pb_path)
                is_valid, errors = validate_playbook_schema(pb)
                self.assertTrue(is_valid, f"Errores sin PyYAML en {name}: {errors}")
                self.assertGreaterEqual(len(pb.get("steps", [])), 1)
        finally:
            seclab_playbook.yaml = orig_yaml

    def test_interpolate_command_valid(self):
        from seclab_playbook import interpolate_command
        tpl = "curl -s -I {target}:{port}"
        res = interpolate_command(tpl, {"target": "example.com", "port": 8080})
        self.assertEqual(res, "curl -s -I example.com:8080")

    def test_interpolate_command_rejects_dangerous_characters(self):
        from seclab_playbook import interpolate_command, PlaybookValidationError
        tpl = "ping {target}"
        for bad_val in ("example.com; rm -rf /", "test | whoami", "host `id`", "target$(id)"):
            with self.assertRaises(PlaybookValidationError):
                interpolate_command(tpl, {"target": bad_val})

    def test_execute_step_dry_run_simulation(self):
        from seclab_playbook import execute_playbook_step
        step = self.valid_playbook["steps"][0]
        res = execute_playbook_step(step, context={"parameters": {"target": "example.com"}}, dry_run=True)
        self.assertEqual(res["status"], "SIMULATED")
        self.assertEqual(res["exit_code"], 0)
        self.assertTrue(res["is_simulated"])
        self.assertIn("whois example.com", res["command"])

    def test_execute_step_blocked_when_active_forbidden(self):
        from seclab_playbook import execute_playbook_step
        step = self.valid_playbook["steps"][1]  # active_low
        res = execute_playbook_step(step, context={"allow_active": False, "parameters": {"target": "example.com"}}, dry_run=False)
        self.assertEqual(res["status"], "BLOCKED")
        self.assertEqual(res["exit_code"], 126)
        self.assertTrue(res["stop_condition_met"])

    def test_run_playbook_full_dry_run(self):
        from seclab_playbook import run_playbook
        target_yaml = self.tmp_path / "target.yaml"
        target_yaml.write_text(
            "scope:\n  in_scope:\n    ips: ['127.0.0.1']\n    domains: []\n    cidrs: []\n    endpoints: []\n"
            "  out_of_scope:\n    ips: []\n    domains: []\n    cidrs: []\n    endpoints: []\n"
            + AUTHORIZATION_YAML
        )
        res = run_playbook(
            self.valid_playbook,
            target_yaml_path=target_yaml,
            context={"parameters": {"target": "127.0.0.1"}},
            dry_run=True,
        )
        self.assertEqual(res["status"], "SIMULATED")
        self.assertEqual(res["total_steps"], 2)
        self.assertEqual(res["executed_steps_count"], 2)
        for s in res["steps_results"]:
            self.assertEqual(s["status"], "SIMULATED")

    def test_run_playbook_stops_on_blocked_step(self):
        from seclab_playbook import run_playbook
        target_yaml = self.tmp_path / "target.yaml"
        target_yaml.write_text(
            "scope:\n  in_scope:\n    ips: ['127.0.0.1']\n    domains: []\n    cidrs: []\n    endpoints: []\n"
            "  out_of_scope:\n    ips: []\n    domains: []\n    cidrs: []\n    endpoints: []\n"
            + AUTHORIZATION_YAML.replace("allow_active: true", "allow_active: false")
        )
        res = run_playbook(
            self.valid_playbook,
            target_yaml_path=target_yaml,
            context={"parameters": {"target": "127.0.0.1"}},
            dry_run=False,
        )
        self.assertEqual(res["status"], "BLOCKED")
        self.assertFalse(res["can_execute"])

    def test_save_playbook_run_evidence(self):
        import json
        from seclab_playbook import save_playbook_run_evidence
        eng_dir = self.tmp_path / "eng_test"
        eng_dir.mkdir(parents=True)

        fake_res = {
            "playbook_id": "pb_test_audit",
            "title": "Auditoría de Prueba",
            "status": "SIMULATED",
            "dry_run": True,
            "total_steps": 2,
            "executed_steps_count": 2,
            "steps_results": [
                {
                    "step_id": "step_01_passive_lookup",
                    "title": "Búsqueda Pasiva",
                    "status": "SIMULATED",
                    "command": "whois example.com",
                    "exit_code": 0,
                    "output": "[dry-run] Simulación completada.",
                }
            ],
        }

        saved_path = save_playbook_run_evidence(eng_dir, fake_res, parameters={"target": "example.com"})
        self.assertTrue(saved_path.is_file())
        self.assertTrue(str(saved_path).endswith(".json"))
        self.assertIn("pb_test_audit", saved_path.name)

        data = json.loads(saved_path.read_text(encoding="utf-8"))
        self.assertEqual(data["schema_version"], "1.0")
        self.assertEqual(data["evidence_type"], "playbook_run")
        self.assertEqual(data["playbook_id"], "pb_test_audit")
        self.assertEqual(data["parameters"], {"target": "example.com"})
        self.assertEqual(len(data["steps_results"]), 1)

    def test_list_playbook_runs(self):
        from seclab_playbook import save_playbook_run_evidence, list_playbook_runs
        eng_dir = self.tmp_path / "eng_test_list"
        eng_dir.mkdir(parents=True)

        # Sin ejecuciones previas
        self.assertEqual(list_playbook_runs(eng_dir), [])

        # Guardar corrida 1
        res1 = {
            "playbook_id": "pb_01",
            "title": "Playbook 1",
            "status": "COMPLETED",
            "dry_run": False,
            "total_steps": 1,
            "executed_steps_count": 1,
            "steps_results": [],
        }
        save_playbook_run_evidence(eng_dir, res1)

        # Guardar corrida 2
        res2 = {
            "playbook_id": "pb_02",
            "title": "Playbook 2",
            "status": "SIMULATED",
            "dry_run": True,
            "total_steps": 2,
            "executed_steps_count": 2,
            "steps_results": [],
        }
        save_playbook_run_evidence(eng_dir, res2)

        runs_all = list_playbook_runs(eng_dir)
        self.assertEqual(len(runs_all), 2)

        runs_pb1 = list_playbook_runs(eng_dir, playbook_id="pb_01")
        self.assertEqual(len(runs_pb1), 1)
        self.assertEqual(runs_pb1[0]["playbook_id"], "pb_01")
        self.assertEqual(runs_pb1[0]["status"], "COMPLETED")
        self.assertFalse(runs_pb1[0]["dry_run"])

        runs_pb2 = list_playbook_runs(eng_dir, playbook_id="pb_02")
        self.assertEqual(len(runs_pb2), 1)
        self.assertEqual(runs_pb2[0]["playbook_id"], "pb_02")
        self.assertTrue(runs_pb2[0]["dry_run"])

    def test_real_run_without_target_yaml_fails_closed(self):
        from seclab_playbook import run_playbook
        res = run_playbook(
            self.valid_playbook,
            target_yaml_path=None,
            dry_run=False,
        )
        self.assertEqual(res["status"], "BLOCKED")
        self.assertFalse(res["can_execute"])
        self.assertIn("target.yaml", res["reason"])

    def test_expired_authorization_window_blocks_active_and_passive(self):
        from datetime import datetime, timezone
        from seclab_playbook import validate_playbook_against_scope
        target_yaml = self.tmp_path / "target_expired.yaml"
        target_yaml.write_text(
            DEFAULT_SCOPE_YAML +
            "authorization:\n"
            "  reference: 'EXP-123'\n"
            "  valid_from: '2026-01-01T00:00:00.000Z'\n"
            "  valid_until: '2026-01-02T00:00:00.000Z'\n"
            "  allow_passive: true\n"
            "  allow_active: true\n"
        )
        # Evaluando en fecha posterior al fin de vigencia
        eval_time = datetime(2026, 10, 12, 12, 0, 0, tzinfo=timezone.utc)
        res = validate_playbook_against_scope(self.valid_playbook, target_yaml, now=eval_time)
        self.assertFalse(res["can_execute"])
        self.assertFalse(res["authorization_state"]["allow_active"])
        self.assertFalse(res["authorization_state"]["allow_passive"])
        for s in res["steps_evaluation"]:
            self.assertEqual(s["status"], "BLOCKED")
            self.assertIn("vigencia", s["reason"])

    def test_valid_authorization_window_allows_execution(self):
        from datetime import datetime, timezone
        from seclab_playbook import validate_playbook_against_scope
        target_yaml = self.tmp_path / "target_valid.yaml"
        target_yaml.write_text(
            DEFAULT_SCOPE_YAML +
            "authorization:\n"
            "  reference: 'VAL-456'\n"
            "  valid_from: '2026-10-01T00:00:00.000Z'\n"
            "  valid_until: '2026-10-31T23:59:59.000Z'\n"
            "  allow_passive: true\n"
            "  allow_active: true\n"
        )
        eval_time = datetime(2026, 10, 12, 12, 0, 0, tzinfo=timezone.utc)
        res = validate_playbook_against_scope(self.valid_playbook, target_yaml, parameters={"target": "target.local"}, now=eval_time)
        self.assertTrue(res["can_execute"])
        self.assertTrue(res["authorization_state"]["allow_active"])
        self.assertTrue(res["authorization_state"]["allow_passive"])
        self.assertEqual(res["blocked_steps_count"], 0)

    def test_target_selector_blocks_out_of_scope_target(self):
        from seclab_playbook import execute_playbook_step
        step = {
            "id": "step_probe",
            "title": "Sondeo Web",
            "interaction_type": "active_low",
            "target_selector": "in_scope_domains",
            "command_template": "curl https://{domain}",
        }
        scope_data = {
            "scope": {
                "in_scope": {"domains": ["target.local"], "ips": [], "cidrs": [], "endpoints": []},
                "out_of_scope": {"domains": ["evil.com"], "ips": [], "cidrs": [], "endpoints": []},
            }
        }
        # Parámetro apunta a dominio fuera de alcance
        res = execute_playbook_step(
            step=step,
            context={
                "parameters": {"domain": "evil.com"},
                "allow_active": True,
                "scope_data": scope_data,
            },
            dry_run=False,
        )
        self.assertEqual(res["status"], "BLOCKED")
        self.assertEqual(res["exit_code"], 126)
        self.assertTrue(res["stop_condition_met"])
        self.assertIn("evil.com", res["output"])
        self.assertIn("Scope Guard", res["output"])

    def test_target_selector_allows_in_scope_target(self):
        from seclab_playbook import execute_playbook_step
        step = {
            "id": "step_probe",
            "title": "Sondeo Web",
            "interaction_type": "active_low",
            "target_selector": "in_scope_domains",
            "command_template": "curl https://{domain}",
        }
        scope_data = {
            "scope": {
                "in_scope": {"domains": ["target.local"], "ips": [], "cidrs": [], "endpoints": []},
                "out_of_scope": {"domains": [], "ips": [], "cidrs": [], "endpoints": []},
            }
        }
        # Parámetro dentro de alcance en simulación
        res = execute_playbook_step(
            step=step,
            context={
                "parameters": {"domain": "target.local"},
                "allow_active": True,
                "scope_data": scope_data,
            },
            dry_run=True,
        )
        self.assertEqual(res["status"], "SIMULATED")
        self.assertEqual(res["exit_code"], 0)
        self.assertIn("target.local", res["command"])

    def test_execute_passive_step_blocked_when_disallowed_in_real_run(self):
        from seclab_playbook import execute_playbook_step
        step = {
            "id": "step_passive",
            "title": "Reconocimiento Pasivo",
            "interaction_type": "passive",
            "command_template": "whois {domain}",
        }
        # Sin permiso pasivo en ejecución real
        res = execute_playbook_step(
            step=step,
            context={"parameters": {"domain": "target.local"}, "allow_passive": False},
            dry_run=False,
        )
        self.assertEqual(res["status"], "BLOCKED")
        self.assertEqual(res["exit_code"], 126)
        self.assertTrue(res["stop_condition_met"])

    def test_incomplete_authorization_missing_reference_or_dates_blocks_real_run(self):
        from seclab_playbook import run_playbook, validate_playbook_against_scope
        # target.yaml con allow_active: true pero sin reference, valid_from ni valid_until
        target_yaml = self.tmp_path / "target_incomplete.yaml"
        target_yaml.write_text(
            DEFAULT_SCOPE_YAML +
            "authorization:\n"
            "  allow_passive: true\n"
            "  allow_active: true\n"
        )
        res_val = validate_playbook_against_scope(self.valid_playbook, target_yaml)
        self.assertFalse(res_val["can_execute"])
        self.assertFalse(res_val["authorization_state"]["allow_active"])
        self.assertFalse(res_val["authorization_state"]["allow_passive"])
        for s in res_val["steps_evaluation"]:
            self.assertEqual(s["status"], "BLOCKED")
            self.assertIn("referencia, inicio y fin de autorización", s["reason"])

        # En ejecución real, run_playbook debe quedar BLOCKED con 0 pasos ejecutados
        pb_simple = {
            "id": "pb_test_exec",
            "title": "Prueba Inocua",
            "version": "1.0",
            "category": "recon",
            "description": "Test",
            "steps": [
                {
                    "id": "step_cmd",
                    "title": "Cmd",
                    "objective": "Test",
                    "interaction_type": "active_low",
                    "command_template": "printf 'EXECUTED'",
                }
            ],
        }
        res_run = run_playbook(pb_simple, target_yaml_path=target_yaml, dry_run=False)
        self.assertEqual(res_run["status"], "BLOCKED")
        self.assertFalse(res_run["can_execute"])
        self.assertEqual(res_run["executed_steps_count"], 0)

    def test_target_selector_with_arbitrary_placeholder_endpoint_blocked(self):
        from seclab_playbook import execute_playbook_step
        step = {
            "id": "step_endpoint_probe",
            "title": "Sondeo Endpoint",
            "interaction_type": "active_low",
            "target_selector": "in_scope_domains",
            "command_template": "curl -s https://{endpoint}/api",
        }
        scope_data = {
            "scope": {
                "in_scope": {"domains": ["target.local"], "ips": [], "cidrs": [], "endpoints": []},
                "out_of_scope": {"domains": ["evil.com"], "ips": [], "cidrs": [], "endpoints": []},
            }
        }
        res = execute_playbook_step(
            step=step,
            context={
                "parameters": {"endpoint": "evil.com"},
                "allow_active": True,
                "scope_data": scope_data,
            },
            dry_run=False,
        )
        self.assertEqual(res["status"], "BLOCKED")
        self.assertEqual(res["exit_code"], 126)
        self.assertTrue(res["stop_condition_met"])
        self.assertIn("evil.com", res["output"])
        self.assertIn("Scope Guard", res["output"])

    def test_file_based_target_selector_blocks_when_file_contains_out_of_scope_destination(self):
        from seclab_playbook import execute_playbook_step
        recon_dir = self.tmp_path / "recon"
        recon_dir.mkdir(parents=True, exist_ok=True)
        subdomains_file = recon_dir / "subdomains.txt"
        subdomains_file.write_text("sub1.target.local\nevil.com\n", encoding="utf-8")

        step = {
            "id": "step_probing",
            "title": "Sondeo de subdominios",
            "interaction_type": "active_low",
            "target_selector": "recon/subdomains.txt",
            "inputs": ["recon/subdomains.txt"],
            "command_template": "httpx -l recon/subdomains.txt",
        }
        scope_data = {
            "scope": {
                "in_scope": {"domains": ["target.local", "*.target.local"], "ips": [], "cidrs": [], "endpoints": []},
                "out_of_scope": {"domains": ["evil.com"], "ips": [], "cidrs": [], "endpoints": []},
            }
        }
        res = execute_playbook_step(
            step=step,
            context={
                "engagement_dir": str(self.tmp_path),
                "allow_active": True,
                "scope_data": scope_data,
            },
            dry_run=False,
        )
        self.assertEqual(res["status"], "BLOCKED")
        self.assertEqual(res["exit_code"], 126)
        self.assertIn("evil.com", res["output"])
        self.assertIn("Scope Guard", res["output"])

    def test_file_based_target_selector_blocks_when_file_is_missing_in_real_run(self):
        from seclab_playbook import execute_playbook_step
        step = {
            "id": "step_probing_missing",
            "title": "Sondeo con archivo faltante",
            "interaction_type": "active_low",
            "target_selector": "recon/nonexistent.txt",
            "inputs": ["recon/nonexistent.txt"],
            "command_template": "httpx -l recon/nonexistent.txt",
        }
        scope_data = {
            "scope": {
                "in_scope": {"domains": ["target.local"], "ips": [], "cidrs": [], "endpoints": []},
                "out_of_scope": {"domains": [], "ips": [], "cidrs": [], "endpoints": []},
            }
        }
        res = execute_playbook_step(
            step=step,
            context={
                "engagement_dir": str(self.tmp_path),
                "allow_active": True,
                "scope_data": scope_data,
            },
            dry_run=False,
        )
        self.assertEqual(res["status"], "BLOCKED")
        self.assertEqual(res["exit_code"], 126)
        self.assertIn("recon/nonexistent.txt", res["output"])

    def test_missing_scope_section_in_target_yaml_handled_gracefully(self):
        from seclab_playbook import validate_playbook_against_scope, execute_playbook_step
        target_yaml = self.tmp_path / "target_no_scope.yaml"
        target_yaml.write_text("engagement:\n  name: Test\n", encoding="utf-8")

        res_val = validate_playbook_against_scope(self.valid_playbook, target_yaml)
        self.assertFalse(res_val["can_execute"])
        self.assertEqual(res_val["blocked_steps_count"], 2)

        # execute_playbook_step con target pero scope_data inválido
        step = {
            "id": "step_test",
            "title": "Test",
            "interaction_type": "active_low",
            "command_template": "curl {endpoint}",
        }
        res_exec = execute_playbook_step(
            step=step,
            context={"parameters": {"endpoint": "target.local"}, "allow_active": True, "scope_data": {"invalid": True}},
            dry_run=False,
        )
        self.assertEqual(res_exec["status"], "BLOCKED")
        self.assertEqual(res_exec["exit_code"], 126)


    def test_valid_auth_with_missing_scope_blocks_real_run_and_steps(self):
        from seclab_playbook import validate_playbook_against_scope, run_playbook, execute_playbook_step
        target_yaml = self.tmp_path / "target_valid_auth_no_scope.yaml"
        # Autorización 100% válida pero sin sección scope:
        target_yaml.write_text(
            "authorization:\n"
            "  reference: 'REF-2026-CANONICAL'\n"
            "  valid_from: '2020-01-01T00:00:00Z'\n"
            "  valid_until: '2030-01-01T00:00:00Z'\n"
            "  allow_passive: true\n"
            "  allow_active: true\n",
            encoding="utf-8",
        )

        # 1. validate_playbook_against_scope debe fallar cerrado
        res_val = validate_playbook_against_scope(self.valid_playbook, target_yaml)
        self.assertFalse(res_val["can_execute"])
        self.assertEqual(res_val["blocked_steps_count"], 2)
        self.assertIsNone(res_val["scope_data"])
        self.assertIn("scope", res_val["scope_error"].lower())
        for s in res_val["steps_evaluation"]:
            self.assertEqual(s["status"], "BLOCKED")

        # 2. run_playbook en ejecución real con comando inocuo sin placeholders debe bloquearse
        pb_innocuous = {
            "id": "pb_innocuous",
            "title": "Comando Inocuo",
            "version": "1.0",
            "category": "recon",
            "description": "Comando sin destinos explícitos",
            "steps": [
                {
                    "id": "step_01_cmd",
                    "title": "Print Execution",
                    "objective": "Verificar ejecución inocua",
                    "interaction_type": "active_low",
                    "command_template": "printf 'EXECUTED'",
                }
            ],
        }
        res_run = run_playbook(pb_innocuous, target_yaml_path=target_yaml, dry_run=False)
        self.assertEqual(res_run["status"], "BLOCKED")
        self.assertFalse(res_run["can_execute"])
        self.assertEqual(res_run["executed_steps_count"], 0)
        self.assertEqual(res_run["steps_results"], [])

        # 3. execute_playbook_step con dry_run=False debe bloquearse
        res_exec = execute_playbook_step(
            step=pb_innocuous["steps"][0],
            context={"target_yaml_path": target_yaml, "allow_active": True, "scope_data": None},
            dry_run=False,
        )
        self.assertEqual(res_exec["status"], "BLOCKED")
        self.assertEqual(res_exec["exit_code"], 126)
        self.assertIn("alcance", res_exec["output"].lower())

    def test_valid_auth_with_malformed_scope_blocks_real_run_and_steps(self):
        from seclab_playbook import validate_playbook_against_scope, run_playbook, execute_playbook_step
        target_yaml = self.tmp_path / "target_malformed_scope.yaml"
        # Autorización válida pero scope malformado (scope es string en vez de dict)
        target_yaml.write_text(
            "scope: 'invalido_no_es_objeto'\n"
            "authorization:\n"
            "  reference: 'REF-2026-MALFORMED'\n"
            "  valid_from: '2020-01-01T00:00:00Z'\n"
            "  valid_until: '2030-01-01T00:00:00Z'\n"
            "  allow_passive: true\n"
            "  allow_active: true\n",
            encoding="utf-8",
        )

        res_val = validate_playbook_against_scope(self.valid_playbook, target_yaml)
        self.assertFalse(res_val["can_execute"])
        self.assertEqual(res_val["blocked_steps_count"], 2)
        self.assertIsNone(res_val["scope_data"])

        pb_simple = {
            "id": "pb_simple",
            "title": "Simple",
            "version": "1.0",
            "category": "recon",
            "description": "Test",
            "steps": [
                {
                    "id": "step_01_hello",
                    "title": "Step 1",
                    "objective": "Objetivo de prueba",
                    "interaction_type": "active_low",
                    "command_template": "echo hello",
                }
            ],
        }
        res_run = run_playbook(pb_simple, target_yaml_path=target_yaml, dry_run=False)
        self.assertEqual(res_run["status"], "BLOCKED")
        self.assertFalse(res_run["can_execute"])
        self.assertEqual(res_run["executed_steps_count"], 0)

        res_step = execute_playbook_step(
            step=pb_simple["steps"][0],
            context={"target_yaml_path": target_yaml, "allow_active": True, "scope_data": {"scope": "invalido"}},
            dry_run=False,
        )
        self.assertEqual(res_step["status"], "BLOCKED")
        self.assertEqual(res_step["exit_code"], 126)

    def test_target_selector_without_resolvable_targets_blocks_real_run(self):
        from seclab_playbook import execute_playbook_step
        step = {
            "id": "step_probe_empty",
            "title": "Sondeo Sin Destinos",
            "interaction_type": "active_low",
            "target_selector": "in_scope_domains",
            "command_template": "curl https://{domain}",
        }
        scope_data = {
            "scope": {
                "in_scope": {"domains": ["target.local"], "ips": [], "cidrs": [], "endpoints": []},
                "out_of_scope": {"domains": [], "ips": [], "cidrs": [], "endpoints": []},
            }
        }
        # En ejecución real, si requiere target_selector y no hay candidatos resolubles, debe bloquearse
        res = execute_playbook_step(
            step=step,
            context={"parameters": {}, "allow_active": True, "scope_data": scope_data},
            dry_run=False,
        )
        self.assertEqual(res["status"], "BLOCKED")
        self.assertEqual(res["exit_code"], 126)
        self.assertIn("in_scope_domains", res["output"])

        # En dry-run sí debe permitirse la simulación
        res_dry = execute_playbook_step(
            step=step,
            context={"parameters": {}, "allow_active": True, "scope_data": scope_data},
            dry_run=True,
        )
        self.assertEqual(res_dry["status"], "SIMULATED")
        self.assertEqual(res_dry["exit_code"], 0)

    def test_active_step_with_literal_out_of_scope_target_is_blocked(self):
        """B3: Paso activo con destino literal fuera de alcance es bloqueado por Scope Guard."""
        from seclab_playbook import execute_playbook_step, run_playbook, validate_playbook_against_scope
        from authorization_fixture import AUTHORIZATION_YAML
        target_yaml = self.tmp_path / "target_literal.yaml"
        target_yaml.write_text(DEFAULT_SCOPE_YAML + AUTHORIZATION_YAML)

        pb = {
            "id": "pb_literal_out_of_scope",
            "title": "Prueba Literal Fuera de Alcance",
            "version": "1.0",
            "category": "recon",
            "description": "Test B3",
            "steps": [
                {
                    "id": "step_literal_curl",
                    "title": "Curl Literal",
                    "objective": "Verificar bloqueo de destino literal no autorizado",
                    "interaction_type": "active_low",
                    "command_template": "curl https://destino-fuera-de-alcance",
                }
            ],
        }

        # 1. Validación estática contra alcance
        res_val = validate_playbook_against_scope(pb, target_yaml)
        self.assertFalse(res_val["can_execute"])
        self.assertEqual(res_val["blocked_steps_count"], 1)
        self.assertEqual(res_val["steps_evaluation"][0]["status"], "BLOCKED")
        self.assertIn("fuera de alcance según Scope Guard", res_val["steps_evaluation"][0]["reason"])

        # 2. Ejecución real paso a paso
        scope_data = {
            "scope": {
                "in_scope": {"domains": ["target.local"], "ips": [], "cidrs": [], "endpoints": []},
                "out_of_scope": {"domains": [], "ips": [], "cidrs": [], "endpoints": []},
            }
        }
        res_step = execute_playbook_step(
            step=pb["steps"][0],
            context={"allow_active": True, "scope_data": scope_data},
            dry_run=False,
        )
        self.assertEqual(res_step["status"], "BLOCKED")
        self.assertEqual(res_step["exit_code"], 126)
        self.assertTrue(res_step["stop_condition_met"])
        self.assertIn("destino-fuera-de-alcance", res_step["output"])

        # 3. Ejecución completa del playbook
        res_run = run_playbook(pb, target_yaml_path=target_yaml, dry_run=False)
        self.assertEqual(res_run["status"], "BLOCKED")
        self.assertFalse(res_run["can_execute"])
        self.assertEqual(res_run["executed_steps_count"], 0)

    def test_active_step_with_literal_in_scope_target_is_authorized(self):
        """B3: Paso activo con destino literal en alcance es autorizado correctamente."""
        from seclab_playbook import validate_playbook_against_scope
        from authorization_fixture import AUTHORIZATION_YAML
        target_yaml = self.tmp_path / "target_literal_in_scope.yaml"
        target_yaml.write_text(DEFAULT_SCOPE_YAML + AUTHORIZATION_YAML)

        pb = {
            "id": "pb_literal_in_scope",
            "title": "Prueba Literal En Alcance",
            "version": "1.0",
            "category": "recon",
            "description": "Test B3 in scope",
            "steps": [
                {
                    "id": "step_literal_curl_in",
                    "title": "Curl En Alcance",
                    "objective": "Verificar autorización de destino literal autorizado",
                    "interaction_type": "active_low",
                    "command_template": "curl https://target.local/api",
                }
            ],
        }

        res_val = validate_playbook_against_scope(pb, target_yaml)
        self.assertTrue(res_val["can_execute"])
        self.assertEqual(res_val["blocked_steps_count"], 0)
        self.assertEqual(res_val["steps_evaluation"][0]["status"], "AUTHORIZED")

    def test_active_step_without_targets_is_blocked(self):
        """B3: Paso activo sin destino resoluble ni declarado (ej. printf) es bloqueado en ejecución real."""
        from seclab_playbook import execute_playbook_step, run_playbook, validate_playbook_against_scope
        from authorization_fixture import AUTHORIZATION_YAML
        target_yaml = self.tmp_path / "target_no_targets.yaml"
        target_yaml.write_text(DEFAULT_SCOPE_YAML + AUTHORIZATION_YAML)

        pb = {
            "id": "pb_no_targets",
            "title": "Prueba Sin Destinos",
            "version": "1.0",
            "category": "recon",
            "description": "Test B3 sin destinos",
            "steps": [
                {
                    "id": "step_cmd_sleep",
                    "title": "Sleep Sin Destino",
                    "objective": "Comando inocuo sin objetivos de red",
                    "interaction_type": "active_low",
                    "command_template": "sleep 10",
                }
            ],
        }

        # Validación estática debe bloquear por falta de destino declarable
        res_val = validate_playbook_against_scope(pb, target_yaml)
        self.assertFalse(res_val["can_execute"])
        self.assertEqual(res_val["blocked_steps_count"], 1)
        self.assertEqual(res_val["steps_evaluation"][0]["status"], "BLOCKED")
        self.assertIn("no declara una fuente de destino resoluble", res_val["steps_evaluation"][0]["reason"])

        # Ejecución real debe bloquear con código 126
        scope_data = {
            "scope": {
                "in_scope": {"domains": ["target.local"], "ips": [], "cidrs": [], "endpoints": []},
                "out_of_scope": {"domains": [], "ips": [], "cidrs": [], "endpoints": []},
            }
        }
        res_step = execute_playbook_step(
            step=pb["steps"][0],
            context={"allow_active": True, "scope_data": scope_data},
            dry_run=False,
        )
        self.assertEqual(res_step["status"], "BLOCKED")
        self.assertEqual(res_step["exit_code"], 126)
        self.assertTrue(res_step["stop_condition_met"])
        self.assertIn("requiere un objetivo verificable", res_step["output"])

        # Ejecución en run_playbook
        res_run = run_playbook(pb, target_yaml_path=target_yaml, dry_run=False)
        self.assertEqual(res_run["status"], "BLOCKED")
        self.assertFalse(res_run["can_execute"])
        self.assertEqual(res_run["executed_steps_count"], 0)

    def test_b3_literal_targets_mixed_and_unrecognized_formats_blocked(self):
        """B3: Bloqueo estricto de destinos literales mixtos (host/path, bare IPv6, esquema FTP)."""
        from seclab_playbook import execute_playbook_step, run_playbook, validate_playbook_against_scope, extract_step_targets
        from authorization_fixture import AUTHORIZATION_YAML
        target_yaml = self.tmp_path / "target_b3_mixed.yaml"
        target_yaml.write_text(DEFAULT_SCOPE_YAML + AUTHORIZATION_YAML)

        scope_data = {
            "scope": {
                "in_scope": {"domains": ["target.local"], "ips": ["127.0.0.1"], "cidrs": [], "endpoints": []},
                "out_of_scope": {"domains": ["evil.com"], "ips": [], "cidrs": [], "endpoints": []},
            }
        }

        # Caso 1: host/path mixto (target.local y evil.com/path)
        step_mixed = {
            "id": "step_mixed",
            "title": "Paso mixto con host/path",
            "objective": "Verificar que evil.com/path sea interceptado",
            "interaction_type": "active_low",
            "command_template": "curl https://target.local evil.com/path",
        }
        targets_mixed, _ = extract_step_targets(step_mixed, context={"target_yaml_path": target_yaml})
        self.assertIn("https://target.local", targets_mixed)
        self.assertTrue(any("evil.com" in t for t in targets_mixed))

        pb_mixed = {
            "id": "pb_mixed",
            "title": "Playbook Mixto",
            "version": "1.0",
            "category": "recon",
            "description": "Test B3 mixto",
            "steps": [step_mixed],
        }
        val_mixed = validate_playbook_against_scope(pb_mixed, target_yaml)
        self.assertFalse(val_mixed["can_execute"])
        self.assertEqual(val_mixed["steps_evaluation"][0]["status"], "BLOCKED")
        self.assertIn("evil.com", val_mixed["steps_evaluation"][0]["reason"])

        step_res_mixed = execute_playbook_step(step_mixed, context={"allow_active": True, "scope_data": scope_data}, dry_run=False)
        self.assertEqual(step_res_mixed["status"], "BLOCKED")
        self.assertEqual(step_res_mixed["exit_code"], 126)
        self.assertIn("evil.com", step_res_mixed["output"])

        # Caso 2: IPv6 sin corchetes no autorizado (2001:db8::bad)
        step_ipv6 = {
            "id": "step_ipv6",
            "title": "Paso con IPv6 sin corchetes",
            "objective": "Verificar intercepción de IPv6 sin corchetes",
            "interaction_type": "active_low",
            "command_template": "nmap target.local 2001:db8::bad",
        }
        targets_ipv6, _ = extract_step_targets(step_ipv6, context={"target_yaml_path": target_yaml})
        self.assertIn("2001:db8::bad", targets_ipv6)

        pb_ipv6 = {
            "id": "pb_ipv6",
            "title": "Playbook IPv6",
            "version": "1.0",
            "category": "recon",
            "description": "Test B3 IPv6",
            "steps": [step_ipv6],
        }
        val_ipv6 = validate_playbook_against_scope(pb_ipv6, target_yaml)
        self.assertFalse(val_ipv6["can_execute"])
        self.assertEqual(val_ipv6["steps_evaluation"][0]["status"], "BLOCKED")
        self.assertIn("2001:db8::bad", val_ipv6["steps_evaluation"][0]["reason"])

        step_res_ipv6 = execute_playbook_step(step_ipv6, context={"allow_active": True, "scope_data": scope_data}, dry_run=False)
        self.assertEqual(step_res_ipv6["status"], "BLOCKED")
        self.assertEqual(step_res_ipv6["exit_code"], 126)
        self.assertIn("2001:db8::bad", step_res_ipv6["output"])

        # Caso 3: Esquema distinto de HTTP/HTTPS (ftp://evil.com)
        step_ftp = {
            "id": "step_ftp",
            "title": "Paso con esquema FTP",
            "objective": "Verificar intercepción de esquema FTP",
            "interaction_type": "active_low",
            "command_template": "wget https://target.local ftp://evil.com",
        }
        targets_ftp, _ = extract_step_targets(step_ftp, context={"target_yaml_path": target_yaml})
        self.assertIn("ftp://evil.com", targets_ftp)

        pb_ftp = {
            "id": "pb_ftp",
            "title": "Playbook FTP",
            "version": "1.0",
            "category": "recon",
            "description": "Test B3 FTP",
            "steps": [step_ftp],
        }
        val_ftp = validate_playbook_against_scope(pb_ftp, target_yaml)
        self.assertFalse(val_ftp["can_execute"])
        self.assertEqual(val_ftp["steps_evaluation"][0]["status"], "BLOCKED")

        step_res_ftp = execute_playbook_step(step_ftp, context={"allow_active": True, "scope_data": scope_data}, dry_run=False)
        self.assertEqual(step_res_ftp["status"], "BLOCKED")
        self.assertEqual(step_res_ftp["exit_code"], 126)

    def test_b3_literal_targets_in_scope_with_paths_and_ports_allowed(self):
        """B3: Destinos literales en alcance con rutas y puertos son autorizados correctamente."""
        from seclab_playbook import validate_playbook_against_scope, execute_playbook_step
        from authorization_fixture import AUTHORIZATION_YAML
        target_yaml = self.tmp_path / "target_b3_allowed.yaml"
        target_yaml.write_text(DEFAULT_SCOPE_YAML + AUTHORIZATION_YAML)

        scope_data = {
            "scope": {
                "in_scope": {"domains": ["target.local"], "ips": ["127.0.0.1"], "cidrs": [], "endpoints": []},
                "out_of_scope": {"domains": [], "ips": [], "cidrs": [], "endpoints": []},
            }
        }

        step = {
            "id": "step_allowed_literals",
            "title": "Literales autorizados",
            "objective": "Verificar paso activo con destinos literales en alcance",
            "interaction_type": "active_low",
            "command_template": "curl https://target.local/api target.local:443/test",
        }
        pb = {
            "id": "pb_allowed_lit",
            "title": "Playbook Autorizado",
            "version": "1.0",
            "category": "recon",
            "description": "Test B3 permitido",
            "steps": [step],
        }
        val = validate_playbook_against_scope(pb, target_yaml)
        self.assertTrue(val["can_execute"])
        self.assertEqual(val["steps_evaluation"][0]["status"], "AUTHORIZED")

    def test_b3_dynamic_shell_substitutions_blocked(self):
        """B3: Destinos dinámicos no verificables ($VAR, `cmd`, $(cmd)) son bloqueados fail-closed."""
        from seclab_playbook import validate_playbook_against_scope, execute_playbook_step
        from authorization_fixture import AUTHORIZATION_YAML
        target_yaml = self.tmp_path / "target_b3_dynamic.yaml"
        target_yaml.write_text(DEFAULT_SCOPE_YAML + AUTHORIZATION_YAML)

        scope_data = {
            "scope": {
                "in_scope": {"domains": ["target.local"], "ips": ["127.0.0.1"], "cidrs": [], "endpoints": []},
                "out_of_scope": {"domains": [], "ips": [], "cidrs": [], "endpoints": []},
            }
        }

        for dynamic_cmd in ("curl $TARGET_HOST", "curl ${EVIL_TARGET}", "curl $(cat hosts.txt)", "curl `cat hosts.txt`"):
            step = {
                "id": "step_dyn",
                "title": "Paso dinámico",
                "objective": "Test dinámico",
                "interaction_type": "active_low",
                "command_template": dynamic_cmd,
            }
            pb = {
                "id": "pb_dyn",
                "title": "Playbook Dinámico",
                "version": "1.0",
                "category": "recon",
                "description": "Test B3 dinámico",
                "steps": [step],
            }
            val = validate_playbook_against_scope(pb, target_yaml)
            self.assertFalse(val["can_execute"])
            self.assertEqual(val["steps_evaluation"][0]["status"], "BLOCKED")
            self.assertIn("destinos dinámicos", val["steps_evaluation"][0]["reason"])

            step_res = execute_playbook_step(step, context={"allow_active": True, "scope_data": scope_data}, dry_run=False)
            self.assertEqual(step_res["status"], "BLOCKED")
            self.assertEqual(step_res["exit_code"], 126)
            self.assertIn("destinos dinámicos", step_res["output"])

    def test_m4_m5_empty_input_file_blocks_and_differentiates_artifacts(self):
        """M4/M5: Archivos de objetivos vacíos fallan cerrado y se diferencian de artefactos de entrada."""
        from seclab_playbook import validate_playbook_against_scope, execute_playbook_step
        from authorization_fixture import AUTHORIZATION_YAML
        target_yaml = self.tmp_path / "target_m4_m5.yaml"
        target_yaml.write_text(DEFAULT_SCOPE_YAML + AUTHORIZATION_YAML)

        recon_dir = self.tmp_path / "recon"
        recon_dir.mkdir(parents=True, exist_ok=True)
        empty_targets_file = recon_dir / "empty.txt"
        empty_targets_file.write_text("", encoding="utf-8")

        # 1. Paso activo con lista de objetivos vacía -> BLOCKED tanto estático como real (M4)
        step_empty_input = {
            "id": "step_empty_targets",
            "title": "Paso con archivo vacío",
            "objective": "Verificar bloqueo de paso activo con archivo de objetivos vacío",
            "interaction_type": "active_low",
            "inputs": ["recon/empty.txt"],
            "command_template": "httpx -l recon/empty.txt",
        }
        pb_m4 = {
            "id": "pb_m4",
            "title": "Playbook M4",
            "version": "1.0",
            "category": "recon",
            "description": "Test M4",
            "steps": [step_empty_input],
        }
        val_m4 = validate_playbook_against_scope(pb_m4, target_yaml)
        self.assertFalse(val_m4["can_execute"])
        self.assertEqual(val_m4["steps_evaluation"][0]["status"], "BLOCKED")
        self.assertIn("recon/empty.txt", val_m4["steps_evaluation"][0]["reason"])

        scope_data = {
            "scope": {
                "in_scope": {"domains": ["target.local"], "ips": ["127.0.0.1"], "cidrs": [], "endpoints": []},
                "out_of_scope": {"domains": [], "ips": [], "cidrs": [], "endpoints": []},
            }
        }
        step_res_m4 = execute_playbook_step(
            step_empty_input,
            context={"engagement_dir": str(self.tmp_path), "allow_active": True, "scope_data": scope_data},
            dry_run=False,
        )
        self.assertEqual(step_res_m4["status"], "BLOCKED")
        self.assertEqual(step_res_m4["exit_code"], 126)
        self.assertIn("recon/empty.txt", step_res_m4["output"])

        # 2. Paso GraphQL con {domain} y artefacto JSON como input -> AUTHORIZED (M5)
        # El archivo JSON es un artefacto de salida/dependencia de datos, NO una lista de objetivos.
        step_graphql_artifact = {
            "id": "step_graphql_field_probe",
            "title": "Paso GraphQL con artefacto JSON",
            "objective": "Verificar que el artefacto JSON no sea tratado como lista de objetivos",
            "interaction_type": "active_low",
            "target_selector": "in_scope_domains",
            "inputs": ["recon/graphql_introspection.json"],
            "command_template": "curl -s -X POST https://{domain}/graphql -H Content-Type:application/json -o recon/graphql_fields.json",
        }
        pb_m5 = {
            "id": "pb_m5",
            "title": "Playbook M5 GraphQL",
            "version": "1.0",
            "category": "api_audit",
            "description": "Test M5",
            "steps": [step_graphql_artifact],
        }
        val_m5 = validate_playbook_against_scope(pb_m5, target_yaml, parameters={"domain": "target.local"})
        self.assertTrue(val_m5["can_execute"])
        self.assertEqual(val_m5["steps_evaluation"][0]["status"], "AUTHORIZED")

    def test_b3_m6_single_label_hosts_and_argument_collisions_blocked(self):
        """B3/M6: Extracción y bloqueo fail-closed de hosts de una sola etiqueta y colisiones en posición de argumento."""
        from seclab_playbook import validate_playbook_against_scope, execute_playbook_step
        from authorization_fixture import AUTHORIZATION_YAML
        target_yaml = self.tmp_path / "target_b3_m6.yaml"
        target_yaml.write_text(DEFAULT_SCOPE_YAML + AUTHORIZATION_YAML)

        scope_data = {
            "scope": {
                "in_scope": {"domains": ["target.local"], "ips": ["127.0.0.1"], "cidrs": [], "endpoints": []},
                "out_of_scope": {"domains": [], "ips": [], "cidrs": [], "endpoints": []},
            }
        }

        # Casos requeridos por la auditoría: localhost, db, service, y colisiones test, get, query, true, false
        commands_to_test = [
            "curl target.local localhost",
            "curl target.local db",
            "curl target.local service",
            "curl target.local test",
            "curl target.local get",
            "curl target.local query",
            "curl target.local true",
            "curl target.local false",
            "printf '%s' target.local localhost",
            "nmap -sT -p 80 target.local localhost",
        ]

        for idx, cmd in enumerate(commands_to_test):
            step = {
                "id": f"step_b3_m6_{idx}",
                "title": f"Test {cmd}",
                "objective": "Verificar bloqueo de host no autorizado",
                "interaction_type": "active_low",
                "command_template": cmd,
            }
            pb = {
                "id": f"pb_b3_m6_{idx}",
                "title": "Playbook B3/M6",
                "version": "1.0",
                "category": "recon",
                "description": "B3 M6 single label test",
                "steps": [step],
            }

            # 1. Validación estática debe bloquear
            val = validate_playbook_against_scope(pb, target_yaml)
            self.assertFalse(val["can_execute"], f"Fallo al bloquear estáticamente comando: {cmd}")
            self.assertEqual(val["steps_evaluation"][0]["status"], "BLOCKED")

            # 2. Ejecución real debe bloquear con código 126
            step_res = execute_playbook_step(
                step,
                context={"allow_active": True, "scope_data": scope_data},
                dry_run=False,
            )
            self.assertEqual(step_res["status"], "BLOCKED", f"Fallo al bloquear en ejecución comando: {cmd}")
            self.assertEqual(step_res["exit_code"], 126)
            self.assertTrue(step_res["stop_condition_met"])
            self.assertIn("Scope Guard", step_res["output"])

    def test_b3_subprocess_run_never_invoked_on_blocked_step(self):
        """B3: Verificar mediante mock que ningún paso bloqueado invoque subprocess.run()."""
        from unittest.mock import patch
        from seclab_playbook import run_playbook, execute_playbook_step
        from authorization_fixture import AUTHORIZATION_YAML
        target_yaml = self.tmp_path / "target_mock.yaml"
        target_yaml.write_text(DEFAULT_SCOPE_YAML + AUTHORIZATION_YAML)

        step_blocked = {
            "id": "step_blocked_test",
            "title": "Paso Bloqueado",
            "objective": "Comprobar no invocación de subprocesos",
            "interaction_type": "active_low",
            "command_template": "curl target.local localhost",
        }
        pb = {
            "id": "pb_mock_run",
            "title": "Playbook Mock Test",
            "version": "1.0",
            "category": "recon",
            "description": "Mock subprocess test",
            "steps": [step_blocked],
        }

        with patch("subprocess.run") as mock_run:
            # 1. execute_playbook_step directo
            scope_data = {
                "scope": {
                    "in_scope": {"domains": ["target.local"], "ips": ["127.0.0.1"], "cidrs": [], "endpoints": []},
                    "out_of_scope": {"domains": [], "ips": [], "cidrs": [], "endpoints": []},
                }
            }
            res_step = execute_playbook_step(
                step_blocked,
                context={"allow_active": True, "scope_data": scope_data},
                dry_run=False,
            )
            self.assertEqual(res_step["status"], "BLOCKED")
            self.assertEqual(res_step["exit_code"], 126)
            mock_run.assert_not_called()

            # 2. run_playbook orquestado
            res_pb = run_playbook(
                pb,
                target_yaml_path=target_yaml,
                dry_run=False,
            )
            self.assertEqual(res_pb["status"], "BLOCKED")
            mock_run.assert_not_called()

    def test_b3_single_label_hosts_in_scope_allowed(self):
        """B3: Hosts de una sola etiqueta autorizados explícitamente en el scope son permitidos."""
        from seclab_playbook import validate_playbook_against_scope, execute_playbook_step
        from authorization_fixture import AUTHORIZATION_YAML
        target_yaml = self.tmp_path / "target_single_label_in_scope.yaml"
        scope_single_labels = (
            "scope:\n"
            "  in_scope:\n"
            "    domains: ['target.local', 'localhost', 'db']\n"
            "    ips: ['127.0.0.1']\n"
            "    cidrs: []\n"
            "    endpoints: []\n"
            "  out_of_scope:\n"
            "    domains: []\n"
            "    ips: []\n"
            "    cidrs: []\n"
            "    endpoints: []\n"
        )
        target_yaml.write_text(scope_single_labels + AUTHORIZATION_YAML)

        step_in_scope = {
            "id": "step_in_scope_local",
            "title": "Localhost y DB en Scope",
            "objective": "Verificar autorización de single-label hosts autorizados",
            "interaction_type": "active_low",
            "command_template": "curl http://localhost http://db",
        }
        pb = {
            "id": "pb_single_label_in_scope",
            "title": "Playbook Single Labels In Scope",
            "version": "1.0",
            "category": "recon",
            "description": "Single labels authorized",
            "steps": [step_in_scope],
        }

        val = validate_playbook_against_scope(pb, target_yaml)
        self.assertTrue(val["can_execute"])
        self.assertEqual(val["steps_evaluation"][0]["status"], "AUTHORIZED")

    def test_m4_unexpanded_placeholders_fail_closed_statically(self):
        """M4: Placeholders de destino sin parámetros suministrados fallan cerrado estáticamente y en ejecución real."""
        from seclab_playbook import validate_playbook_against_scope, execute_playbook_step
        from authorization_fixture import AUTHORIZATION_YAML
        target_yaml = self.tmp_path / "target_m4_placeholders.yaml"
        target_yaml.write_text(DEFAULT_SCOPE_YAML + AUTHORIZATION_YAML)

        step_unexpanded = {
            "id": "step_active_placeholder",
            "title": "Paso Activo con Placeholder sin Parámetro",
            "objective": "Verificar paridad estática fail-closed",
            "interaction_type": "active_low",
            "command_template": "curl https://{domain}",
        }
        pb = {
            "id": "pb_m4_unexpanded",
            "title": "Playbook M4 Unexpanded Placeholder",
            "version": "1.0",
            "category": "recon",
            "description": "M4 test placeholder without param",
            "steps": [step_unexpanded],
        }

        # 1. Sin parámetro domain provisto -> validate_playbook_against_scope DEBE fallar cerrado (can_execute=False, BLOCKED)
        val_no_param = validate_playbook_against_scope(pb, target_yaml)
        self.assertFalse(val_no_param["can_execute"])
        self.assertEqual(val_no_param["steps_evaluation"][0]["status"], "BLOCKED")
        self.assertIn("placeholders de destino sin resolver", val_no_param["steps_evaluation"][0]["reason"])

        # 2. Sin parámetro domain provisto en ejecución real -> execute_playbook_step bloquea con exit code 126
        scope_data = {
            "scope": {
                "in_scope": {"domains": ["target.local"], "ips": ["127.0.0.1"], "cidrs": [], "endpoints": []},
                "out_of_scope": {"domains": [], "ips": [], "cidrs": [], "endpoints": []},
            }
        }
        res_exec_no_param = execute_playbook_step(
            step_unexpanded,
            context={"allow_active": True, "scope_data": scope_data},
            dry_run=False,
        )
        self.assertEqual(res_exec_no_param["status"], "BLOCKED")
        self.assertEqual(res_exec_no_param["exit_code"], 126)
        self.assertTrue(res_exec_no_param["stop_condition_met"])

        # 3. Con parámetro domain provisto en alcance -> autorizado estáticamente
        val_with_param = validate_playbook_against_scope(pb, target_yaml, parameters={"domain": "target.local"})
        self.assertTrue(val_with_param["can_execute"])
        self.assertEqual(val_with_param["steps_evaluation"][0]["status"], "AUTHORIZED")

    def test_b3_proxy_flags_extraction_and_blocking(self):
        """B3: Banderas de proxy (-x, --proxy, -x=, --proxy=) extraen destinos y bloquean tráfico no autorizado."""
        from seclab_playbook import validate_playbook_against_scope, execute_playbook_step, _extract_literal_targets
        from authorization_fixture import AUTHORIZATION_YAML
        target_yaml = self.tmp_path / "target_b3_proxies.yaml"
        target_yaml.write_text(DEFAULT_SCOPE_YAML + AUTHORIZATION_YAML)

        scope_data = {
            "scope": {
                "in_scope": {"domains": ["target.local"], "ips": ["127.0.0.1"], "cidrs": [], "endpoints": []},
                "out_of_scope": {"domains": ["evil.com"], "ips": [], "cidrs": [], "endpoints": []},
            }
        }

        proxy_cases = [
            ("curl -x evil.com https://target.local", ["https://target.local", "evil.com"]),
            ("curl --proxy evil.com https://target.local", ["https://target.local", "evil.com"]),
            ("curl --proxy=evil.com https://target.local", ["https://target.local", "evil.com"]),
            ("curl -x=evil.com https://target.local", ["https://target.local", "evil.com"]),
            ("curl -x localhost https://target.local", ["https://target.local", "localhost"]),
        ]

        for cmd, expected_targets in proxy_cases:
            # 1. Extracción sintáctica exhaustiva de proxy
            extracted = _extract_literal_targets(cmd)
            for exp in expected_targets:
                self.assertIn(exp, extracted, f"Fallo extracción de {exp} en '{cmd}': {extracted}")

            # 2. Validación estática contra alcance (evil.com o localhost fuera de alcance)
            step = {
                "id": "step_proxy_audit",
                "title": "Prueba de Proxy",
                "objective": "Verificar bloqueo de proxies no autorizados",
                "interaction_type": "active_low",
                "command_template": cmd,
            }
            pb = {
                "id": "pb_proxy_test",
                "title": "Playbook Proxy Test",
                "version": "1.0",
                "category": "recon",
                "description": "Prueba de B3 proxy flags",
                "steps": [step],
            }
            val = validate_playbook_against_scope(pb, target_yaml)
            self.assertFalse(val["can_execute"], f"Validación estática autorizó indebidamente '{cmd}'")
            self.assertEqual(val["steps_evaluation"][0]["status"], "BLOCKED")

            # 3. Verificación mockeada en ejecución real: subprocess.run NUNCA debe ser llamado
            with unittest.mock.patch("subprocess.run") as mock_run:
                res = execute_playbook_step(
                    step,
                    context={"allow_active": True, "scope_data": scope_data},
                    dry_run=False,
                )
                self.assertEqual(res["status"], "BLOCKED")
                self.assertEqual(res["exit_code"], 126)
                self.assertTrue(res["stop_condition_met"])
                mock_run.assert_not_called()

    def test_b3_flag_case_sensitivity_and_non_target_flags(self):
        """B3: Sensibilidad a mayúsculas (-X vs -x) y preservación de flags como -O."""
        from seclab_playbook import validate_playbook_against_scope, _extract_literal_targets
        from authorization_fixture import AUTHORIZATION_YAML
        target_yaml = self.tmp_path / "target_b3_flags.yaml"
        target_yaml.write_text(DEFAULT_SCOPE_YAML + AUTHORIZATION_YAML)

        # 1. -X (método HTTP) vs -x (proxy): POST nunca debe ser extraído como host
        extracted_post = _extract_literal_targets("curl -X POST https://target.local")
        self.assertEqual(extracted_post, ["https://target.local"])
        self.assertNotIn("POST", extracted_post)

        # 2. -O (remote-name output) no consume el destino siguiente
        extracted_o = _extract_literal_targets("curl -O https://target.local")
        self.assertEqual(extracted_o, ["https://target.local"])

        # 3. Banderas combinadas complejas
        cmd_complex = "curl -s -X POST https://target.local -H Content-Type:application/json -o recon/out.json"
        extracted_complex = _extract_literal_targets(cmd_complex)
        self.assertEqual(extracted_complex, ["https://target.local"])

        # 4. Ambos comandos son autorizados contra target_yaml porque sus destinos son válidos
        for cmd in ["curl -X POST https://target.local", "curl -O https://target.local"]:
            pb = {
                "id": "pb_flag_test",
                "title": "Playbook Flag Test",
                "version": "1.0",
                "category": "recon",
                "description": "Prueba flags válidos",
                "steps": [
                    {
                        "id": "step_flag_valid",
                        "title": "Paso Flag Válido",
                        "objective": "Verificar autorización",
                        "interaction_type": "active_low",
                        "command_template": cmd,
                    }
                ],
            }
            val = validate_playbook_against_scope(pb, target_yaml)
            self.assertTrue(val["can_execute"], f"Fallo autorización de '{cmd}': {val}")
            self.assertEqual(val["steps_evaluation"][0]["status"], "AUTHORIZED")

    def test_m4_mixed_unexpanded_placeholders_fail_closed(self):
        """M4: Comandos mixtos con placeholder no expandido y destino literal autorizado fallan cerrado."""
        from seclab_playbook import validate_playbook_against_scope, execute_playbook_step
        from authorization_fixture import AUTHORIZATION_YAML
        target_yaml = self.tmp_path / "target_m4_mixed.yaml"
        target_yaml.write_text(DEFAULT_SCOPE_YAML + AUTHORIZATION_YAML)

        scope_data = {
            "scope": {
                "in_scope": {"domains": ["target.local"], "ips": ["127.0.0.1"], "cidrs": [], "endpoints": []},
                "out_of_scope": {"domains": [], "ips": [], "cidrs": [], "endpoints": []},
            }
        }

        # Comando activo mixto: {domain} sin valor junto a target.local autorizado
        step_mixed = {
            "id": "step_active_mixed",
            "title": "Paso Activo Mixto",
            "objective": "Verificar paridad fail-closed en comandos mixtos",
            "interaction_type": "active_low",
            "command_template": "curl https://{domain} target.local",
        }
        pb_mixed = {
            "id": "pb_m4_mixed",
            "title": "Playbook M4 Mixed",
            "version": "1.0",
            "category": "recon",
            "description": "M4 test mixed placeholder with valid literal",
            "steps": [step_mixed],
        }

        # 1. Sin parámetros: validación estática DEBE bloquearse a pesar de target.local en alcance
        val_no_param = validate_playbook_against_scope(pb_mixed, target_yaml)
        self.assertFalse(val_no_param["can_execute"])
        self.assertEqual(val_no_param["steps_evaluation"][0]["status"], "BLOCKED")
        self.assertIn("placeholders de destino sin resolver: domain", val_no_param["steps_evaluation"][0]["reason"])

        # 2. Sin parámetros: ejecución real bloquea con exit code 126 y mock de subprocess.run confirma 0 llamadas
        with unittest.mock.patch("subprocess.run") as mock_run:
            res_exec = execute_playbook_step(
                step_mixed,
                context={"allow_active": True, "scope_data": scope_data},
                dry_run=False,
            )
            self.assertEqual(res_exec["status"], "BLOCKED")
            self.assertEqual(res_exec["exit_code"], 126)
            self.assertTrue(res_exec["stop_condition_met"])
            self.assertIn("placeholders de destino sin resolver (domain)", res_exec["output"])
            mock_run.assert_not_called()

        # 3. Con parámetro suministrado y autorizado: validación estática autoriza
        val_with_param = validate_playbook_against_scope(
            pb_mixed,
            target_yaml,
            parameters={"domain": "target.local"},
        )
        self.assertTrue(val_with_param["can_execute"])
        self.assertEqual(val_with_param["steps_evaluation"][0]["status"], "AUTHORIZED")

    def test_b3_compact_and_clustered_proxy_flags(self):
        """B3: Formas compactas (-xVALOR) y agrupadas (-sSxVALOR, -sSx VALOR) extraen destinos y bloquean tráfico no autorizado."""
        from seclab_playbook import validate_playbook_against_scope, execute_playbook_step, _extract_literal_targets
        from authorization_fixture import AUTHORIZATION_YAML
        target_yaml = self.tmp_path / "target_b3_compact_proxies.yaml"
        target_yaml.write_text(DEFAULT_SCOPE_YAML + AUTHORIZATION_YAML)

        scope_data = {
            "scope": {
                "in_scope": {"domains": ["target.local"], "ips": ["127.0.0.1"], "cidrs": [], "endpoints": []},
                "out_of_scope": {"domains": ["evil.com"], "ips": [], "cidrs": [], "endpoints": []},
            }
        }

        cases = [
            ("curl -xevil.com https://target.local", ["https://target.local", "evil.com"]),
            ("curl -sSxevil.com https://target.local", ["https://target.local", "evil.com"]),
            ("curl -sSx evil.com https://target.local", ["https://target.local", "evil.com"]),
        ]

        for cmd, expected_targets in cases:
            # 1. Extracción sintáctica exhaustiva de proxy compacto/agrupado
            extracted = _extract_literal_targets(cmd)
            for exp in expected_targets:
                self.assertIn(exp, extracted, f"Fallo extracción de {exp} en '{cmd}': {extracted}")

            step = {
                "id": "step_compact_proxy",
                "title": "Prueba Proxy Compacto",
                "objective": "Verificar bloqueo de proxy compacto fuera de alcance",
                "interaction_type": "active_low",
                "command_template": cmd,
            }
            pb = {
                "id": "pb_compact_proxy_test",
                "title": "Playbook Compact Proxy Test",
                "version": "1.0",
                "category": "recon",
                "description": "Prueba de B3 compact proxy flags",
                "steps": [step],
            }

            # 2. Validación estática bloquea
            val = validate_playbook_against_scope(pb, target_yaml)
            self.assertFalse(val["can_execute"], f"Validación estática autorizó indebidamente '{cmd}'")
            self.assertEqual(val["steps_evaluation"][0]["status"], "BLOCKED")

            # 3. Verificación con mock: subprocess.run NUNCA debe ser llamado
            with unittest.mock.patch("subprocess.run") as mock_run:
                res = execute_playbook_step(
                    step,
                    context={"allow_active": True, "scope_data": scope_data},
                    dry_run=False,
                )
                self.assertEqual(res["status"], "BLOCKED")
                self.assertEqual(res["exit_code"], 126)
                self.assertTrue(res["stop_condition_met"])
                mock_run.assert_not_called()

        # Control: proxy compacto autorizado
        pb_control = {
            "id": "pb_control",
            "title": "Control",
            "version": "1.0",
            "category": "recon",
            "description": "Control",
            "steps": [
                {
                    "id": "step_ctrl",
                    "title": "Ctrl",
                    "objective": "Ctrl",
                    "interaction_type": "active_low",
                    "command_template": "curl -xtarget.local https://target.local",
                }
            ],
        }
        val_ctrl = validate_playbook_against_scope(pb_control, target_yaml)
        self.assertTrue(val_ctrl["can_execute"])
        self.assertEqual(val_ctrl["steps_evaluation"][0]["status"], "AUTHORIZED")

    def test_m4_placeholders_under_target_flags_fail_closed(self):
        """M4: Placeholders sin resolver bajo cualquier bandera de destino declarada fallan cerrado."""
        from seclab_playbook import validate_playbook_against_scope, execute_playbook_step
        from authorization_fixture import AUTHORIZATION_YAML
        target_yaml = self.tmp_path / "target_m4_flags.yaml"
        target_yaml.write_text(DEFAULT_SCOPE_YAML + AUTHORIZATION_YAML)

        scope_data = {
            "scope": {
                "in_scope": {"domains": ["target.local"], "ips": ["127.0.0.1"], "cidrs": [], "endpoints": []},
                "out_of_scope": {"domains": [], "ips": [], "cidrs": [], "endpoints": []},
            }
        }

        # 1. Caso de auditoría: openssl s_client -connect {peer}:443 -servername target.local
        step_openssl = {
            "id": "step_openssl",
            "title": "OpenSSL S_Client Step",
            "objective": "Verificar placeholder bajo -connect",
            "interaction_type": "active_low",
            "command_template": "openssl s_client -connect {peer}:443 -servername target.local",
        }
        pb_openssl = {
            "id": "pb_openssl_test",
            "title": "OpenSSL Connect Test",
            "version": "1.0",
            "category": "recon",
            "description": "Prueba placeholder peer",
            "steps": [step_openssl],
        }

        # Sin parámetro peer: bloquea estáticamente
        val_no_peer = validate_playbook_against_scope(pb_openssl, target_yaml)
        self.assertFalse(val_no_peer["can_execute"])
        self.assertEqual(val_no_peer["steps_evaluation"][0]["status"], "BLOCKED")
        self.assertIn("placeholders de destino sin resolver: peer", val_no_peer["steps_evaluation"][0]["reason"])

        # Sin parámetro peer: ejecución real bloquea con código 126 y subprocess.run no se invoca
        with unittest.mock.patch("subprocess.run") as mock_run:
            res_exec = execute_playbook_step(
                step_openssl,
                context={"allow_active": True, "scope_data": scope_data},
                dry_run=False,
            )
            self.assertEqual(res_exec["status"], "BLOCKED")
            self.assertEqual(res_exec["exit_code"], 126)
            self.assertTrue(res_exec["stop_condition_met"])
            mock_run.assert_not_called()

        # Con parámetro peer autorizado: autoriza
        val_peer_ok = validate_playbook_against_scope(
            pb_openssl,
            target_yaml,
            parameters={"peer": "target.local"},
        )
        self.assertTrue(val_peer_ok["can_execute"])
        self.assertEqual(val_peer_ok["steps_evaluation"][0]["status"], "AUTHORIZED")

        # 2. Casos paramétricos bajo diversas banderas de destino
        unexpanded_flag_cases = [
            ("curl --proxy {p} https://target.local", "p"),
            ("curl --socks5 {p}:1080 https://target.local", "p"),
            ("curl -x{p} https://target.local", "p"),
            ("curl -sSx{p} https://target.local", "p"),
        ]
        for cmd_tpl, ph_name in unexpanded_flag_cases:
            step = {
                "id": "step_flag_ph",
                "title": "Paso Placeholder Flag",
                "objective": "Verificar bloqueo",
                "interaction_type": "active_low",
                "command_template": cmd_tpl,
            }
            pb = {
                "id": "pb_test",
                "title": "PB Test",
                "version": "1.0",
                "category": "recon",
                "description": "Test",
                "steps": [step],
            }
            val = validate_playbook_against_scope(pb, target_yaml)
            self.assertFalse(val["can_execute"], f"Validación debió bloquear '{cmd_tpl}'")
            self.assertEqual(val["steps_evaluation"][0]["status"], "BLOCKED")

    def test_b3_interpolated_positional_parameter_validates_against_scope(self):
        """B3: Parámetros posicionales no canónicos interpolados son validados contra Scope Guard y fallan cerrado."""
        from seclab_playbook import validate_playbook_against_scope, execute_playbook_step, extract_step_targets
        from authorization_fixture import AUTHORIZATION_YAML
        target_yaml = self.tmp_path / "target_b3_asset_param.yaml"
        target_yaml.write_text(DEFAULT_SCOPE_YAML + AUTHORIZATION_YAML)

        scope_data = {
            "scope": {
                "in_scope": {"domains": ["target.local"], "ips": ["127.0.0.1"], "cidrs": [], "endpoints": []},
                "out_of_scope": {"domains": ["evil.com"], "ips": [], "cidrs": [], "endpoints": []},
            }
        }

        step = {
            "id": "step_asset_positional",
            "title": "Paso Posicional Asset",
            "objective": "Verificar validación de parámetro asset",
            "interaction_type": "active_low",
            "command_template": "curl {asset} target.local",
        }
        pb = {
            "id": "pb_asset_test",
            "title": "Playbook Asset Test",
            "version": "1.0",
            "category": "recon",
            "description": "Prueba de parámetro posicional no canónico",
            "steps": [step],
        }

        # 1. Caso auditoría: parameters={"asset": "evil.com"} (fuera de alcance)
        targets_extracted, _ = extract_step_targets(
            step,
            context={"parameters": {"asset": "evil.com"}},
            dry_run=True,
        )
        self.assertIn("evil.com", targets_extracted)
        self.assertIn("target.local", targets_extracted)

        val_evil = validate_playbook_against_scope(pb, target_yaml, parameters={"asset": "evil.com"})
        self.assertFalse(val_evil["can_execute"])
        self.assertEqual(val_evil["steps_evaluation"][0]["status"], "BLOCKED")
        self.assertIn("evil.com", val_evil["steps_evaluation"][0]["reason"])

        with unittest.mock.patch("subprocess.run") as mock_run:
            res_evil = execute_playbook_step(
                step,
                context={
                    "allow_active": True,
                    "scope_data": scope_data,
                    "parameters": {"asset": "evil.com"},
                },
                dry_run=False,
            )
            self.assertEqual(res_evil["status"], "BLOCKED")
            self.assertEqual(res_evil["exit_code"], 126)
            self.assertTrue(res_evil["stop_condition_met"])
            mock_run.assert_not_called()

        # 2. Sin parámetro: debe bloquear por placeholder sin resolver
        val_no_param = validate_playbook_against_scope(pb, target_yaml, parameters={})
        self.assertFalse(val_no_param["can_execute"])
        self.assertEqual(val_no_param["steps_evaluation"][0]["status"], "BLOCKED")
        self.assertIn("asset", val_no_param["steps_evaluation"][0]["reason"])

        with unittest.mock.patch("subprocess.run") as mock_run:
            res_no_param = execute_playbook_step(
                step,
                context={"allow_active": True, "scope_data": scope_data, "parameters": {}},
                dry_run=False,
            )
            self.assertEqual(res_no_param["status"], "BLOCKED")
            self.assertEqual(res_no_param["exit_code"], 126)
            self.assertTrue(res_no_param["stop_condition_met"])
            mock_run.assert_not_called()

        # 3. Control: parameters={"asset": "target.local"} (autorizado)
        val_ok = validate_playbook_against_scope(pb, target_yaml, parameters={"asset": "target.local"})
        self.assertTrue(val_ok["can_execute"])
        self.assertEqual(val_ok["steps_evaluation"][0]["status"], "AUTHORIZED")

    def test_b1_target_flag_precedence_over_non_target_name_and_trailing_dot_fqdn(self):
        """B1: La posición inequívoca de destino prevalece sobre el nombre del placeholder y FQDN con punto terminal se extrae y bloquea."""
        from seclab_playbook import (
            validate_playbook_against_scope,
            execute_playbook_step,
            extract_step_targets,
            is_target_placeholder,
            _extract_literal_targets,
        )
        from authorization_fixture import AUTHORIZATION_YAML
        target_yaml = self.tmp_path / "target_b1_proxy_precedence.yaml"
        target_yaml.write_text(DEFAULT_SCOPE_YAML + AUTHORIZATION_YAML)

        scope_data = {
            "scope": {
                "in_scope": {"domains": ["target.local"], "ips": ["127.0.0.1"], "cidrs": [], "endpoints": []},
                "out_of_scope": {"domains": ["evil.com"], "ips": [], "cidrs": [], "endpoints": []},
            }
        }

        # 1. Verificación sintáctica directa: la posición de bandera prevalece sobre NON_TARGET_PLACEHOLDERS ('method')
        cmd_proxy = "curl --proxy {method} https://target.local"
        self.assertTrue(is_target_placeholder("method", cmd_proxy))
        self.assertTrue(is_target_placeholder("method", "curl -x {method} https://target.local"))
        self.assertTrue(is_target_placeholder("method", "curl -x{method} https://target.local"))
        self.assertTrue(is_target_placeholder("method", "curl -sSx {method} https://target.local"))
        self.assertTrue(is_target_placeholder("method", "curl -sSx{method} https://target.local"))
        self.assertTrue(is_target_placeholder("method", "curl --proxy={method} https://target.local"))
        self.assertTrue(is_target_placeholder("method", "openssl s_client -connect {method}:443"))

        # Falso positivo prevenido: en posición no-objetivo sigue siendo no-objetivo
        self.assertFalse(is_target_placeholder("method", "curl -X {method} https://target.local"))

        # 2. Extractor literal reconoce FQDNs con punto terminal DNS
        lit_extracted = _extract_literal_targets("curl --proxy evil.com. https://target.local")
        self.assertIn("evil.com.", lit_extracted)
        self.assertIn("evil.com", lit_extracted)
        self.assertIn("https://target.local", lit_extracted)

        step = {
            "id": "step_proxy_method",
            "title": "Paso Proxy Method",
            "objective": "Verificar precedencia de bandera de proxy sobre nombre method",
            "interaction_type": "active_low",
            "command_template": cmd_proxy,
        }
        pb = {
            "id": "pb_proxy_test",
            "title": "Playbook Proxy Test",
            "version": "1.0",
            "category": "recon",
            "description": "Prueba de bandera proxy con nombre no canónico y FQDN con punto terminal",
            "steps": [step],
        }

        # 3. Caso auditoría: method="evil.com." (proxy fuera de alcance con punto terminal)
        targets_extracted, _ = extract_step_targets(
            step,
            context={"parameters": {"method": "evil.com."}},
            dry_run=True,
        )
        self.assertTrue(any("evil.com" in t for t in targets_extracted))
        self.assertIn("https://target.local", targets_extracted)

        val_evil = validate_playbook_against_scope(pb, target_yaml, parameters={"method": "evil.com."})
        self.assertFalse(val_evil["can_execute"])
        self.assertEqual(val_evil["steps_evaluation"][0]["status"], "BLOCKED")
        self.assertIn("evil.com", val_evil["steps_evaluation"][0]["reason"])

        with unittest.mock.patch("subprocess.run") as mock_run:
            res_evil = execute_playbook_step(
                step,
                context={
                    "allow_active": True,
                    "scope_data": scope_data,
                    "parameters": {"method": "evil.com."},
                },
                dry_run=False,
            )
            self.assertEqual(res_evil["status"], "BLOCKED")
            self.assertEqual(res_evil["exit_code"], 126)
            self.assertTrue(res_evil["stop_condition_met"])
            mock_run.assert_not_called()

        # 4. Sin parámetro: debe fallar cerrado por placeholder sin resolver
        val_no_param = validate_playbook_against_scope(pb, target_yaml, parameters={})
        self.assertFalse(val_no_param["can_execute"])
        self.assertEqual(val_no_param["steps_evaluation"][0]["status"], "BLOCKED")
        self.assertIn("method", val_no_param["steps_evaluation"][0]["reason"])

        with unittest.mock.patch("subprocess.run") as mock_run:
            res_no_param = execute_playbook_step(
                step,
                context={"allow_active": True, "scope_data": scope_data, "parameters": {}},
                dry_run=False,
            )
            self.assertEqual(res_no_param["status"], "BLOCKED")
            self.assertEqual(res_no_param["exit_code"], 126)
            self.assertTrue(res_no_param["stop_condition_met"])
            mock_run.assert_not_called()

        # 5. Control positivo: method="target.local" (proxy en alcance)
        val_ok = validate_playbook_against_scope(pb, target_yaml, parameters={"method": "target.local"})
        self.assertTrue(val_ok["can_execute"])
        self.assertEqual(val_ok["steps_evaluation"][0]["status"], "AUTHORIZED")

        with unittest.mock.patch("subprocess.run") as mock_run:
            mock_proc = unittest.mock.MagicMock(returncode=0, stdout="OK", stderr="")
            mock_run.return_value = mock_proc
            res_ok = execute_playbook_step(
                step,
                context={
                    "allow_active": True,
                    "scope_data": scope_data,
                    "parameters": {"method": "target.local"},
                },
                dry_run=False,
            )
            self.assertEqual(res_ok["status"], "SUCCESS")
            mock_run.assert_called_once()

    def test_m1_non_target_payload_url_exclusion_and_context_preservation(self):
        """M1: El análisis postinterpolación preserva el contexto no-objetivo (-d, -H) y no bloquea URLs en payloads de datos."""
        from seclab_playbook import (
            validate_playbook_against_scope,
            execute_playbook_step,
            extract_step_targets,
            _extract_literal_targets,
        )
        from authorization_fixture import AUTHORIZATION_YAML
        target_yaml = self.tmp_path / "target_m1_payload_context.yaml"
        target_yaml.write_text(DEFAULT_SCOPE_YAML + AUTHORIZATION_YAML)

        scope_data = {
            "scope": {
                "in_scope": {"domains": ["target.local"], "ips": ["127.0.0.1"], "cidrs": [], "endpoints": []},
                "out_of_scope": {"domains": ["client.example"], "ips": [], "cidrs": [], "endpoints": []},
            }
        }

        # 1. Extractor literal excluye URLs contenidas exclusivamente en banderas de datos (-d, --data, -H)
        cmd_interp_data = "curl -d 'https://client.example/callback' https://target.local"
        extracted_data = _extract_literal_targets(cmd_interp_data)
        self.assertIn("https://target.local", extracted_data)
        self.assertNotIn("https://client.example/callback", extracted_data)
        self.assertNotIn("client.example", extracted_data)

        cmd_interp_header = "curl -H 'Referer: https://client.example/callback' https://target.local"
        extracted_header = _extract_literal_targets(cmd_interp_header)
        self.assertIn("https://target.local", extracted_header)
        self.assertNotIn("https://client.example/callback", extracted_header)

        # 2. Paso activo con payload conteniendo URL externa bajo -d
        step_payload = {
            "id": "step_oauth_callback_payload",
            "title": "Paso OAuth Payload",
            "objective": "Enviar callback URL como payload de datos a target.local",
            "interaction_type": "active_low",
            "command_template": "curl -d '{payload}' https://target.local",
        }
        pb_payload = {
            "id": "pb_oauth_test",
            "title": "Playbook OAuth Payload Test",
            "version": "1.0",
            "category": "api",
            "description": "Prueba de no clasificación errónea de URLs en payloads",
            "steps": [step_payload],
        }

        # Extracción previa no agrega client.example a targets
        targets_extracted, _ = extract_step_targets(
            step_payload,
            context={"parameters": {"payload": "https://client.example/callback"}},
            dry_run=True,
        )
        self.assertIn("https://target.local", targets_extracted)
        self.assertNotIn("https://client.example/callback", targets_extracted)
        self.assertNotIn("client.example", targets_extracted)

        # Validación estática aprueba porque el destino real es target.local
        val_payload = validate_playbook_against_scope(
            pb_payload,
            target_yaml,
            parameters={"payload": "https://client.example/callback"},
        )
        self.assertTrue(val_payload["can_execute"])
        self.assertEqual(val_payload["steps_evaluation"][0]["status"], "AUTHORIZED")

        # Ejecución real autorizada llama a subprocess.run con el comando interpolado
        with unittest.mock.patch("subprocess.run") as mock_run:
            mock_proc = unittest.mock.MagicMock(returncode=0, stdout='{"success": true}', stderr="")
            mock_run.return_value = mock_proc
            res_payload = execute_playbook_step(
                step_payload,
                context={
                    "allow_active": True,
                    "scope_data": scope_data,
                    "parameters": {"payload": "https://client.example/callback"},
                },
                dry_run=False,
            )
            self.assertEqual(res_payload["status"], "SUCCESS")
            mock_run.assert_called_once()
            call_cmd = mock_run.call_args[0][0]
            self.assertIn("https://client.example/callback", call_cmd)
            self.assertIn("https://target.local", call_cmd)

        # 3. Control de seguridad: la MISMA URL como destino real bloquea estática y dinámicamente
        step_real_target = {
            "id": "step_real_target",
            "title": "Paso Destino Real Fuera de Alcance",
            "objective": "Verificar que la misma URL cuando es objetivo real se bloquea",
            "interaction_type": "active_low",
            "command_template": "curl https://client.example/callback",
        }
        pb_real = {
            "id": "pb_real_target_test",
            "title": "Playbook Real Target Test",
            "version": "1.0",
            "category": "api",
            "description": "Prueba de control de destino real fuera de alcance",
            "steps": [step_real_target],
        }

        val_real = validate_playbook_against_scope(pb_real, target_yaml)
        self.assertFalse(val_real["can_execute"])
        self.assertEqual(val_real["steps_evaluation"][0]["status"], "BLOCKED")
        self.assertIn("client.example", val_real["steps_evaluation"][0]["reason"])

        with unittest.mock.patch("subprocess.run") as mock_run:
            res_real = execute_playbook_step(
                step_real_target,
                context={"allow_active": True, "scope_data": scope_data},
                dry_run=False,
            )
            self.assertEqual(res_real["status"], "BLOCKED")
            self.assertEqual(res_real["exit_code"], 126)
            self.assertTrue(res_real["stop_condition_met"])
            mock_run.assert_not_called()


if __name__ == "__main__":
    unittest.main()


