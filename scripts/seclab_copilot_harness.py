#!/usr/bin/env python3
"""seclab_copilot_harness.py - Harness de integracion para modelos locales (Ollama/vLLM) con fallback determinista y cero perdida de estado."""

from __future__ import annotations

import datetime
import json
import os
import pathlib
import re
import socket
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional, Tuple


def normalize_provider_url(raw_url: Optional[str], default_port: int = 11434) -> str:
    """Normaliza URLs de proveedores locales asegurando esquema y host limpios."""
    if not raw_url or not str(raw_url).strip():
        return f"http://127.0.0.1:{default_port}"
    url = str(raw_url).strip().rstrip("/")
    if not (url.startswith("http://") or url.startswith("https://")):
        url = f"http://{url}"
    return url


def probe_local_provider(
    base_url: str,
    timeout_seconds: float = 2.0,
) -> Dict[str, Any]:
    """Sondea la salud y modelos disponibles de un endpoint local (Ollama o vLLM/OpenAI-compatible)

    Aplica un socket timeout estricto de timeout_seconds (por defecto 2.0s) para garantizar
    que nunca bloquee la interfaz ni el backend si el daemon esta detenido.
    """
    normalized_url = normalize_provider_url(base_url)
    start_time = time.time()
    models: List[str] = []
    provider_type = "unknown"
    error_msg: Optional[str] = None
    is_online = False

    # Candidatos de sondeo:
    # 1. Ollama: /api/tags
    # 2. vLLM / OpenAI: /v1/models o /models
    # 3. Base health: /api/version o /
    candidate_endpoints = [
        ("/api/tags", "ollama"),
        ("/v1/models", "vllm_openai"),
        ("/models", "vllm_openai"),
        ("/api/version", "ollama"),
        ("/", "generic"),
    ]

    for path, p_type in candidate_endpoints:
        target_url = f"{normalized_url}{path}"
        try:
            req = urllib.request.Request(
                target_url,
                headers={"User-Agent": "SecLab-Copilot-Harness/1.0", "Accept": "application/json"},
                method="GET",
            )
            with urllib.request.urlopen(req, timeout=timeout_seconds) as resp:
                status_code = resp.getcode()
                raw_data = resp.read()
                if status_code == 200:
                    is_online = True
                    provider_type = p_type
                    try:
                        data = json.loads(raw_data.decode("utf-8"))
                        if isinstance(data, dict):
                            # Ollama /api/tags format
                            if "models" in data and isinstance(data["models"], list):
                                for m in data["models"]:
                                    if isinstance(m, dict) and "name" in m:
                                        models.append(m["name"])
                                    elif isinstance(m, str):
                                        models.append(m)
                            # OpenAI /v1/models format
                            elif "data" in data and isinstance(data["data"], list):
                                for m in data["data"]:
                                    if isinstance(m, dict) and "id" in m:
                                        models.append(m["id"])
                                    elif isinstance(m, str):
                                        models.append(m)
                    except Exception:
                        pass
                    break
        except (urllib.error.URLError, socket.timeout, TimeoutError, OSError, ConnectionRefusedError) as e:
            error_msg = str(e)
            continue
        except Exception as e:
            error_msg = str(e)
            continue

    latency_ms = int((time.time() - start_time) * 1000)

    return {
        "status": "ONLINE" if is_online else "OFFLINE",
        "provider_type": provider_type,
        "endpoint": normalized_url,
        "latency_ms": latency_ms,
        "models": sorted(list(set(models))),
        "error": None if is_online else (error_msg or "Endpoint no respondio en el tiempo limite"),
        "checked_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }


def _extract_scope_summary(target_dir: pathlib.Path) -> Tuple[List[str], List[str]]:
    """Extrae resumen de objetivos in_scope y out_of_scope desde target.yaml o scope.txt."""
    in_scope: List[str] = []
    out_of_scope: List[str] = []

    target_yaml = target_dir / "target.yaml"
    if target_yaml.is_file():
        try:
            content = target_yaml.read_text(encoding="utf-8")
            # Parseo basico seguro de lineas YAML
            current_section = None
            for line in content.splitlines():
                stripped = line.strip()
                if stripped.startswith("in_scope:"):
                    current_section = "in"
                elif stripped.startswith("out_of_scope:"):
                    current_section = "out"
                elif stripped.startswith("- ") and current_section:
                    item = stripped[2:].strip().strip("\"'")
                    if current_section == "in":
                        in_scope.append(item)
                    elif current_section == "out":
                        out_of_scope.append(item)
        except Exception:
            pass

    if not in_scope and not out_of_scope:
        scope_txt = target_dir / "scope.txt"
        if scope_txt.is_file():
            try:
                for line in scope_txt.read_text(encoding="utf-8").splitlines():
                    s = line.strip()
                    if s and not s.startswith("#"):
                        in_scope.append(s)
            except Exception:
                pass

    return in_scope, out_of_scope


def _extract_findings_summary(target_dir: pathlib.Path) -> List[str]:
    """Lista los hallazgos en markdown registrados en evidence/."""
    evidence_dir = target_dir / "evidence"
    if not evidence_dir.is_dir():
        return []
    findings = []
    for p in evidence_dir.glob("*.md"):
        if p.name.startswith("."):
            continue
        findings.append(p.stem)
    return sorted(findings)


def generate_heuristic_fallback(
    engagement_dir: pathlib.Path | str,
    agent_id: str,
    user_message: str,
) -> str:
    """Genera orientacion tecnica determinista sin dependencia de LLMs externos cuando el proveedor falla o esta offline."""
    edir = pathlib.Path(engagement_dir)
    in_scope, out_of_scope = _extract_scope_summary(edir)
    findings = _extract_findings_summary(edir)

    # Identificar activos primarios
    targets_str = ", ".join(f"`{t}`" for t in in_scope[:5]) if in_scope else "`Sin objetivos formalizados en target.yaml`"
    exclusions_str = ", ".join(f"`{t}`" for t in out_of_scope[:3]) if out_of_scope else "Ninguna exclusion explicita"

    # Consejos especificos segun la especialidad del agente
    specialty_guidance = {
        "recon-agent": (
            "1. **Enumeracion de Superficie:** Inicia con descubrimiento pasivo de DNS y certificados TLS antes de escaneo de puertos.\n"
            "2. **Descubrimiento de Servicios:** Ejecuta sondeo selectivo de puertos respetando limites de concurrencia.\n"
            "3. **Trazabilidad:** Correlaciona cada puerto y tecnologia detectada en `recon/` para preservar procedencia técnica."
        ),
        "triage-agent": (
            "1. **Verificacion de Reproducibilidad:** Todo hallazgo debe contar con pasos numerados reproducibles y evidencia en crudo.\n"
            "2. **Puntuacion CVSS:** Contrasta vectores de métricas de impacto (Confidencialidad, Integridad, Disponibilidad) objetivamente.\n"
            "3. **Verificacion de Falsos Positivos:** Valida que las respuestas HTTP anomalas no sean respuestas genéricas del WAF."
        ),
        "auth-agent": (
            "1. **Matriz de Control de Acceso:** Audita endpoints privilegiados alternando tokens de usuario no autenticado, usuario bajo y admin.\n"
            "2. **Vulnerabilidades BOLA/IDOR:** Reemplaza identificadores de recursos directos en rutas REST y GraphQL.\n"
            "3. **Ciclo de Vida de Sesion:** Verifica expiracion tras logout, regeneracion de tokens post-login y flags de seguridad."
        ),
        "logic-agent": (
            "1. **Flujos Secuenciales:** Prueba saltos de etapas en procesos transaccionales o asistentes multipaso.\n"
            "2. **Condiciones de Carrera (TOCTOU):** Analiza canjes concurrentes de cupones, saldos o codigos de un solo uso.\n"
            "3. **Limites de Parametros:** Introduce cantidades negativas, cero o numeros enteros extragrandes en campos numéricos."
        ),
        "injection-agent": (
            "1. **Pruebas Contextuales:** Analiza el contexto de renderizado (HTML, atributo, script, base de datos) antes de usar payloads.\n"
            "2. **Inyecciones Ciegas & Fuera de Banda:** Emplea diferenciales de tiempo o callbacks controlados dentro del alcance.\n"
            "3. **Validacion de SSRF:** Audita URLs suministradas por el usuario asegurando bloqueo estricto de rangos RFC1918 y loopback."
        ),
        "report-agent": (
            "1. **Sintesis Ejecutiva:** Resume el riesgo para los objetivos de negocio sin jerga técnica innecesaria.\n"
            "2. **Detalle Tecnico y Mitigacion:** Provee recomendaciones accionables a corto y mediano plazo para el equipo de desarrollo.\n"
            "3. **Compilacion Final:** Ejecuta `pt-report --verify-artifacts` para certificar la integridad del reporte y sus anexos."
        ),
    }

    guidance = specialty_guidance.get(
        agent_id,
        (
            "1. **Metodologia Estructurada:** Ejecuta reconocimiento, analisis de vulnerabilidades y explotacion controlada paso a paso.\n"
            "2. **Respeto de Alcance:** Verifica siempre que el objetivo pertenezca al alcance autorizado antes de lanzar comandos.\n"
            "3. **Registro Continuo:** Documenta artefactos y hallazgos en `evidence/` inmediatamente tras su observacion."
        ),
    )

    findings_block = ""
    if findings:
        sample_slugs = ", ".join(f"`{f}`" for f in findings[:4])
        findings_block = f"\n**Hallazgos Actuales en Evidencia ({len(findings)}):** {sample_slugs} (ver [ref:evidence:{findings[0]}])\n"
    else:
        findings_block = "\n**Hallazgos Registrados:** Ningun hallazgo documentado todavia en `evidence/`.\n"

    response = (
        "ℹ️ [Modo Degradación Determinista Local: Proveedor sin conexión — Respuesta heurística generada sin pérdida de estado]\n\n"
        f"### Orientación Táctica Local (Agente: `{agent_id}`)\n\n"
        f"**Consulta del Operador:** \"{user_message.strip()}\"\n\n"
        f"**Alcance Autorizado:** {targets_str} (ver [ref:scope:target.yaml])\n"
        f"**Exclusiones:** {exclusions_str}\n"
        f"{findings_block}\n"
        "**Recomendaciones Metodológicas Directas:**\n"
        f"{guidance}\n\n"
        "> ⚠️ **Nota de Incertidumbre y Verificación:** Esta respuesta es determinista y generada localmente por SecLab-SBF sin asistencia de modelos generativos externos. Toda sugerencia técnica debe considerarse una hipótesis preliminar (\"posible\", \"candidato a verificar\") que requiere comprobación manual en el laboratorio antes de actuar.\n"
    )

    return response
