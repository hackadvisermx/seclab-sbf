#!/usr/bin/env python3
"""Detector y neutralizador de contenido hostil e inyecciones de prompt para SecLab-SBF.

Protege el contexto del Copiloto contra Indirect Prompt Injection, evasión de delimitadores
y secuestro de instrucciones por datos no confiables provenientes de objetivos evaluados.

Sin dependencias externas obligatorias (Python 3 stdlib).
"""

import re
from typing import Any, Dict, List, Tuple


DELIMITER_PATTERNS = [
    (r"--- FIN DEL CONTEXTO ---", "[DELIMITADOR NEUTRALIZADO: FIN DEL CONTEXTO]", "Intento de cierre prematuro de delimitador de contexto"),
    (r"--- CONTEXTO EN VIVO DEL PROYECTO ---", "[DELIMITADOR NEUTRALIZADO: CONTEXTO EN VIVO]", "Intento de duplicación de encabezado de contexto"),
    (r"<\|(im_start|im_end|endoftext)\|>", "[TOKEN NEUTRALIZADO: \\1]", "Token especial de control de modelo de lenguaje"),
    (r"\[/?(SYSTEM|INST)\]", "[TOKEN NEUTRALIZADO: \\1]", "Delimitador estructural de instrucciones de sistema"),
    (r"<<\/?(SYS)>>", "[TOKEN NEUTRALIZADO: \\1]", "Delimitador de sistema estilo Llama"),
    (r"(?m)^(?:\s*)(system|assistant)\s*:\s*", "[ROL NEUTRALIZADO: \\1]: ", "Intento de simulación de rol de sistema o asistente al inicio de línea"),
]

INJECTION_PATTERNS = [
    (r"(?i)\b(?:ignore|disregard|forget)\s+(?:all\s+)?(?:previous|prior|above)\s+(?:instructions|prompts|rules|commands)\b",
     "Intento de anulación de instrucciones previas"),
    (r"(?i)\byou\s+are\s+now\s+(?:an?\s+)?(?:evil|new|unrestricted|jailbroken|dan)\b",
     "Intento de redefinición de identidad del modelo"),
    (r"(?i)\b(?:new|updated)\s+instructions?\s*:",
     "Intento de inyección de nuevas instrucciones"),
    (r"(?i)\bsystem\s+prompt\s+override\b",
     "Intento explícito de anulación de prompt de sistema"),
    (r"(?i)\b(?:bypass|disable)\s+(?:all\s+)?(?:safety|content\s+filters?|rules)\b",
     "Intento de evasión de filtros y reglas de seguridad"),
]


def detect_hostile_content(text: str) -> List[Dict[str, Any]]:
    """Detecta patrones de inyección y manipulación de delimitadores en texto no confiable."""
    if not text:
        return []

    findings: List[Dict[str, Any]] = []

    for pattern, _, description in DELIMITER_PATTERNS:
        for match in re.finditer(pattern, text):
            line_no = text[:match.start()].count("\n") + 1
            findings.append({
                "type": "delimiter_breakout",
                "matched_text": match.group(0),
                "description": description,
                "line": line_no,
            })

    for pattern, description in INJECTION_PATTERNS:
        for match in re.finditer(pattern, text):
            line_no = text[:match.start()].count("\n") + 1
            findings.append({
                "type": "prompt_injection",
                "matched_text": match.group(0),
                "description": description,
                "line": line_no,
            })

    return findings


def neutralize_hostile_content(text: str) -> Tuple[str, List[Dict[str, Any]]]:
    """Neutraliza delimitadores hostiles y envuelve inyecciones detectadas en etiquetas seguras."""
    if not text:
        return "", []

    findings = detect_hostile_content(text)
    sanitized = text

    # 1. Neutralizar delimitadores y tokens de control
    for pattern, replacement, _ in DELIMITER_PATTERNS:
        sanitized = re.sub(pattern, replacement, sanitized)

    # 2. Envolver patrones de inyección en contenedores seguros
    for pattern, _ in INJECTION_PATTERNS:
        sanitized = re.sub(
            pattern,
            lambda m: f"[DATO NO CONFIABLE - PATRÓN DE INYECCIÓN NEUTRALIZADO: {m.group(0)}]",
            sanitized
        )

    return sanitized, findings
