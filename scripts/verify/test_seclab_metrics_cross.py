#!/usr/bin/env python3
"""Pruebas unitarias para el resumen consolidado de métricas entre auditorías (Phase 231 / V3-07d)."""

import json
import os
import pathlib
import sys
import tempfile
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from seclab_metrics import compute_cross_engagement_summary


class TestSeclabCrossEngagementMetrics(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.ws_dir = pathlib.Path(self.tmp_dir.name)

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_nonexistent_workspace_raises(self):
        with self.assertRaises(FileNotFoundError):
            compute_cross_engagement_summary(self.ws_dir / "nonexistent")

    def test_empty_workspace_returns_zero_summary(self):
        summary = compute_cross_engagement_summary(self.ws_dir)
        self.assertEqual(summary["total_projects"], 0)
        self.assertEqual(summary["total_engagements"], 0)
        self.assertEqual(summary["total_retos"], 0)
        self.assertEqual(summary["avg_readiness_score"], 0.0)
        self.assertEqual(summary["total_findings"], 0)
        self.assertEqual(summary["projects"], [])

    def test_cross_engagement_aggregation_with_projects(self):
        # Create engagement
        eng_dir = self.ws_dir / "engagements" / "eng-alpha"
        eng_dir.mkdir(parents=True)
        (eng_dir / "target.yaml").write_text(
            """engagement:
  id: eng-alpha
authorization:
  allow_passive: true
  allow_active: true
scope:
  domains:
    - target.local
""",
            encoding="utf-8",
        )
        ev_dir1 = eng_dir / "evidence"
        ev_dir1.mkdir()
        (ev_dir1 / "finding-1.md").write_text(
            """---
finding_id: f-1
status: PROVEN
severity: high
source_job_id: job-101
source_stage: nikto
asset: target.local
---
High severity finding
""",
            encoding="utf-8",
        )
        (eng_dir / "REPORT.md").write_text("# Report\nValid", encoding="utf-8")

        # Create reto
        reto_dir = self.ws_dir / "retos" / "reto-beta"
        reto_dir.mkdir(parents=True)
        (reto_dir / "target.yaml").write_text(
            """engagement:
  id: reto-beta
authorization:
  allow_passive: true
scope:
  domains:
    - ctf.local
""",
            encoding="utf-8",
        )
        ev_dir2 = reto_dir / "evidence"
        ev_dir2.mkdir()
        (ev_dir2 / "finding-2.md").write_text(
            """---
finding_id: f-2
status: CANDIDATE
severity: medium
asset: ctf.local
---
Medium candidate finding
""",
            encoding="utf-8",
        )

        summary = compute_cross_engagement_summary(self.ws_dir)
        self.assertEqual(summary["total_projects"], 2)
        self.assertEqual(summary["total_engagements"], 1)
        self.assertEqual(summary["total_retos"], 1)
        self.assertEqual(summary["total_findings"], 2)
        self.assertEqual(summary["confirmed_findings_count"], 1)
        self.assertEqual(summary["candidate_findings_count"], 1)
        self.assertEqual(summary["findings_by_severity"]["high"], 1)
        self.assertEqual(summary["findings_by_severity"]["medium"], 1)
        self.assertEqual(summary["total_findings_with_provenance"], 1)
        self.assertEqual(summary["overall_provenance_coverage_pct"], 50.0)
        self.assertGreater(summary["avg_readiness_score"], 0.0)
        self.assertEqual(len(summary["projects"]), 2)


if __name__ == "__main__":
    unittest.main()
