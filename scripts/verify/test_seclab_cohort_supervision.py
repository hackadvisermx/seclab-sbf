#!/usr/bin/env python3
"""Pruebas unitarias para la supervisión pedagógica agregada de cohorte docente (seclab_supervision)."""

import pathlib
import sys
import tempfile
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from seclab_supervision import compute_cohort_supervision_summary


class TestSeclabCohortSupervision(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.ws_path = pathlib.Path(self.tmp.name)
        (self.ws_path / "engagements").mkdir(parents=True)
        (self.ws_path / "retos").mkdir(parents=True)

    def test_empty_workspace_returns_zeroes(self):
        summary = compute_cohort_supervision_summary(self.ws_path)
        self.assertEqual(summary["total_cohort_projects"], 0)
        self.assertEqual(summary["cohort_completion_pct"], 0.0)
        self.assertEqual(summary["blocked_projects_count"], 0)
        self.assertEqual(summary["projects"], [])

    def test_cohort_aggregated_metrics(self):
        # Proyecto 1: Completo al 100%
        p1 = self.ws_path / "engagements" / "p1_complete"
        p1.mkdir()
        (p1 / "target.yaml").write_text("authorization:\n  allow_passive: true\n  allow_active: true\n")
        recon_dir = p1 / "recon"
        recon_dir.mkdir()
        (recon_dir / "live_hosts.txt").write_text("10.0.0.1\n")
        (recon_dir / "subdomains.txt").write_text("a.target.local\n")
        ev_dir = p1 / "evidence"
        ev_dir.mkdir()
        (ev_dir / "sqli.md").write_text("# SQL Injection\n")
        (p1 / "REPORT.md").write_text("# Reporte Técnico\n")
        deliv_dir = p1 / "deliverables"
        deliv_dir.mkdir()
        (deliv_dir / "report.zip").write_text("dummy zip content")

        # Proyecto 2: Bloqueado en alcance (sin target.yaml)
        p2 = self.ws_path / "retos" / "p2_blocked"
        p2.mkdir()

        summary = compute_cohort_supervision_summary(self.ws_path)
        self.assertEqual(summary["total_cohort_projects"], 2)
        self.assertEqual(summary["blocked_projects_count"], 1)
        self.assertEqual(summary["fully_completed_projects_count"], 1)
        self.assertEqual(summary["cohort_passed_checkpoints"], 4)
        self.assertEqual(summary["cohort_total_checkpoints"], 8)
        self.assertEqual(summary["cohort_completion_pct"], 50.0)

        # Desglose de checkpoints
        breakdown = summary["checkpoint_breakdown"]
        self.assertEqual(breakdown["cp_scope"]["passed"], 1)
        self.assertEqual(breakdown["cp_scope"]["blocked"], 1)

        # Proyectos
        self.assertEqual(len(summary["projects"]), 2)
        p_ids = [p["id"] for p in summary["projects"]]
        self.assertIn("p1_complete", p_ids)
        self.assertIn("p2_blocked", p_ids)


if __name__ == "__main__":
    unittest.main()
