#!/usr/bin/env python3
"""Pruebas unitarias para la ejecución individual de pasos de playbooks (Phase 229)."""

import pathlib
import sys
import unittest

SCRIPTS_DIR = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS_DIR))

from seclab_playbook import execute_playbook_step


class TestPlaybookStepRun(unittest.TestCase):
    def test_execute_passive_step_simulated(self):
        step = {
            "id": "step_subfinder",
            "title": "Descubrimiento de subdominios",
            "interaction_type": "passive",
            "command_template": "echo 'target: {target}'",
        }
        res = execute_playbook_step(
            step=step,
            context={"parameters": {"target": "example.com"}, "allow_passive": True},
            dry_run=True,
        )

        self.assertEqual(res["step_id"], "step_subfinder")
        self.assertEqual(res["status"], "SIMULATED")
        self.assertIn("target: example.com", res["command"])
        self.assertTrue(res["is_simulated"])

    def test_execute_active_step_blocked_by_scope(self):
        step = {
            "id": "step_portscan",
            "title": "Escaneo de puertos activo",
            "interaction_type": "active_low",
            "command_template": "nmap -p 80 {target}",
        }
        # Sin permiso activo
        res = execute_playbook_step(
            step=step,
            context={"parameters": {"target": "target.local"}, "allow_active": False},
            dry_run=False,
        )

        self.assertEqual(res["status"], "BLOCKED")
        self.assertEqual(res["exit_code"], 126)
        self.assertTrue(res["stop_condition_met"])


if __name__ == "__main__":
    unittest.main()
