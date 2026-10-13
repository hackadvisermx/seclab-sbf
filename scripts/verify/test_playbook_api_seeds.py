#!/usr/bin/env python3
"""Pruebas unitarias para las plantillas de playbooks de APIs modernas (GraphQL y OAuth/JWT)."""

import pathlib
import sys
import tempfile
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import seclab_playbook
from seclab_playbook import (
    load_playbook_file,
    validate_playbook_schema,
    validate_playbook_against_scope,
)


class TestPlaybookApiSeeds(unittest.TestCase):
    def setUp(self):
        self.playbooks_dir = REPO_ROOT / "workspace-seed" / "playbooks"
        self.graphql_path = self.playbooks_dir / "api_graphql_audit.yaml"
        self.oauth_path = self.playbooks_dir / "oauth_jwt_audit.yaml"

    def test_files_exist(self):
        self.assertTrue(self.graphql_path.is_file(), "Debe existir api_graphql_audit.yaml")
        self.assertTrue(self.oauth_path.is_file(), "Debe existir oauth_jwt_audit.yaml")

    def test_graphql_playbook_schema(self):
        pb = load_playbook_file(self.graphql_path)
        is_valid, errors = validate_playbook_schema(pb)
        self.assertTrue(is_valid, f"Errores en schema GraphQL: {errors}")
        self.assertEqual(pb["id"], "pb_api_graphql_audit")
        self.assertEqual(pb["category"], "api_audit")
        self.assertEqual(len(pb["steps"]), 3)
        for step in pb["steps"]:
            self.assertEqual(step["interaction_type"], "active_low")
            self.assertIn("allow_active", step["required_permissions"])

    def test_oauth_jwt_playbook_schema(self):
        pb = load_playbook_file(self.oauth_path)
        is_valid, errors = validate_playbook_schema(pb)
        self.assertTrue(is_valid, f"Errores en schema OAuth/JWT: {errors}")
        self.assertEqual(pb["id"], "pb_oauth_jwt_audit")
        self.assertEqual(pb["category"], "api_audit")
        self.assertEqual(len(pb["steps"]), 3)
        for step in pb["steps"]:
            self.assertEqual(step["interaction_type"], "active_low")
            self.assertIn("allow_active", step["required_permissions"])

    def test_fallback_parser_without_pyyaml(self):
        orig_yaml = seclab_playbook.yaml
        try:
            seclab_playbook.yaml = None
            for path in [self.graphql_path, self.oauth_path]:
                pb = load_playbook_file(path)
                is_valid, errors = validate_playbook_schema(pb)
                self.assertTrue(is_valid, f"Errores sin PyYAML para {path.name}: {errors}")
                self.assertEqual(len(pb.get("steps", [])), 3)
        finally:
            seclab_playbook.yaml = orig_yaml

    def test_scope_validation_with_authorized_target(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            target_yaml = pathlib.Path(tmp_dir) / "target.yaml"
            target_yaml.write_text("authorization:\n  allow_passive: true\n  allow_active: true\n")
            for path in [self.graphql_path, self.oauth_path]:
                pb = load_playbook_file(path)
                res = validate_playbook_against_scope(pb, target_yaml)
                self.assertTrue(res["can_execute"], f"No se pudo ejecutar {path.name} con active permitido")
                self.assertEqual(res["blocked_steps_count"], 0)

    def test_scope_validation_blocks_when_active_disallowed(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            target_yaml = pathlib.Path(tmp_dir) / "target.yaml"
            target_yaml.write_text("authorization:\n  allow_passive: true\n  allow_active: false\n")
            for path in [self.graphql_path, self.oauth_path]:
                pb = load_playbook_file(path)
                res = validate_playbook_against_scope(pb, target_yaml)
                self.assertFalse(res["can_execute"], f"No debió permitirse {path.name} con active deshabilitado")
                self.assertEqual(res["blocked_steps_count"], 3)


if __name__ == "__main__":
    unittest.main()
