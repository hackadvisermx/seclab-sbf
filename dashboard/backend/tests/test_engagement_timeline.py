import datetime
import json
import pathlib
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from app.core import database
from app.models.schemas import EngagementTimelineResponse, FindingCreate
from app.services.workspace_sync import WorkspaceSyncService
from app.services.timeline_service import TimelineService


class TestEngagementTimeline(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.ws_dir = pathlib.Path(self.tmp.name) / "workspace"
        self.recon_db_path = pathlib.Path(self.tmp.name) / "recon-jobs.db"
        self.vault_db_path = pathlib.Path(self.tmp.name) / "vault.db"

        self.db_patch = patch.object(database, "VAULT_DB_PATH", self.vault_db_path)
        self.db_patch.start()
        self.addCleanup(self.db_patch.stop)
        database.init_db()

        self.ws_service = WorkspaceSyncService(self.ws_dir, recon_db_path=self.recon_db_path)
        self.timeline_service = TimelineService()

    def _init_recon_db(self, eng_id: str = "test-proj", run_id: str = "run-101"):
        from app.core.recon_jobs import ReconJobStore
        store = ReconJobStore(self.recon_db_path)
        with sqlite3.connect(self.recon_db_path) as conn:
            conn.execute(
                "INSERT INTO recon_job_history VALUES (?, ?, ?, ?, ?, 0, ?, ?, NULL, ?, 'dashboard')",
                ("engagement", eng_id, run_id, "completed", "probe",
                 "2026-10-11T10:00:00Z", "2026-10-11T10:05:00Z", "rev1")
            )
            conn.execute(
                "INSERT INTO recon_job_outcome_reviews VALUES (?, ?, ?, ?, ?)",
                ("engagement", eng_id, run_id, "mock_rev", "2026-10-11T10:10:00Z")
            )

    def test_timeline_empty_engagement(self):
        self.ws_service.create_engagement("empty-proj", domain="empty.example")
        with patch("app.services.timeline_service.workspace_service", self.ws_service):
            with patch("app.services.recon_service.recon_service.store.history", return_value={"jobs": []}):
                res = self.timeline_service.get_timeline("empty-proj", "engagement")
                self.assertIsInstance(res, EngagementTimelineResponse)
                self.assertEqual(res.engagement_id, "empty-proj")
                # Al menos debe contener el evento de target.yaml generado por create_engagement
                cats = [e.category for e in res.events]
                self.assertIn("scope", cats)

    def test_timeline_aggregates_events_chronologically(self):
        eng_id = "chron-proj"
        valid_job_id = "a" * 32
        self.ws_service.create_engagement(eng_id, domain="target.example")
        self._init_recon_db(eng_id, valid_job_id)

        # Crear notas y reporte
        target_dir = self.ws_service._resolve_dir(eng_id)
        notes_file = target_dir / "notes.md"
        notes_file.write_text("# Notas de prueba\n- Hallado puerto 8080\n")

        report_file = target_dir / "REPORT.md"
        report_file.write_text("# Informe Ejecutivo\nResumen de hallazgos.\n")

        deliverables_dir = target_dir / "deliverables"
        deliverables_dir.mkdir(parents=True, exist_ok=True)
        manifest_file = deliverables_dir / "finding-manifest.json"
        manifest_file.write_text('{"version": 1, "findings": []}')

        # Crear finding con procedencia
        with patch("app.services.workspace_sync.workspace_service", self.ws_service):
            finding = self.ws_service.save_finding(
                eng_id,
                FindingCreate(
                    slug="sqli-test",
                    title="Inyección SQL",
                    severity="CRITICAL",
                    description="Parámetro vulnerable id",
                    asset="http://target.example/vuln",
                    source_job_id=valid_job_id,
                    source_stage="probe",
                ),
            )

        from app.core.recon_jobs import ReconJobStore
        with patch("app.services.timeline_service.workspace_service", self.ws_service), \
             patch("app.services.recon_service.recon_service.store", ReconJobStore(self.recon_db_path)):
            res = self.timeline_service.get_timeline(eng_id, "engagement")
            self.assertGreaterEqual(res.total_events, 4)
            categories = {e.category for e in res.events}
            self.assertIn("scope", categories)
            self.assertIn("recon", categories)
            self.assertIn("finding", categories)
            self.assertIn("notes", categories)
            self.assertIn("report", categories)

            # Verificar que los eventos están ordenados cronológicamente descendente
            timestamps = [e.timestamp for e in res.events]
            sorted_timestamps = sorted(timestamps, reverse=True)
            self.assertEqual(timestamps, sorted_timestamps)

            # Verificar evento de finding
            finding_events = [e for e in res.events if e.category == "finding"]
            self.assertTrue(len(finding_events) > 0)
            fe = finding_events[0]
            self.assertEqual(fe.details.get("severity"), "CRITICAL")
            self.assertEqual(fe.details.get("source_job_id"), valid_job_id)
            self.assertEqual(fe.status, "error")

    def test_timeline_api_endpoint(self):
        from app.main import app
        from app.api.endpoints import auth
        from fastapi.testclient import TestClient

        self.ws_service.create_engagement("api-proj", domain="api.example")
        auth._attempts.clear()

        with patch.object(auth, "TESTER_PASSWORD", "test-pass"), \
             patch("app.services.timeline_service.workspace_service", self.ws_service), \
             patch("app.services.recon_service.recon_service.store.history", return_value={"jobs": []}):
            client = TestClient(app)
            login_res = client.post("/api/v1/auth/login", json={"password": "test-pass"})
            self.assertEqual(login_res.status_code, 200)

            # GET timeline
            res = client.get("/api/v1/engagements/api-proj/timeline?type=engagement")
            self.assertEqual(res.status_code, 200)
            data = res.json()
            self.assertEqual(data["engagement_id"], "api-proj")
            self.assertEqual(data["type"], "engagement")
            self.assertIsInstance(data["events"], list)

            # Export JSON
            res_json = client.get("/api/v1/engagements/api-proj/timeline/export?type=engagement&format=json")
            self.assertEqual(res_json.status_code, 200)
            self.assertEqual(res_json.headers.get("content-type"), "application/json")
            parsed_json = json.loads(res_json.content)
            self.assertEqual(parsed_json["engagement_id"], "api-proj")

            # Export Markdown
            res_md = client.get("/api/v1/engagements/api-proj/timeline/export?type=engagement&format=markdown")
            self.assertEqual(res_md.status_code, 200)
            self.assertIn("text/markdown", res_md.headers.get("content-type"))
            self.assertIn("# Línea de Tiempo de Auditoría: api-proj", res_md.text)
            self.assertIn("target.yaml", res_md.text)
            client.close()

    def test_timeline_export_service(self):
        self.ws_service.create_engagement("export-proj", domain="export.example")
        with patch("app.services.timeline_service.workspace_service", self.ws_service):
            with patch("app.services.recon_service.recon_service.store.history", return_value={"jobs": []}):
                md_out = self.timeline_service.export_timeline("export-proj", "engagement", format="markdown")
                self.assertIn("# Línea de Tiempo de Auditoría: export-proj", md_out)
                self.assertIn("Alcance Autorizado", md_out)

                json_out = self.timeline_service.export_timeline("export-proj", "engagement", format="json")
                parsed = json.loads(json_out)
                self.assertEqual(parsed["engagement_id"], "export-proj")
                self.assertIsInstance(parsed["events"], list)

