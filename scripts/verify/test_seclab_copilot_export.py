#!/usr/bin/env python3
"""Pruebas unitarias para el exportador de chat del Copiloto (scripts/seclab_copilot_export.py)."""

import json
import unittest

from scripts.seclab_copilot_export import export_copilot_chat, format_copilot_chat_markdown


class TestSeclabCopilotExport(unittest.TestCase):
    def setUp(self):
        self.engagement_id = "test-export-eng"
        self.messages = [
            {
                "id": 1,
                "agent_id": "copilot",
                "user_message": "Analiza los puertos abiertos en el objetivo.",
                "assistant_message": "Se identificó el puerto 443 abierto con servicio HTTPS según [evidence/recon_nmap.md].",
                "citations": [
                    {"id": "evidence/recon_nmap.md", "exists": True, "excerpt": "443/tcp open https"}
                ],
                "provider": "anthropic",
                "model": "claude-3-7-sonnet",
                "created_at": "2026-10-12 18:00:00",
            },
            {
                "id": 2,
                "agent_id": "copilot",
                "user_message": "¿Existe alguna vulnerabilidad crítica?",
                "assistant_message": "No se encontraron vulnerabilidades críticas en [evidence/findings_missing.md].",
                "citations": [
                    {"id": "evidence/findings_missing.md", "exists": False, "excerpt": "No hallado"}
                ],
                "provider": "ollama",
                "model": "llama3",
                "created_at": "2026-10-12 18:05:00",
            },
        ]

    def test_format_copilot_chat_markdown_empty(self):
        res = format_copilot_chat_markdown("empty-eng", [])
        self.assertIn("# Transcripción de Sesión del Copiloto Táctico: empty-eng", res)
        self.assertIn("Total de Mensajes**: 0", res)
        self.assertIn("_No hay mensajes registrados en el historial de esta auditoría._", res)

    def test_format_copilot_chat_markdown_with_messages(self):
        res = format_copilot_chat_markdown(self.engagement_id, self.messages)
        self.assertIn(f"# Transcripción de Sesión del Copiloto Táctico: {self.engagement_id}", res)
        self.assertIn("Total de Mensajes**: 2", res)
        self.assertIn("## Turno 1 — 2026-10-12 18:00:00", res)
        self.assertIn("> Analiza los puertos abiertos en el objetivo.", res)
        self.assertIn("Copiloto (copilot · anthropic/claude-3-7-sonnet):", res)
        self.assertIn("Citas y Fuentes de Evidencia:", res)
        self.assertIn("**[evidence/recon_nmap.md]** (Válido): _443/tcp open https_", res)
        self.assertIn("## Turno 2 — 2026-10-12 18:05:00", res)
        self.assertIn("**[evidence/findings_missing.md]** (No verificado): _No hallado_", res)

    def test_export_copilot_chat_json(self):
        json_str = export_copilot_chat(self.engagement_id, self.messages, format="json")
        data = json.loads(json_str)
        self.assertEqual(data["engagement_id"], self.engagement_id)
        self.assertEqual(data["type"], "engagement")
        self.assertEqual(data["total_messages"], 2)
        self.assertEqual(len(data["messages"]), 2)
        self.assertEqual(data["messages"][0]["citations"][0]["exists"], True)

    def test_export_copilot_chat_markdown_aliases(self):
        res_md = export_copilot_chat(self.engagement_id, self.messages, format="md")
        self.assertIn("# Transcripción de Sesión del Copiloto Táctico:", res_md)
        res_markdown = export_copilot_chat(self.engagement_id, self.messages, format="markdown")
        self.assertEqual(res_md, res_markdown)

    def test_export_copilot_chat_invalid_format(self):
        with self.assertRaises(ValueError) as ctx:
            export_copilot_chat(self.engagement_id, self.messages, format="pdf")
        self.assertIn("Formato no soportado", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
