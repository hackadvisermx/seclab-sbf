#!/usr/bin/env python3
"""Pruebas unitarias para la ingestión de ejecuciones CLI manuales en recon_jobs.db (Phase 228)."""

import pathlib
import sqlite3
import sys
import tempfile
import unittest

SCRIPTS_DIR = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS_DIR))

from seclab_record_job import record_external_recon_job


class TestRecordExternalJob(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = pathlib.Path(self.temp_dir.name) / "recon-jobs.db"

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_record_external_recon_job_inserts_row(self):
        res = record_external_recon_job(
            db_path=self.db_path,
            engagement_type="engagement",
            engagement_id="audit-alpha",
            tool="nmap",
            stage="probe",
            command="nmap -sS -p 22,80,443 192.168.1.10",
            status="completed",
            notes="3 puertos abiertos identificados",
        )

        self.assertEqual(res["engagement_id"], "audit-alpha")
        self.assertEqual(res["origin"], "cli-external")
        self.assertEqual(res["status"], "completed")
        self.assertEqual(res["tool"], "nmap")

        # Verificar en base SQLite
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            rows = cursor.execute("SELECT * FROM recon_job_history WHERE engagement_id = 'audit-alpha'").fetchall()
            self.assertEqual(len(rows), 1)
            row = rows[0]
            # Columnas: engagement_type, engagement_id, run_id, status, stage, dry_run, started_at, finished_at, error, scope_revision, origin
            self.assertEqual(row[0], "engagement")
            self.assertEqual(row[1], "audit-alpha")
            self.assertEqual(row[3], "completed")
            self.assertEqual(row[4], "probe")
            self.assertEqual(row[5], 0)  # dry_run = 0
            self.assertIn("[nmap] nmap -sS -p 22,80,443", row[8])
            self.assertEqual(row[10], "cli-external")
        finally:
            conn.close()

    def test_record_external_recon_job_failed_status(self):
        res = record_external_recon_job(
            db_path=self.db_path,
            engagement_type="reto",
            engagement_id="ctf-box",
            tool="ffuf",
            stage="urls",
            command="ffuf -u http://target/FUZZ -w wordlist.txt",
            status="failed",
            notes="Conexión rechazada por firewall",
        )

        self.assertEqual(res["status"], "failed")
        self.assertEqual(res["origin"], "cli-external")


if __name__ == "__main__":
    unittest.main()
