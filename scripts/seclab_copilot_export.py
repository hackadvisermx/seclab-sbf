#!/usr/bin/env python3
"""Módulo de exportación estructurada de transcripciones del Copiloto Táctico (V3-05n).

Genera documentos en Markdown y JSON con metadatos de auditoría,
preguntas del operador, respuestas del asistente y desglose de citas/fuentes verificadas.
"""

import datetime
import json
from typing import Any, Dict, List, Optional


def format_copilot_chat_markdown(
    engagement_id: str,
    messages: List[Dict[str, Any]],
    engagement_type: str = "engagement",
) -> str:
    """Formatea la transcripción de chat del Copiloto como un documento Markdown estructurado."""
    now_iso = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    lines = [
        f"# Transcripción de Sesión del Copiloto Táctico: {engagement_id}",
        "",
        f"- **Auditoría / Proyecto**: `{engagement_id}` ({engagement_type})",
        f"- **Fecha de Exportación**: `{now_iso}`",
        f"- **Total de Mensajes**: {len(messages)}",
        "",
        "---",
        "",
    ]

    if not messages:
        lines.append("_No hay mensajes registrados en el historial de esta auditoría._\n")
        return "\n".join(lines)

    for idx, msg in enumerate(messages, 1):
        timestamp = msg.get("created_at") or "N/D"
        agent = msg.get("agent_id") or "copilot"
        provider = msg.get("provider") or "desconocido"
        model = msg.get("model") or "estándar"

        user_text = msg.get("user_message", "").strip()
        assistant_text = msg.get("assistant_message", "").strip()
        citations = msg.get("citations", [])

        lines.extend([
            f"## Turno {idx} — {timestamp}",
            "",
            f"**Operador:**",
            "> " + user_text.replace("\n", "\n> "),
            "",
            f"**Copiloto ({agent} · {provider}/{model}):**",
            assistant_text,
            "",
        ])

        if citations:
            lines.append("### Citas y Fuentes de Evidencia:")
            for cit in citations:
                cit_id = cit.get("id") or cit.get("target") or "referencia"
                status = "Válido" if cit.get("exists") else "No verificado"
                detail = cit.get("detail") or cit.get("excerpt") or ""
                line = f"- **[{cit_id}]** ({status})"
                if detail:
                    line += f": _{detail}_"
                lines.append(line)
            lines.append("")

        lines.append("---\n")

    return "\n".join(lines)


def export_copilot_chat(
    engagement_id: str,
    messages: List[Dict[str, Any]],
    format: str = "markdown",
    engagement_type: str = "engagement",
) -> str:
    """Exporta el historial de chat en el formato solicitado (markdown o json)."""
    fmt = (format or "markdown").lower()
    if fmt == "json":
        return json.dumps(
            {
                "engagement_id": engagement_id,
                "type": engagement_type,
                "exported_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "total_messages": len(messages),
                "messages": messages,
            },
            indent=2,
            ensure_ascii=False,
        )
    elif fmt in ("markdown", "md"):
        return format_copilot_chat_markdown(engagement_id, messages, engagement_type)
    else:
        raise ValueError(f"Formato no soportado: '{format}'. Debe ser 'markdown' o 'json'.")
