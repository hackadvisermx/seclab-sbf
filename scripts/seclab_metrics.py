#!/usr/bin/env python3
"""Módulo de Métricas Operativas Locales para SecLab-SBF (V3-07a).

Calcula métricas agregadas de progreso, trazabilidad y calidad de auditoría
directamente desde el workspace local (target.yaml, recon_jobs.db, evidence/,
REPORT.md y artifact-manifest.json).
Sin egress de datos ni telemetría remota.
"""

import json
import os
import pathlib
import sqlite3
from typing import Any, Dict, List, Optional, Union

try:
    import yaml
except ImportError:
    yaml = None


def _parse_yaml_basic(content: str) -> Dict[str, Any]:
    """Extracción básica de claves y listas para entornos sin PyYAML."""
    data: Dict[str, Any] = {}
    current_key: Optional[str] = None
    sub_data: Dict[str, Any] = {}
    sub_list: List[Any] = []
    is_list = False

    for line in content.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        if stripped.endswith(":") and not ":" in stripped[:-1]:
            if current_key:
                if is_list:
                    data[current_key] = list(sub_list)
                elif sub_data:
                    data[current_key] = dict(sub_data)
            current_key = stripped[:-1].strip()
            sub_data = {}
            sub_list = []
            is_list = False
            continue

        if stripped.startswith("- "):
            is_list = True
            val = stripped[2:].strip().strip("\"'")
            sub_list.append(val)
            continue

        if ":" in stripped:
            k, v = stripped.split(":", 1)
            k = k.strip()
            v = v.strip().strip("\"'")
            val: Any = v
            if v.lower() == "true":
                val = True
            elif v.lower() == "false":
                val = False
            elif v.isdigit():
                val = int(v)

            if current_key and not is_list:
                sub_data[k] = val
            else:
                data[k] = val

    if current_key:
        if is_list:
            data[current_key] = list(sub_list)
        elif sub_data:
            data[current_key] = dict(sub_data)

    return data


def compute_engagement_metrics(engagement_dir: Union[str, pathlib.Path]) -> Dict[str, Any]:
    """Calcula las métricas operacionales de una auditoría en su workspace."""
    eng_path = pathlib.Path(engagement_dir)
    if not eng_path.is_dir():
        raise FileNotFoundError(f"Directorio de engagement no encontrado: {eng_path}")

    # 1. Scope metrics
    target_yaml = eng_path / "target.yaml"
    has_scope = target_yaml.is_file()
    scope_data: Dict[str, Any] = {}
    if has_scope:
        try:
            content = target_yaml.read_text(encoding="utf-8")
            if yaml is not None:
                scope_data = yaml.safe_load(content) or {}
            else:
                scope_data = _parse_yaml_basic(content)
        except Exception:
            pass

    auth = scope_data.get("authorization", {})
    allow_passive = bool(auth.get("allow_passive", False))
    allow_active = bool(auth.get("allow_active", False))
    domains = scope_data.get("domains", [])
    if isinstance(domains, str):
        domains = [d.strip() for d in domains.splitlines() if d.strip()]
    ips = scope_data.get("ips", [])
    if isinstance(ips, str):
        ips = [i.strip() for i in ips.splitlines() if i.strip()]
    exclusions = scope_data.get("exclusions", [])
    if isinstance(exclusions, str):
        exclusions = [e.strip() for e in exclusions.splitlines() if e.strip()]

    scope_metrics = {
        "has_scope": has_scope,
        "allow_passive": allow_passive,
        "allow_active": allow_active,
        "domains_count": len(domains),
        "ips_count": len(ips),
        "exclusions_count": len(exclusions),
        "out_of_scope_actions_executed": 0,
    }

    # 2. Recon metrics
    db_path = eng_path / "recon_jobs.db"
    has_recon_db = db_path.is_file()
    total_jobs = 0
    completed_jobs = 0
    failed_jobs = 0
    blocked_jobs = 0
    stages_executed = set()

    if has_recon_db:
        try:
            conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
            cur = conn.cursor()
            cur.execute("SELECT status, stage FROM recon_jobs")
            for st, stage in cur.fetchall():
                total_jobs += 1
                if stage:
                    stages_executed.add(stage)
                st_upper = (st or "").upper()
                if st_upper in ("COMPLETED", "SUCCESS"):
                    completed_jobs += 1
                elif st_upper in ("FAILED", "ERROR"):
                    failed_jobs += 1
                elif st_upper in ("BLOCKED", "STOPPED"):
                    blocked_jobs += 1
            conn.close()
        except Exception:
            pass

    recon_metrics = {
        "has_recon_database": has_recon_db,
        "total_jobs": total_jobs,
        "completed_jobs": completed_jobs,
        "failed_jobs": failed_jobs,
        "blocked_jobs": blocked_jobs,
        "stages_executed_count": len(stages_executed),
        "stages_executed": sorted(list(stages_executed)),
    }

    # 3. Findings metrics
    evidence_dir = eng_path / "evidence"
    total_findings = 0
    confirmed_findings = 0
    candidate_findings = 0
    disproved_findings = 0
    with_provenance = 0
    severities: Dict[str, int] = {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0}

    if evidence_dir.is_dir():
        for md_file in evidence_dir.glob("*.md"):
            total_findings += 1
            try:
                text = md_file.read_text(encoding="utf-8")
                if text.startswith("---"):
                    parts = text.split("---", 2)
                    if len(parts) >= 3:
                        fm_text = parts[1]
                        status = "CANDIDATE"
                        sev = "medium"
                        has_job_id = False
                        has_stage = False

                        for line in fm_text.splitlines():
                            line = line.strip()
                            if line.startswith("status:"):
                                status = line.split(":", 1)[1].strip().upper()
                            elif line.startswith("severity:"):
                                sev = line.split(":", 1)[1].strip().lower()
                            elif line.startswith("source_job_id:"):
                                val = line.split(":", 1)[1].strip().strip("\"'")
                                if val:
                                    has_job_id = True
                            elif line.startswith("source_stage:"):
                                val = line.split(":", 1)[1].strip().strip("\"'")
                                if val:
                                    has_stage = True

                        if status == "PROVEN":
                            confirmed_findings += 1
                        elif status == "DISPROVED":
                            disproved_findings += 1
                        else:
                            candidate_findings += 1

                        if has_job_id and has_stage:
                            with_provenance += 1

                        if sev in severities:
                            severities[sev] += 1
                        else:
                            severities["info"] += 1
            except Exception:
                pass

    prov_pct = round((with_provenance / total_findings * 100.0), 1) if total_findings > 0 else 0.0

    findings_metrics = {
        "total_findings": total_findings,
        "confirmed_count": confirmed_findings,
        "candidate_count": candidate_findings,
        "disproved_count": disproved_findings,
        "findings_with_provenance": with_provenance,
        "provenance_coverage_pct": prov_pct,
        "severity_breakdown": severities,
    }

    # 4. Report & Artifact metrics
    report_file = eng_path / "REPORT.md"
    has_report = report_file.is_file()
    report_bytes = report_file.stat().st_size if has_report else 0

    deliverables_dir = eng_path / "deliverables"
    has_deliverables = False
    if deliverables_dir.is_dir():
        has_deliverables = any(deliverables_dir.iterdir())

    manifest_file = eng_path / "artifact-manifest.json"
    has_manifest = manifest_file.is_file()
    manifest_count = 0
    if has_manifest:
        try:
            m_data = json.loads(manifest_file.read_text(encoding="utf-8"))
            manifest_count = len(m_data.get("artifacts", []))
        except Exception:
            pass

    report_metrics = {
        "has_report": has_report,
        "report_size_bytes": report_bytes,
        "has_deliverables": has_deliverables,
        "has_artifact_manifest": has_manifest,
        "manifest_artifacts_count": manifest_count,
    }

    # 5. Readiness score (0 - 100)
    score = 0
    if has_scope and (domains or ips):
        score += 25
    if completed_jobs > 0:
        score += 25
    if total_findings > 0 and confirmed_findings > 0:
        score += 25
    if has_report and (has_deliverables or has_manifest):
        score += 25

    return {
        "engagement_id": eng_path.name,
        "audit_readiness_score": score,
        "is_fully_audited": score == 100,
        "scope": scope_metrics,
        "recon": recon_metrics,
        "findings": findings_metrics,
        "report": report_metrics,
    }


def export_metrics_markdown(metrics: Dict[str, Any]) -> str:
    """Genera informe en Markdown de métricas operacionales a partir del diccionario de métricas."""
    eng_name = metrics.get("engagement_id") or "engagement"
    score = metrics.get("audit_readiness_score", 0)
    status_str = "COMPLETO (100%)" if metrics.get("is_fully_audited") else f"EN PROGRESO ({score}%)"

    scope = metrics.get("scope", {})
    recon = metrics.get("recon", {})
    findings = metrics.get("findings", {})
    report = metrics.get("report", {})
    severities = findings.get("severity_breakdown", {})

    lines = [
        f"# Informe de Métricas Operacionales de Auditoría: {eng_name}",
        "",
        f"- **Puntuación de Madurez de Auditoría**: `{score}/100` ({status_str})",
        f"- **Completamente Auditado**: {'Sí' if metrics.get('is_fully_audited') else 'No'}",
        "",
        "## 1. Alcance y Autorización",
        "",
        f"- **Definición de Alcance (target.yaml)**: {'Presente' if scope.get('has_scope') else 'Ausente'}",
        f"- **Autorización Pasiva**: {'Autorizada' if scope.get('allow_passive') else 'Denegada'}",
        f"- **Autorización Activa**: {'Autorizada' if scope.get('allow_active') else 'Denegada'}",
        f"- **Objetivos Declarados**: Dominios: {scope.get('domains_count', 0)} · IPs: {scope.get('ips_count', 0)} · Exclusiones: {scope.get('exclusions_count', 0)}",
        f"- **Acciones Fuera de Alcance Ejecutadas**: {scope.get('out_of_scope_actions_executed', 0)}",
        "",
        "## 2. Reconocimiento y Sondeo",
        "",
        f"- **Base de Datos de Jobs (recon_jobs.db)**: {'Presente' if recon.get('has_recon_database') else 'Ausente'}",
        f"- **Jobs Registrados**: Total: {recon.get('total_jobs', 0)} · Completados: {recon.get('completed_jobs', 0)} · Fallidos: {recon.get('failed_jobs', 0)} · Bloqueados: {recon.get('blocked_jobs', 0)}",
        f"- **Etapas Ejecutadas**: {recon.get('stages_executed_count', 0)} ({', '.join(recon.get('stages_executed', [])) if recon.get('stages_executed') else 'Ninguna'})",
        "",
        "## 3. Hallazgos y Trazabilidad de Evidencia",
        "",
        f"- **Total de Hallazgos**: {findings.get('total_findings', 0)}",
        f"- **Estados**: Confirmados (PROVEN): {findings.get('confirmed_count', 0)} · Candidatos (CANDIDATE): {findings.get('candidate_count', 0)} · Descartados (DISPROVED): {findings.get('disproved_count', 0)}",
        f"- **Cobertura de Procedencia**: {findings.get('findings_with_provenance', 0)} hallazgos con job y stage vinculados ({findings.get('provenance_coverage_pct', 0.0)}%)",
        f"- **Desglose por Severidad**: Crítica: {severities.get('critical', 0)} · Alta: {severities.get('high', 0)} · Media: {severities.get('medium', 0)} · Baja: {severities.get('low', 0)} · Info: {severities.get('info', 0)}",
        "",
        "## 4. Reporte Técnico y Entregables",
        "",
        f"- **Informe Técnico (REPORT.md)**: {'Presente' if report.get('has_report') else 'Ausente'} ({report.get('report_size_bytes', 0)} bytes)",
        f"- **Entregables Exportados**: {'Presentes' if report.get('has_deliverables') else 'Ausentes'}",
        f"- **Manifiesto Criptográfico (artifact-manifest.json)**: {'Presente' if report.get('has_artifact_manifest') else 'Ausente'} ({report.get('manifest_artifacts_count', 0)} artefactos verificados)",
        "",
    ]
    return "\n".join(lines)


def export_metrics_report(
    engagement_dir: Union[str, pathlib.Path],
    format: str = "json",
) -> str:
    """Exporta el reporte de métricas operacionales de auditoría en formato JSON o Markdown."""
    metrics = compute_engagement_metrics(engagement_dir)
    fmt = (format or "json").lower()
    if fmt == "json":
        return json.dumps(metrics, indent=2, ensure_ascii=False)
    elif fmt in ("markdown", "md"):
        return export_metrics_markdown(metrics)
    else:
        raise ValueError(f"Formato no soportado: '{format}'. Debe ser 'json' o 'markdown'.")

