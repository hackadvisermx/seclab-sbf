#!/usr/bin/env python3
"""Pruebas unitarias para la evaluación de checkpoints de supervisión (seclab_supervision)."""

import pathlib
import sys
import tempfile
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from seclab_supervision import evaluate_supervision_checkpoints


class TestSupervisionCheckpoints(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.eng_dir = pathlib.Path(self.tmp.name) / "test-eng"
        self.eng_dir.mkdir(parents=True, exist_ok=True)

    def test_empty_engagement_supervision_state(self):
        (self.eng_dir / "target.yaml").write_text("authorization:\n  allow_passive: false\n")
        res = evaluate_supervision_checkpoints(self.eng_dir)

        self.assertEqual(res["current_stage"], "scope")
        self.assertEqual(len(res["checkpoints"]), 4)

        cp_map = {cp["id"]: cp for cp in res["checkpoints"]}
        self.assertEqual(cp_map["cp_scope"]["status"], "PENDING")
        self.assertEqual(cp_map["cp_recon"]["status"], "NOT_STARTED")
        self.assertEqual(cp_map["cp_evidence"]["status"], "NOT_STARTED")
        self.assertEqual(cp_map["cp_report"]["status"], "NOT_STARTED")

    def test_authorized_and_recon_completed(self):
        (self.eng_dir / "target.yaml").write_text("authorization:\n  allow_passive: true\n")
        recon_dir = self.eng_dir / "recon"
        recon_dir.mkdir()
        (recon_dir / "live_hosts.txt").write_text("10.10.10.1\n10.10.10.2\n")

        res = evaluate_supervision_checkpoints(self.eng_dir)
        self.assertEqual(res["current_stage"], "probing")

        cp_map = {cp["id"]: cp for cp in res["checkpoints"]}
        self.assertEqual(cp_map["cp_scope"]["status"], "PASSED")
        self.assertEqual(cp_map["cp_recon"]["status"], "PASSED")
        self.assertEqual(res["live_hosts_count"], 2)

    def test_export_supervision_report(self):
        import json
        from seclab_supervision import export_supervision_report

        (self.eng_dir / "target.yaml").write_text("authorization:\n  allow_passive: true\n")
        recon_dir = self.eng_dir / "recon"
        recon_dir.mkdir()
        (recon_dir / "live_hosts.txt").write_text("10.10.10.1\n")

        # JSON
        json_str = export_supervision_report(self.eng_dir, format="json")
        data = json.loads(json_str)
        self.assertEqual(data["engagement"], "test-eng")
        self.assertEqual(len(data["checkpoints"]), 4)

        # Markdown
        md_str = export_supervision_report(self.eng_dir, format="markdown")
        self.assertIn("# Informe de Supervisión Pedagógica", md_str)
        self.assertIn("Checkpoints Pedagógicos Formativos", md_str)
        self.assertIn("Hosts vivos: 1", md_str)

        # Invalid format
        with self.assertRaises(ValueError):
            export_supervision_report(self.eng_dir, format="invalid")


if __name__ == "__main__":
    unittest.main()

