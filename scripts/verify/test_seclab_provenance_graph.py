#!/usr/bin/env python3
"""Pruebas unitarias para el grafo estructurado de procedencia (scripts/seclab_provenance.py)."""

import json
import pathlib
import sqlite3
import tempfile
import unittest

from scripts.seclab_provenance import (
    build_provenance_graph,
    export_provenance_graph_markdown,
    export_provenance_graph_mermaid,
)


class TestSeclabProvenanceGraph(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.eng_dir = pathlib.Path(self.tmp_dir.name) / "test-eng"
        self.eng_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_build_provenance_graph_minimal(self):
        # Crear solo target.yaml
        target_yaml = self.eng_dir / "target.yaml"
        target_yaml.write_text("scope:\n  in_scope:\n    domains:\n      - target.local\n", encoding="utf-8")

        graph = build_provenance_graph(self.eng_dir)
        self.assertEqual(graph["engagement_id"], "test-eng")
        self.assertEqual(graph["summary"]["total_nodes"], 1)
        self.assertEqual(graph["summary"]["total_edges"], 0)
        self.assertEqual(graph["summary"]["findings_count"], 0)
        self.assertEqual(graph["summary"]["provenance_coverage_pct"], 100.0)

        nodes = graph["nodes"]
        self.assertEqual(len(nodes), 1)
        self.assertEqual(nodes[0]["id"], "scope:root")
        self.assertEqual(nodes[0]["type"], "scope")

    def test_build_provenance_graph_complete_chain(self):
        # 1. target.yaml
        (self.eng_dir / "target.yaml").write_text(
            "scope:\n  in_scope:\n    domains:\n      - target.local\n",
            encoding="utf-8",
        )

        # 2. recon_jobs.db
        db_path = self.eng_dir / "recon_jobs.db"
        conn = sqlite3.connect(db_path)
        conn.execute(
            "CREATE TABLE recon_jobs (id INTEGER PRIMARY KEY, tool TEXT, stage TEXT, status TEXT, command TEXT)"
        )
        conn.execute(
            "INSERT INTO recon_jobs (id, tool, stage, status, command) VALUES (1, 'nmap', 'port_scan', 'completed', 'nmap -sV target.local')"
        )
        conn.commit()
        conn.close()

        # 3. evidence/sqli.md
        ev_dir = self.eng_dir / "evidence"
        ev_dir.mkdir(parents=True, exist_ok=True)
        (ev_dir / "sqli.md").write_text(
            "---\n"
            "title: SQL Injection\n"
            "severity: high\n"
            "status: PROVEN\n"
            "asset: target.local\n"
            "source_job_id: \"1\"\n"
            "source_stage: port_scan\n"
            "---\n"
            "Detalle de la vulnerabilidad.\n",
            encoding="utf-8",
        )

        # 4. REPORT.md
        (self.eng_dir / "REPORT.md").write_text(
            "# Informe de Seguridad\n\nHallazgos identificados:\n- sqli (SQL Injection)\n",
            encoding="utf-8",
        )

        # 5. artifact-manifest.json
        (self.eng_dir / "artifact-manifest.json").write_text(
            json.dumps({"schema_version": 1, "artifacts": []}),
            encoding="utf-8",
        )

        graph = build_provenance_graph(self.eng_dir)
        summary = graph["summary"]
        self.assertEqual(summary["total_nodes"], 5)  # scope, job:1, finding:sqli, deliverable:report, deliverable:manifest
        self.assertEqual(summary["total_edges"], 4)  # scope->job, job->finding, finding->report, report->manifest
        self.assertEqual(summary["findings_count"], 1)
        self.assertEqual(summary["with_provenance_count"], 1)
        self.assertEqual(summary["unlinked_findings_count"], 0)
        self.assertEqual(summary["provenance_coverage_pct"], 100.0)
        self.assertEqual(summary["complete_chains_count"], 1)

        # Verificar aristas
        edge_types = [e["type"] for e in graph["edges"]]
        self.assertIn("targets", edge_types)
        self.assertIn("evidences", edge_types)
        self.assertIn("compiled_in", edge_types)
        self.assertIn("verified_by", edge_types)

    def test_build_provenance_graph_unlinked_manual_finding(self):
        (self.eng_dir / "target.yaml").write_text("scope:\n  in_scope:\n    domains: []\n", encoding="utf-8")
        ev_dir = self.eng_dir / "evidence"
        ev_dir.mkdir(parents=True, exist_ok=True)
        (ev_dir / "manual-note.md").write_text(
            "---\n"
            "title: Hallazgo Manual\n"
            "severity: low\n"
            "status: CANDIDATE\n"
            "---\n",
            encoding="utf-8",
        )

        graph = build_provenance_graph(self.eng_dir)
        summary = graph["summary"]
        self.assertEqual(summary["findings_count"], 1)
        self.assertEqual(summary["with_provenance_count"], 0)
        self.assertEqual(summary["unlinked_findings_count"], 1)
        self.assertEqual(summary["provenance_coverage_pct"], 0.0)
        self.assertEqual(summary["complete_chains_count"], 0)

        # Arista debe ser manual_unlinked
        self.assertEqual(len(graph["edges"]), 1)
        self.assertEqual(graph["edges"][0]["type"], "manual_unlinked")

    def test_export_formats(self):
        (self.eng_dir / "target.yaml").write_text("scope:\n  in_scope:\n    domains:\n      - target.local\n", encoding="utf-8")
        graph = build_provenance_graph(self.eng_dir)

        mermaid_str = export_provenance_graph_mermaid(graph)
        self.assertIn("flowchart LR", mermaid_str)
        self.assertIn("Alcance", mermaid_str)

        markdown_str = export_provenance_graph_markdown(graph)
        self.assertIn("# Grafo de Procedencia de Auditoría:", markdown_str)
        self.assertIn("```mermaid", markdown_str)


if __name__ == "__main__":
    unittest.main()
