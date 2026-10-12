#!/usr/bin/env python3
"""Pruebas unitarias para respuestas y auto-justificaciones en supervisión pedagógica (Phase 232 / V3-06d)."""

import json
import os
import pathlib
import sys
import tempfile
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from seclab_supervision import (
    evaluate_supervision_checkpoints,
    load_supervision_responses,
    save_checkpoint_response,
    export_supervision_report,
)


class TestSupervisionResponses(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.eng_dir = pathlib.Path(self.tmp.name) / "test-eng"
        self.eng_dir.mkdir(parents=True, exist_ok=True)
        (self.eng_dir / "target.yaml").write_text("authorization:\n  allow_passive: true\n", encoding="utf-8")

    def test_save_and_load_checkpoint_response(self):
        # Initial empty
        resps = load_supervision_responses(self.eng_dir)
        self.assertEqual(resps, {})

        # Save response for cp_recon
        entry = save_checkpoint_response(
            self.eng_dir,
            checkpoint_id="cp_recon",
            justification="Ejecuté subfinder y httpx sin encontrar nuevos hosts; procedo con sondeo de puertos bajos.",
            learner_action="proceder_con_nmap",
        )
        self.assertEqual(entry["checkpoint_id"], "cp_recon")
        self.assertIn("subfinder", entry["justification"])
        self.assertEqual(entry["learner_action"], "proceder_con_nmap")
        self.assertIn("updated_at", entry)

        # Loaded responses should contain it
        loaded = load_supervision_responses(self.eng_dir)
        self.assertIn("cp_recon", loaded)
        self.assertEqual(loaded["cp_recon"]["justification"], entry["justification"])

    def test_evaluate_checkpoints_attaches_learner_response(self):
        save_checkpoint_response(
            self.eng_dir,
            checkpoint_id="cp_scope",
            justification="Alcance verificado contra contrato del cliente Acme.",
        )

        state = evaluate_supervision_checkpoints(self.eng_dir)
        cp_map = {cp["id"]: cp for cp in state["checkpoints"]}

        self.assertTrue(cp_map["cp_scope"]["is_justified"])
        self.assertIsNotNone(cp_map["cp_scope"]["learner_response"])
        self.assertEqual(cp_map["cp_scope"]["learner_response"]["justification"], "Alcance verificado contra contrato del cliente Acme.")

        # cp_recon has no response
        self.assertFalse(cp_map["cp_recon"]["is_justified"])
        self.assertIsNone(cp_map["cp_recon"]["learner_response"])

    def test_export_supervision_markdown_includes_justifications(self):
        save_checkpoint_response(
            self.eng_dir,
            checkpoint_id="cp_scope",
            justification="Alcance revisado con el instructor.",
            learner_action="autorizar_pasivo",
        )

        md = export_supervision_report(self.eng_dir, format="markdown")
        self.assertIn("Justificaciones y Decisiones del Estudiante", md)
        self.assertIn("Alcance revisado con el instructor.", md)
        self.assertIn("autorizar_pasivo", md)


if __name__ == "__main__":
    unittest.main()
