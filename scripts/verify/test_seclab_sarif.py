#!/usr/bin/env python3
"""Pruebas unitarias para la exportación de hallazgos a SARIF v2.1.0 (Phase 230)."""

import json
import pathlib
import sys
import tempfile
import unittest

SCRIPTS_DIR = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS_DIR))

from seclab_sarif import export_findings_to_sarif, severity_to_sarif_level


class TestSeclabSarifExport(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.workspace = pathlib.Path(self.temp_dir.name)
        self.evidence_dir = self.workspace / "evidence"
        self.evidence_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_severity_level_mapping(self):
        self.assertEqual(severity_to_sarif_level("CRITICAL"), "error")
        self.assertEqual(severity_to_sarif_level("HIGH"), "error")
        self.assertEqual(severity_to_sarif_level("alta"), "error")
        self.assertEqual(severity_to_sarif_level("MEDIUM"), "warning")
        self.assertEqual(severity_to_sarif_level("media"), "warning")
        self.assertEqual(severity_to_sarif_level("LOW"), "note")
        self.assertEqual(severity_to_sarif_level("INFO"), "note")

    def test_export_findings_to_sarif_valid_document(self):
        # Crear ficha de hallazgo ficticia en evidence/
        finding_file = self.evidence_dir / "sqli-auth.md"
        finding_content = """---
id: 550e8400-e29b-41d4-a716-446655440000
title: Inyección SQL en endpoint de autenticación
severity: HIGH
cvss_score: 8.8
cvss_vector: CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H
status: CONFIRMED
target: https://target.local/api/login
source_job_id: 1234567890abcdef1234567890abcdef
source_stage: probe
---

## Descripción
Vulnerabilidad de inyección SQL clásica en el parámetro 'username'.

## Pasos para reproducir
Enviar carga util: `' OR 1=1 --` en petición POST.

## Remediación
Utilizar consultas parametrizadas o sentencias preparadas.
"""
        finding_file.write_text(finding_content, encoding="utf-8")

        sarif_doc = export_findings_to_sarif(self.workspace)

        # Validaciones de la estructura OASIS SARIF v2.1.0
        self.assertEqual(sarif_doc["version"], "2.1.0")
        self.assertIn("sarif-schema-2.1.0.json", sarif_doc["$schema"])
        self.assertEqual(len(sarif_doc["runs"]), 1)

        run = sarif_doc["runs"][0]
        self.assertEqual(run["tool"]["driver"]["name"], "SecLab-SBF")
        self.assertEqual(len(run["tool"]["driver"]["rules"]), 1)
        self.assertEqual(len(run["results"]), 1)

        rule = run["tool"]["driver"]["rules"][0]
        self.assertEqual(rule["id"], "sqli-auth")
        self.assertEqual(rule["defaultConfiguration"]["level"], "error")
        self.assertEqual(rule["properties"]["security_severity"], "8.8")

        result = run["results"][0]
        self.assertEqual(result["ruleId"], "sqli-auth")
        self.assertEqual(result["level"], "error")
        self.assertIn("Inyección SQL", result["message"]["text"])
        self.assertIn("Remediación sugerida:", result["message"]["text"])
        self.assertEqual(result["locations"][0]["physicalLocation"]["artifactLocation"]["uri"], "evidence/sqli-auth.md")
        self.assertEqual(result["properties"]["source_job_id"], "1234567890abcdef1234567890abcdef")


if __name__ == "__main__":
    unittest.main()
