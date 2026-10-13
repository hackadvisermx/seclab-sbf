#!/usr/bin/env python3
"""Pruebas unitarias para el historial longitudinal de métricas de madurez de auditoría (seclab_metrics)."""

import json
import pathlib
import sys
import tempfile
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from seclab_metrics import (
    record_metrics_snapshot,
    get_metrics_history,
)


class TestSeclabMetricsHistory(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.tmp_path = pathlib.Path(self.tmp.name)
        (self.tmp_path / "evidence").mkdir(parents=True)

    def test_record_and_get_metrics_snapshot(self):
        mock_metrics_1 = {
            "audit_readiness_score": 40.0,
            "is_fully_audited": False,
            "pillars": {
                "scope": {"status": "COMPLETE", "score": 100},
                "recon": {"status": "PENDING", "score": 0},
                "findings": {"status": "PENDING", "score": 0},
                "deliverables": {"status": "PENDING", "score": 0},
            },
            "findings": {
                "total_findings": 0,
                "provenance_coverage_pct": 0.0,
            },
            "recon": {
                "completed_jobs": 0,
            },
        }

        snap1 = record_metrics_snapshot(self.tmp_path, metrics_data=mock_metrics_1, author="auditor_1")
        self.assertEqual(snap1["audit_readiness_score"], 40.0)
        self.assertFalse(snap1["is_fully_audited"])
        self.assertEqual(snap1["author"], "auditor_1")
        self.assertTrue(bool(snap1["snapshot_id"]))

        # Historial con 1 registro
        hist = get_metrics_history(self.tmp_path)
        self.assertEqual(len(hist), 1)
        self.assertEqual(hist[0]["snapshot_id"], snap1["snapshot_id"])
        self.assertEqual(hist[0]["delta_score"], 0.0)

        # Grabar segundo snapshot con avance de madurez
        mock_metrics_2 = {
            "audit_readiness_score": 75.0,
            "is_fully_audited": False,
            "pillars": {
                "scope": {"status": "COMPLETE", "score": 100},
                "recon": {"status": "COMPLETE", "score": 100},
                "findings": {"status": "COMPLETE", "score": 100},
                "deliverables": {"status": "PENDING", "score": 0},
            },
            "findings": {
                "total_findings": 2,
                "provenance_coverage_pct": 100.0,
            },
            "recon": {
                "completed_jobs": 2,
            },
        }

        snap2 = record_metrics_snapshot(self.tmp_path, metrics_data=mock_metrics_2, author="auditor_2")
        self.assertEqual(snap2["audit_readiness_score"], 75.0)

        # Historial con 2 registros en orden inverso (más reciente primero)
        hist2 = get_metrics_history(self.tmp_path)
        self.assertEqual(len(hist2), 2)
        self.assertEqual(hist2[0]["snapshot_id"], snap2["snapshot_id"])
        self.assertEqual(hist2[0]["delta_score"], 35.0)  # 75.0 - 40.0
        self.assertEqual(hist2[1]["snapshot_id"], snap1["snapshot_id"])
        self.assertEqual(hist2[1]["delta_score"], 0.0)

    def test_empty_history_returns_empty_list(self):
        hist = get_metrics_history(self.tmp_path)
        self.assertEqual(hist, [])

    def test_nonexistent_directory_raises(self):
        with self.assertRaises(FileNotFoundError):
            record_metrics_snapshot(self.tmp_path / "no_existe")


if __name__ == "__main__":
    unittest.main()
