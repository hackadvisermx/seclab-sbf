#!/usr/bin/env python3
"""Pruebas unitarias para el gestor y validador de Playbooks deterministas (seclab_playbook)."""

import pathlib
import sys
import tempfile
import unittest

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
        res = validate_playbook_against_scope(self.valid_playbook, target_yaml)
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
        res = validate_playbook_against_scope(self.valid_playbook, target_yaml, now=eval_time)
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
            "command_template": "curl https://example.local",
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


if __name__ == "__main__":
    unittest.main()


