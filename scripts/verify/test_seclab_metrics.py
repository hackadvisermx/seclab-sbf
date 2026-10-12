#!/usr/bin/env python3
"""Pruebas unitarias para el calculador de métricas locales de auditoría (seclab_metrics)."""

import json
import pathlib
import sqlite3
import sys
import tempfile
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from seclab_metrics import compute_engagement_metrics


class TestSeclabMetrics(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.tmp_path = pathlib.Path(self.tmp.name)

    def test_nonexistent_directory_raises(self):
        with self.assertRaises(FileNotFoundError):
            compute_engagement_metrics(self.tmp_path / "nonexistent")

    def test_empty_engagement_metrics(self):
        eng_dir = self.tmp_path / "empty_eng"
        eng_dir.mkdir()

        metrics = compute_engagement_metrics(eng_dir)
        self.assertEqual(metrics["engagement_id"], "empty_eng")
        self.assertEqual(metrics["audit_readiness_score"], 0)
        self.assertFalse(metrics["is_fully_audited"])
        self.assertFalse(metrics["scope"]["has_scope"])
        self.assertEqual(metrics["scope"]["out_of_scope_actions_executed"], 0)
        self.assertEqual(metrics["recon"]["total_jobs"], 0)
        self.assertEqual(metrics["findings"]["total_findings"], 0)
        self.assertFalse(metrics["report"]["has_report"])

    def test_complete_engagement_metrics(self):
        eng_dir = self.tmp_path / "complete_eng"
        eng_dir.mkdir()

        # 1. target.yaml
        target_yaml = eng_dir / "target.yaml"
        target_yaml.write_text(
            "authorization:\n  allow_passive: true\n  allow_active: true\n"
            "domains:\n  - example.com\n  - sub.example.com\n"
            "ips:\n  - 192.168.1.1\n"
            "exclusions:\n  - private.example.com\n"
        )

        # 2. recon_jobs.db
        db_path = eng_dir / "recon_jobs.db"
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("CREATE TABLE recon_jobs (status TEXT, stage TEXT)")
        cur.execute("INSERT INTO recon_jobs VALUES ('COMPLETED', 'probe')")
        cur.execute("INSERT INTO recon_jobs VALUES ('COMPLETED', 'portscan')")
        conn.commit()
        conn.close()

        # 3. evidence/
        evidence_dir = eng_dir / "evidence"
        evidence_dir.mkdir()
        f1 = evidence_dir / "vuln1.md"
        f1.write_text(
            "---\n"
            "title: Inyección SQL\n"
            "severity: high\n"
            "status: PROVEN\n"
            "source_job_id: job-123\n"
            "source_stage: probe\n"
            "---\n"
            "Detalle de la prueba\n"
        )
        f2 = evidence_dir / "vuln2.md"
        f2.write_text(
            "---\n"
            "title: Divulgación de Información\n"
            "severity: low\n"
            "status: CANDIDATE\n"
            "---\n"
            "Candidato pendiente\n"
        )

        # 4. REPORT.md & artifact-manifest.json
        report_md = eng_dir / "REPORT.md"
        report_md.write_text("# Reporte Técnico de Auditoría\n\nHallazgos encontrados.")

        manifest_file = eng_dir / "artifact-manifest.json"
        manifest_file.write_text(json.dumps({
            "schema_version": 1,
            "artifacts": [
                {"path": "evidence/vuln1.md", "sha256": "abc", "size_bytes": 100, "category": "evidence"}
            ]
        }))

        metrics = compute_engagement_metrics(eng_dir)

        # Scope assertions
        self.assertTrue(metrics["scope"]["has_scope"])
        self.assertTrue(metrics["scope"]["allow_passive"])
        self.assertTrue(metrics["scope"]["allow_active"])
        self.assertEqual(metrics["scope"]["domains_count"], 2)
        self.assertEqual(metrics["scope"]["ips_count"], 1)
        self.assertEqual(metrics["scope"]["exclusions_count"], 1)
        self.assertEqual(metrics["scope"]["out_of_scope_actions_executed"], 0)

        # Recon assertions
        self.assertTrue(metrics["recon"]["has_recon_database"])
        self.assertEqual(metrics["recon"]["total_jobs"], 2)
        self.assertEqual(metrics["recon"]["completed_jobs"], 2)
        self.assertEqual(metrics["recon"]["stages_executed"], ["portscan", "probe"])

        # Findings assertions
        self.assertEqual(metrics["findings"]["total_findings"], 2)
        self.assertEqual(metrics["findings"]["confirmed_count"], 1)
        self.assertEqual(metrics["findings"]["candidate_count"], 1)
        self.assertEqual(metrics["findings"]["findings_with_provenance"], 1)
        self.assertEqual(metrics["findings"]["provenance_coverage_pct"], 50.0)
        self.assertEqual(metrics["findings"]["severity_breakdown"]["high"], 1)
        self.assertEqual(metrics["findings"]["severity_breakdown"]["low"], 1)

        # Report assertions
        self.assertTrue(metrics["report"]["has_report"])
        self.assertGreater(metrics["report"]["report_size_bytes"], 0)
        self.assertTrue(metrics["report"]["has_artifact_manifest"])
        self.assertEqual(metrics["report"]["manifest_artifacts_count"], 1)

        # Readiness
        self.assertEqual(metrics["audit_readiness_score"], 100)
        self.assertTrue(metrics["is_fully_audited"])

    def test_complete_engagement_metrics_without_pyyaml(self):
        import seclab_metrics
        orig_yaml = seclab_metrics.yaml
        try:
            seclab_metrics.yaml = None
            eng_dir = self.tmp_path / "no_pyyaml_eng"
            eng_dir.mkdir()
            target_yaml = eng_dir / "target.yaml"
            target_yaml.write_text(
                "authorization:\n  allow_passive: true\n  allow_active: true\n"
                "domains:\n  - example.com\n  - sub.example.com\n"
                "ips:\n  - 192.168.1.1\n"
                "exclusions:\n  - private.example.com\n"
            )
            metrics = compute_engagement_metrics(eng_dir)
            self.assertTrue(metrics["scope"]["has_scope"])
            self.assertEqual(metrics["scope"]["domains_count"], 2)
            self.assertEqual(metrics["scope"]["ips_count"], 1)
            self.assertEqual(metrics["scope"]["exclusions_count"], 1)
            self.assertTrue(metrics["scope"]["allow_passive"])
            self.assertTrue(metrics["scope"]["allow_active"])
        finally:
            seclab_metrics.yaml = orig_yaml


if __name__ == "__main__":
    unittest.main()

