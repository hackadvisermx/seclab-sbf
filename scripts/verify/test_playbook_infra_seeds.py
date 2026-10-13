#!/usr/bin/env python3
"""Pruebas unitarias para las plantillas de playbooks de infraestructura interna (SMB y Pivot/Segmento)."""

import pathlib
import sys
import tempfile
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))
sys.path.insert(0, str(REPO_ROOT / "scripts" / "verify"))

import seclab_playbook
from seclab_playbook import (
    load_playbook_file,
    validate_playbook_schema,
    validate_playbook_against_scope,
)


class TestPlaybookInfraSeeds(unittest.TestCase):
    def setUp(self):
        self.playbooks_dir = REPO_ROOT / "workspace-seed" / "playbooks"
        self.smb_path = self.playbooks_dir / "smb_shares_recon.yaml"
        self.pivot_path = self.playbooks_dir / "internal_pivot_audit.yaml"

    def test_files_exist(self):
        self.assertTrue(self.smb_path.is_file(), "Debe existir smb_shares_recon.yaml")
        self.assertTrue(self.pivot_path.is_file(), "Debe existir internal_pivot_audit.yaml")

    def test_smb_playbook_schema(self):
        pb = load_playbook_file(self.smb_path)
        is_valid, errors = validate_playbook_schema(pb)
        self.assertTrue(is_valid, f"Errores en schema SMB: {errors}")
        self.assertEqual(pb["id"], "pb_smb_shares_recon")
        self.assertEqual(pb["category"], "infra_audit")
        self.assertEqual(len(pb["steps"]), 3)
        for step in pb["steps"]:
            self.assertEqual(step["interaction_type"], "active_low")
            self.assertIn("allow_active", step["required_permissions"])

    def test_pivot_playbook_schema(self):
        pb = load_playbook_file(self.pivot_path)
        is_valid, errors = validate_playbook_schema(pb)
        self.assertTrue(is_valid, f"Errores en schema pivot interno: {errors}")
        self.assertEqual(pb["id"], "pb_internal_pivot_audit")
        self.assertEqual(pb["category"], "infra_audit")
        self.assertEqual(len(pb["steps"]), 3)
        # Paso 1 es pasivo
        self.assertEqual(pb["steps"][0]["interaction_type"], "passive")
        self.assertIn("allow_passive", pb["steps"][0]["required_permissions"])
        # Pasos 2 y 3 son active_low
        self.assertEqual(pb["steps"][1]["interaction_type"], "active_low")
        self.assertEqual(pb["steps"][2]["interaction_type"], "active_low")

    def test_fallback_parser_without_pyyaml(self):
        orig_yaml = seclab_playbook.yaml
        try:
            seclab_playbook.yaml = None
            for path in [self.smb_path, self.pivot_path]:
                pb = load_playbook_file(path)
                is_valid, errors = validate_playbook_schema(pb)
                self.assertTrue(is_valid, f"Errores sin PyYAML para {path.name}: {errors}")
                self.assertEqual(len(pb.get("steps", [])), 3)
        finally:
            seclab_playbook.yaml = orig_yaml

    def test_scope_validation_with_authorized_target(self):
        from authorization_fixture import AUTHORIZATION_YAML
        with tempfile.TemporaryDirectory() as tmp_dir:
            target_yaml = pathlib.Path(tmp_dir) / "target.yaml"
            target_yaml.write_text(AUTHORIZATION_YAML)
            for path in [self.smb_path, self.pivot_path]:
                pb = load_playbook_file(path)
                res = validate_playbook_against_scope(pb, target_yaml)
                self.assertTrue(res["can_execute"], f"No se pudo ejecutar {path.name} con active permitido")
                self.assertEqual(res["blocked_steps_count"], 0)

    def test_scope_validation_blocks_active_steps_when_active_disallowed(self):
        from authorization_fixture import AUTHORIZATION_YAML
        with tempfile.TemporaryDirectory() as tmp_dir:
            target_yaml = pathlib.Path(tmp_dir) / "target.yaml"
            target_yaml.write_text(AUTHORIZATION_YAML.replace("allow_active: true", "allow_active: false"))

            # SMB tiene 3 pasos active_low -> bloquea los 3
            pb_smb = load_playbook_file(self.smb_path)
            res_smb = validate_playbook_against_scope(pb_smb, target_yaml)
            self.assertFalse(res_smb["can_execute"])
            self.assertEqual(res_smb["blocked_steps_count"], 3)

            # Pivot interno tiene 1 pasivo y 2 active_low -> el pasivo se autoriza, los 2 activos se bloquean
            pb_pivot = load_playbook_file(self.pivot_path)
            res_pivot = validate_playbook_against_scope(pb_pivot, target_yaml)
            self.assertFalse(res_pivot["can_execute"])
            self.assertEqual(res_pivot["blocked_steps_count"], 2)
            self.assertEqual(res_pivot["steps_evaluation"][0]["status"], "AUTHORIZED")


if __name__ == "__main__":
    unittest.main()
