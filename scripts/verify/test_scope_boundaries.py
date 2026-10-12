#!/usr/bin/env python3
"""Pruebas unitarias para la especificación canónica de límites de Scope Guard (V3-01g)."""

import pathlib
import sys
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from seclab_scope import get_scope_guard_boundaries


class TestScopeBoundaries(unittest.TestCase):
    def test_scope_guard_boundaries_structure(self):
        boundaries = get_scope_guard_boundaries()
        self.assertIn("enforced_mechanisms", boundaries)
        self.assertIn("unenforced_mechanisms", boundaries)
        self.assertIn("notice", boundaries)

        # Verificar mecanismos interceptados
        enforced = boundaries["enforced_mechanisms"]
        self.assertTrue(len(enforced) >= 3)
        channels_enforced = [m["channel"] for m in enforced]
        self.assertIn("dashboard_pipeline", channels_enforced)
        self.assertIn("deterministic_playbooks", channels_enforced)
        self.assertIn("api_endpoints", channels_enforced)
        for m in enforced:
            self.assertTrue(m["intercepted"])
            self.assertIn(m["enforcement"], ("STRICT_BLOCK", "STRICT_CHECK", "ADVISORY_WARNING"))

        # Verificar mecanismos NO interceptados (terminal libre)
        unenforced = boundaries["unenforced_mechanisms"]
        self.assertTrue(len(unenforced) >= 1)
        channels_unenforced = [m["channel"] for m in unenforced]
        self.assertIn("interactive_terminal_ttyd", channels_unenforced)
        for m in unenforced:
            self.assertFalse(m["intercepted"])
            self.assertEqual(m["enforcement"], "NONE")
            self.assertTrue(m.get("operator_responsibility"))

    def test_scope_boundaries_notice_text(self):
        boundaries = get_scope_guard_boundaries()
        notice = boundaries["notice"]
        self.assertIn("AVISO DE LÍMITES OPERACIONALES", notice)
        self.assertIn("Scope Guard", notice)
        self.assertIn("terminal", notice.lower())
        self.assertIn("responsable", notice.lower())


if __name__ == "__main__":
    unittest.main()
