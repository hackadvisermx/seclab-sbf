#!/usr/bin/env python3
"""Módulo de evaluación de estado de supervisión y checkpoints de auditoría para SecLab-SBF (V3-06a).

Evalúa el progreso de un engagement a través de 4 checkpoints pedagógicos formales:
1. Alcance y Autorización (scope & rules)
2. Mapeo de Superficie y Hosts Vivos (recon & probing)
3. Documentación y Evidencia de Hallazgos (triage & proof of concept)
4. Informe Técnico y Cierre (reporting & packaging)

Sin dependencias externas obligatorias (Python 3 stdlib).
"""

import datetime
import json
import os
import pathlib
from typing import Any, Dict, List, Optional, Tuple, Union

try:
    import yaml
except ImportError:
    yaml = None


def load_supervision_responses(engagement_dir: Union[str, pathlib.Path]) -> Dict[str, Any]:
    """Carga las justificaciones pedagógicas del estudiante almacenadas en evidence/.supervision_responses.json."""
    eng_path = pathlib.Path(engagement_dir)
    resp_file = eng_path / "evidence" / ".supervision_responses.json"
    if not resp_file.is_file():
        return {}
    try:
        data = json.loads(resp_file.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_checkpoint_response(
    engagement_dir: Union[str, pathlib.Path],
    checkpoint_id: str,
    justification: str,
    learner_action: Optional[str] = None,
) -> Dict[str, Any]:
    """Guarda la justificación y decisión del estudiante para un checkpoint formativo."""
    eng_path = pathlib.Path(engagement_dir)
    if not eng_path.is_dir():
        raise FileNotFoundError(f"Directorio de engagement no encontrado: {eng_path}")

    ev_dir = eng_path / "evidence"
    ev_dir.mkdir(parents=True, exist_ok=True)
    resp_file = ev_dir / ".supervision_responses.json"

    current_responses = {}
    if resp_file.is_file():
        try:
            current_responses = json.loads(resp_file.read_text(encoding="utf-8"))
            if not isinstance(current_responses, dict):
                current_responses = {}
        except Exception:
            current_responses = {}

    entry = {
        "checkpoint_id": checkpoint_id,
        "justification": (justification or "").strip(),
        "learner_action": (learner_action or "").strip() if learner_action else None,
        "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
    current_responses[checkpoint_id] = entry

    # Escritura atómica
    tmp_file = ev_dir / f".supervision_responses.tmp.{os.getpid()}"
    tmp_file.write_text(json.dumps(current_responses, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp_file, resp_file)

    return entry


def parse_target_yaml_simple(path: pathlib.Path) -> Dict[str, Any]:
    """Lee y extrae campos clave de target.yaml de forma robusta con o sin PyYAML."""
    if not path.is_file():
        return {}
    content = path.read_text(encoding="utf-8")
    if yaml is not None:
        try:
            return yaml.safe_load(content) or {}
        except Exception:
            pass

    # Parser básico
    data: Dict[str, Any] = {"authorization": {}, "scope": {"in_scope": {}}}
    current_section = None
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.endswith(":"):
            current_section = line[:-1].strip()
            continue
        if current_section == "authorization" and ":" in line:
            k, v = line.split(":", 1)
            v = v.strip().lower()
            data["authorization"][k.strip()] = v == "true"
    return data


def evaluate_supervision_checkpoints(engagement_dir: Union[str, pathlib.Path]) -> Dict[str, Any]:
    """Evalúa los checkpoints pedagógicos de auditoría para el directorio del engagement."""
    eng_path = pathlib.Path(engagement_dir)
    if not eng_path.is_dir():
        raise FileNotFoundError(f"Directorio de engagement no encontrado: {eng_path}")

    # 1. Alcance
    target_yaml_file = eng_path / "target.yaml"
    target_data = parse_target_yaml_simple(target_yaml_file) if target_yaml_file.is_file() else {}
    target_yaml_present = target_yaml_file.is_file()

    auth_meta = target_data.get("authorization", {})
    allow_passive = bool(auth_meta.get("allow_passive", False))
    allow_active = bool(auth_meta.get("allow_active", False))

    scope_status = "PASSED" if (target_yaml_present and (allow_passive or allow_active)) else ("PENDING" if target_yaml_present else "BLOCKED")
    scope_reason = "Alcance definido y permisos formalmente autorizados." if scope_status == "PASSED" else "Falta autorización explícita en target.yaml."

    # 2. Reconocimiento
    recon_dir = eng_path / "recon"
    live_hosts_file = recon_dir / "live_hosts.txt"
    subdomains_file = recon_dir / "subdomains.txt"

    live_hosts_count = 0
    if live_hosts_file.is_file():
        try:
            live_hosts_count = len([line for line in live_hosts_file.read_text(encoding="utf-8").splitlines() if line.strip()])
        except Exception:
            pass

    subdomains_count = 0
    if subdomains_file.is_file():
        try:
            subdomains_count = len([line for line in subdomains_file.read_text(encoding="utf-8").splitlines() if line.strip()])
        except Exception:
            pass

    recon_status = "PASSED" if live_hosts_count > 0 else ("IN_PROGRESS" if subdomains_count > 0 else "NOT_STARTED")
    recon_reason = f"Superficie identificada ({live_hosts_count} hosts vivos, {subdomains_count} subdominios)." if recon_status == "PASSED" else "Sin hosts vivos detectados todavía."

    # 3. Evidencias
    ev_dir = eng_path / "evidence"
    evidence_files = list(ev_dir.glob("*.md")) if ev_dir.is_dir() else []
    total_findings = len([f for f in evidence_files if not f.name.startswith("_")])

    ev_status = "PASSED" if total_findings > 0 else "NOT_STARTED"
    ev_reason = f"Fichas de evidencia registradas ({total_findings} hallazgos)." if ev_status == "PASSED" else "Sin hallazgos documentados."

    # 4. Reporte
    report_file = eng_path / "REPORT.md"
    report_present = report_file.is_file()
    deliverables_dir = eng_path / "deliverables"
    exports_dir = eng_path / "exports"

    deliv_count = 0
    if deliverables_dir.is_dir():
        deliv_count += len(list(deliverables_dir.iterdir()))
    if exports_dir.is_dir():
        deliv_count += len(list(exports_dir.iterdir()))

    report_status = "PASSED" if (report_present and deliv_count > 0) else ("IN_PROGRESS" if report_present else "NOT_STARTED")
    report_reason = "Reporte compilado y paquete de entregables exportado." if report_status == "PASSED" else "Falta compilar o exportar el reporte final."

    checkpoints = [
        {
            "id": "cp_scope",
            "title": "Definición y Autorización de Alcance",
            "stage": "scope",
            "status": scope_status,
            "reason": scope_reason,
            "hint": "Revisa y autoriza target.yaml habilitando permisos pasivos o activos.",
        },
        {
            "id": "cp_recon",
            "title": "Mapeo de Superficie y Hosts Vivos",
            "stage": "recon",
            "status": recon_status,
            "reason": recon_reason,
            "hint": "Ejecuta el reconocimiento o sondeo web sobre los dominios en alcance.",
        },
        {
            "id": "cp_evidence",
            "title": "Documentación y Evidencia de Hallazgos",
            "stage": "triage",
            "status": ev_status,
            "reason": ev_reason,
            "hint": "Crea fichas en evidence/*.md vinculando comandos reproducibles.",
        },
        {
            "id": "cp_report",
            "title": "Informe Técnico de Auditoría y Cierre",
            "stage": "reporting",
            "status": report_status,
            "reason": report_reason,
            "hint": "Compila REPORT.md y genera el paquete de entregables.",
        },
    ]

    responses = load_supervision_responses(eng_path)
    for cp in checkpoints:
        resp = responses.get(cp["id"])
        cp["learner_response"] = resp
        cp["is_justified"] = bool(resp and resp.get("justification"))

    current_stage = "scope"
    if total_findings > 0 and report_present:
        current_stage = "reporting"
    elif total_findings > 0:
        current_stage = "triage"
    elif live_hosts_count > 0:
        current_stage = "probing"
    elif subdomains_count > 0:
        current_stage = "recon"

    return {
        "engagement": eng_path.name,
        "current_stage": current_stage,
        "live_hosts_count": live_hosts_count,
        "subdomains_count": subdomains_count,
        "total_findings": total_findings,
        "report_present": report_present,
        "deliverables_count": deliv_count,
        "checkpoints": checkpoints,
    }


def export_supervision_markdown(state: Dict[str, Any]) -> str:
    """Genera informe en Markdown de supervisión pedagógica a partir del diccionario de estado."""
    eng_name = state.get("engagement") or state.get("engagement_id") or "engagement"
    stage = state.get("current_stage", "scope")
    lines = [
        f"# Informe de Supervisión Pedagógica: {eng_name}",
        "",
        f"- **Etapa Actual**: `{stage}`",
        "",
        "## 1. Checkpoints Pedagógicos Formativos",
        "",
        "| ID | Checkpoint | Etapa | Estado | Evaluación | Guía / Siguiente Acción |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for cp in state.get("checkpoints", []):
        cid = cp.get("id", "-")
        title = (cp.get("title") or cid).replace("|", "\\|")
        stg = cp.get("stage", "-")
        status = cp.get("status", "NOT_STARTED")
        reason = (cp.get("reason") or "-").replace("|", "\\|")
        hint = (cp.get("hint") or "-").replace("|", "\\|")
        lines.append(f"| `{cid}` | {title} | {stg} | {status} | {reason} | {hint} |")

    lines.extend([
        "",
        "## 2. Resumen Operacional por Disciplina",
        "",
        f"- **Reconocimiento y Sondeo**: Hosts vivos: {state.get('live_hosts_count', 0)} · Subdominios: {state.get('subdomains_count', 0)}",
        f"- **Hallazgos y Evidencias**: Total hallazgos: {state.get('total_findings', 0)}",
        f"- **Informe y Entregables**: REPORT.md: {'Presente' if state.get('report_present') else 'Pendiente'} · Entregables exportados: {state.get('deliverables_count', 0)}",
        "",
    ])

    justifications = [
        cp for cp in state.get("checkpoints", []) if cp.get("learner_response") and cp["learner_response"].get("justification")
    ]
    if justifications:
        lines.extend([
            "## 3. Justificaciones y Decisiones del Estudiante",
            "",
        ])
        for cp in justifications:
            resp = cp["learner_response"]
            lines.append(f"- **{cp.get('title', cp.get('id'))}**: {resp.get('justification')}")
            if resp.get("learner_action"):
                lines.append(f"  - Acción: `{resp.get('learner_action')}`")
        lines.append("")

    return "\n".join(lines)


def export_supervision_report(
    engagement_dir: Union[str, pathlib.Path],
    format: str = "json",
) -> str:
    """Exporta el informe de supervisión pedagógica en formato JSON o Markdown."""
    state = evaluate_supervision_checkpoints(engagement_dir)
    fmt = (format or "json").lower()
    if fmt == "json":
        return json.dumps(state, indent=2, ensure_ascii=False)
    elif fmt in ("markdown", "md"):
        return export_supervision_markdown(state)
    else:
        raise ValueError(f"Formato no soportado: '{format}'. Debe ser 'json' o 'markdown'.")


def compute_cohort_supervision_summary(workspace_dir: Union[str, pathlib.Path]) -> Dict[str, Any]:
    """Calcula la vista agregada de supervisión pedagógica para la cohorte del aula docente (V3-06e)."""
    ws_path = pathlib.Path(workspace_dir)
    found_projects = []

    eng_root = ws_path / "engagements"
    if eng_root.is_dir():
        for d in eng_root.iterdir():
            if d.is_dir() and not d.name.startswith("."):
                found_projects.append((d.name, "engagement", d))

    retos_root = ws_path / "retos"
    if retos_root.is_dir():
        for d in retos_root.iterdir():
            if d.is_dir() and not d.name.startswith("."):
                found_projects.append((d.name, "reto", d))

    total_projects = len(found_projects)
    if total_projects == 0:
        return {
            "total_cohort_projects": 0,
            "cohort_total_checkpoints": 0,
            "cohort_passed_checkpoints": 0,
            "cohort_completion_pct": 0.0,
            "blocked_projects_count": 0,
            "fully_completed_projects_count": 0,
            "checkpoint_breakdown": {
                "cp_scope": {"title": "Alcance & Reglas", "passed": 0, "blocked": 0, "in_progress": 0, "not_started": 0},
                "cp_recon": {"title": "Superficie & Hosts", "passed": 0, "blocked": 0, "in_progress": 0, "not_started": 0},
                "cp_evidence": {"title": "Hallazgos & Evidencias", "passed": 0, "blocked": 0, "in_progress": 0, "not_started": 0},
                "cp_report": {"title": "Informe Técnico", "passed": 0, "blocked": 0, "in_progress": 0, "not_started": 0},
            },
            "projects": [],
        }

    cohort_passed_checkpoints = 0
    blocked_projects_count = 0
    fully_completed_count = 0

    cp_stats = {
        "cp_scope": {"title": "Alcance & Reglas", "passed": 0, "blocked": 0, "in_progress": 0, "not_started": 0},
        "cp_recon": {"title": "Superficie & Hosts", "passed": 0, "blocked": 0, "in_progress": 0, "not_started": 0},
        "cp_evidence": {"title": "Hallazgos & Evidencias", "passed": 0, "blocked": 0, "in_progress": 0, "not_started": 0},
        "cp_report": {"title": "Informe Técnico", "passed": 0, "blocked": 0, "in_progress": 0, "not_started": 0},
    }

    projects_summary = []

    for p_id, p_type, p_path in found_projects:
        try:
            state = evaluate_supervision_checkpoints(p_path)
            passed_cps = 0
            has_blocked = False

            cps_data = []
            for cp in state.get("checkpoints", []):
                cid = cp.get("id")
                status = cp.get("status", "NOT_STARTED")
                if cid in cp_stats:
                    if status == "PASSED":
                        cp_stats[cid]["passed"] += 1
                        passed_cps += 1
                    elif status == "BLOCKED":
                        cp_stats[cid]["blocked"] += 1
                        has_blocked = True
                    elif status == "IN_PROGRESS":
                        cp_stats[cid]["in_progress"] += 1
                    else:
                        cp_stats[cid]["not_started"] += 1

                cps_data.append({
                    "id": cid,
                    "title": cp.get("title", cid),
                    "status": status,
                    "reason": cp.get("reason", ""),
                })

            cohort_passed_checkpoints += passed_cps
            if has_blocked or state.get("is_blocked"):
                blocked_projects_count += 1
            if passed_cps == 4:
                fully_completed_count += 1

            projects_summary.append({
                "id": p_id,
                "type": p_type,
                "overall_status": state.get("overall_status", "NOT_STARTED"),
                "passed_count": passed_cps,
                "is_blocked": bool(has_blocked or state.get("is_blocked")),
                "checkpoints": cps_data,
            })
        except Exception:
            continue

    total_cps = total_projects * 4
    completion_pct = round((cohort_passed_checkpoints / total_cps * 100), 1) if total_cps > 0 else 0.0

    return {
        "total_cohort_projects": total_projects,
        "cohort_total_checkpoints": total_cps,
        "cohort_passed_checkpoints": cohort_passed_checkpoints,
        "cohort_completion_pct": completion_pct,
        "blocked_projects_count": blocked_projects_count,
        "fully_completed_projects_count": fully_completed_count,
        "checkpoint_breakdown": cp_stats,
        "projects": projects_summary,
    }


