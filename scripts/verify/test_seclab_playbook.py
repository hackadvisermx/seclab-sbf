#!/usr/bin/env python3
"""Pruebas unitarias para el gestor y validador de Playbooks deterministas (seclab_playbook)."""

import pathlib
import sys
import tempfile
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from seclab_playbook import (
    validate_playbook_schema,
    validate_playbook_against_scope,
    load_playbook_file,
    PlaybookValidationError,
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
        target_yaml = self.tmp_path / "target.yaml"
        target_yaml.write_text(
            "authorization:\n  allow_passive: true\n  allow_active: true\n"
        )
        res = validate_playbook_against_scope(self.valid_playbook, target_yaml)
        self.assertTrue(res["can_execute"])
        self.assertEqual(res["blocked_steps_count"], 0)
        for s in res["steps_evaluation"]:
            self.assertEqual(s["status"], "AUTHORIZED")

    def test_scope_validation_blocks_active_when_disallowed(self):
        target_yaml = self.tmp_path / "target.yaml"
        target_yaml.write_text(
            "authorization:\n  allow_passive: true\n  allow_active: false\n"
        )
        res = validate_playbook_against_scope(self.valid_playbook, target_yaml)
        self.assertFalse(res["can_execute"])
        self.assertEqual(res["blocked_steps_count"], 1)

        step_map = {s["step_id"]: s for s in res["steps_evaluation"]}
        self.assertEqual(step_map["step_01_passive_lookup"]["status"], "AUTHORIZED")
        self.assertEqual(step_map["step_02_port_scan"]["status"], "BLOCKED")
        self.assertIn("target.yaml", step_map["step_02_port_scan"]["reason"])

    def test_load_builtin_playbook_templates(self):
        web_recon = REPO_ROOT / "workspace-seed" / "playbooks" / "web_recon.yaml"
        self.assertTrue(web_recon.is_file())
        pb = load_playbook_file(web_recon)
        is_valid, errors = validate_playbook_schema(pb)
        self.assertTrue(is_valid, f"Errores en web_recon.yaml: {errors}")

    def test_load_builtin_playbook_templates_without_pyyaml(self):
        import seclab_playbook
        orig_yaml = seclab_playbook.yaml
        try:
            seclab_playbook.yaml = None
            web_recon = REPO_ROOT / "workspace-seed" / "playbooks" / "web_recon.yaml"
            pb = load_playbook_file(web_recon)
            is_valid, errors = validate_playbook_schema(pb)
            self.assertTrue(is_valid, f"Errores sin PyYAML en web_recon.yaml: {errors}")
            self.assertEqual(pb["id"], "pb_web_recon")
            self.assertEqual(len(pb["steps"]), 2)
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
        target_yaml.write_text("authorization:\n  allow_passive: true\n  allow_active: true\n")
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
        target_yaml.write_text("authorization:\n  allow_passive: true\n  allow_active: false\n")
        res = run_playbook(
            self.valid_playbook,
            target_yaml_path=target_yaml,
            context={"parameters": {"target": "127.0.0.1"}},
            dry_run=False,
        )
        self.assertEqual(res["status"], "BLOCKED")
        self.assertFalse(res["can_execute"])


if __name__ == "__main__":
    unittest.main()

