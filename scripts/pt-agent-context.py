#!/usr/bin/env python3
"""Agregador de Contexto para Agentes de Seguridad (Agent Context Aggregator) para SecLab-SBF.

Sintetiza de forma determinista la superficie de ataque, especificación de alcance
(target.yaml / scope.txt), hallazgos validados (evidence/*.md), bitácora de auditoría
(terminal.log) y playbooks metodológicos (skills / prompts) en un bloque estructurado
de contexto Markdown o JSON listo para inyección en LLMs o consulta del operador.

Sin dependencias externas obligatorias (Python 3 stdlib).
"""

import argparse
import datetime
import importlib.machinery
import importlib.util
import json
import os
import pathlib
import re
import subprocess
import sys
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from seclab_findings import finding_status_from_markdown

SEVERITY_ORDER = {
    "CRITICAL": 5,
    "HIGH": 4,
    "MEDIUM": 3,
    "LOW": 2,
    "INFO": 1,
}


def parse_simple_yaml_lists(content: str) -> Dict[str, Any]:
    """Parser liviano de respaldo para target.yaml sin dependencias externas."""
    data: Dict[str, Any] = {
        "scope": {
            "in_scope": {"domains": [], "ips": [], "cidrs": [], "endpoints": []},
            "out_of_scope": {"domains": [], "ips": [], "cidrs": [], "notes": []},
        },
        "operational_limits": {},
        "engagement": {},
    }

    current_section = None
    current_sub = None
    current_list = None

    for line in content.splitlines():
        line_str = line.strip()
        if not line_str or line_str.startswith("#"):
            continue

        if line.startswith("engagement:"):
            current_section = "engagement"
            continue
        elif line.startswith("scope:"):
            current_section = "scope"
            continue
        elif line.startswith("operational_limits:"):
            current_section = "operational_limits"
            continue
        elif not line.startswith(" ") and not line.startswith("\t"):
            current_section = None

        if current_section == "engagement":
            if ":" in line_str:
                k, v = line_str.split(":", 1)
                data["engagement"][k.strip()] = v.strip().strip("'\"")
        elif current_section == "operational_limits":
            if ":" in line_str:
                k, v = line_str.split(":", 1)
                data["operational_limits"][k.strip()] = v.strip().strip("'\"")
        elif current_section == "scope":
            indent = len(line) - len(line.lstrip())
            if indent in (2, 4) and line_str.endswith(":"):
                sub_name = line_str[:-1].strip()
                if sub_name in ("in_scope", "out_of_scope"):
                    current_sub = sub_name
                    current_list = None
                elif current_sub and sub_name in ("domains", "ips", "cidrs", "endpoints", "notes"):
                    current_list = sub_name
            elif line_str.startswith("-") and current_sub and current_list:
                item = line_str[1:].strip().strip("'\"")
                if " #" in item:
                    item = item.split(" #")[0].strip().strip("'\"")
                if item:
                    data["scope"][current_sub][current_list].append(item)

    return data


def parse_frontmatter(content: str) -> Tuple[Dict[str, Any], str]:
    """Extrae metadata YAML simple del encabezado y el cuerpo markdown."""
    metadata: Dict[str, Any] = {}
    body = content

    if content.startswith("---\n"):
        parts = content.split("---\n", 2)
        if len(parts) >= 3:
            fm_text = parts[1]
            body = parts[2]
            for line in fm_text.splitlines():
                line_str = line.strip()
                if not line_str or line_str.startswith("#"):
                    continue
                if ":" in line_str:
                    key, val = line_str.split(":", 1)
                    key = key.strip()
                    val = val.strip().strip("'\"")
                    if " #" in val:
                        val = val.split(" #")[0].strip().strip("'\"")
                    metadata[key] = val

    return metadata, body


def resolve_engagement_dir(target_arg: Optional[str] = None) -> Optional[pathlib.Path]:
    """Localiza el directorio del engagement basado en argumento o contexto actual."""
    candidates = []

    if target_arg:
        p = pathlib.Path(target_arg).expanduser()
        if p.is_dir():
            return p.resolve()

        # Comprobar en rutas estándar
        ws_env = os.environ.get("WORKSPACE_DIR")
        ws_dirs = [pathlib.Path(ws_env)] if ws_env else []
        ws_dirs.extend([
            pathlib.Path("/workspace"),
            pathlib.Path("./workspace"),
            pathlib.Path("."),
        ])

        for base in ws_dirs:
            for cat in ("engagements", "retos"):
                candidate = base / cat / target_arg
                if candidate.is_dir():
                    return candidate.resolve()
            candidate_direct = base / target_arg
            if candidate_direct.is_dir() and (candidate_direct / "target.yaml").is_file():
                return candidate_direct.resolve()

    # Si no se especificó argumento, inspeccionar directorio actual
    cwd = pathlib.Path.cwd().resolve()
    if (cwd / "target.yaml").is_file() or (cwd / "evidence").is_dir() or (cwd / "scope.txt").is_file():
        return cwd

    # Inspeccionar variable de log activo en tmux si estamos en tmux
    if "TMUX" in os.environ:
        try:
            res = subprocess.run(
                ["tmux", "show-option", "-pv", "@seclab_log_file"],
                capture_output=True,
                text=True,
                check=False,
            )
            log_path = res.stdout.strip()
            if log_path:
                log_file = pathlib.Path(log_path)
                if log_file.parent.is_dir():
                    return log_file.parent.resolve()
        except Exception:
            pass

    # Inspeccionar el engagement modificado más recientemente en workspace
    ws_env = os.environ.get("WORKSPACE_DIR")
    search_dirs = [pathlib.Path(ws_env)] if ws_env else []
    search_dirs.extend([
        pathlib.Path("/workspace/engagements"),
        pathlib.Path("./workspace/engagements"),
        pathlib.Path("./engagements"),
    ])

    newest_dir = None
    newest_mtime = -1.0
    for s_dir in search_dirs:
        if s_dir.is_dir():
            for child in s_dir.iterdir():
                if child.is_dir() and not child.name.startswith((".", "_")):
                    try:
                        mtime = child.stat().st_mtime
                        if mtime > newest_mtime:
                            newest_mtime = mtime
                            newest_dir = child
                    except OSError:
                        continue

    return newest_dir.resolve() if newest_dir else None


def load_scope_data(engagement_dir: pathlib.Path) -> Dict[str, Any]:
    """Carga target.yaml o scope.txt del engagement."""
    target_yaml = engagement_dir / "target.yaml"
    if target_yaml.is_file():
        try:
            content = target_yaml.read_text(encoding="utf-8")
            return parse_simple_yaml_lists(content)
        except Exception as e:
            return {"error": f"No se pudo leer target.yaml: {e}"}

    scope_txt = engagement_dir / "scope.txt"
    if scope_txt.is_file():
        domains = []
        for line in scope_txt.read_text(encoding="utf-8").splitlines():
            line_str = line.strip()
            if line_str and not line_str.startswith("#"):
                domains.append(line_str)
        return {
            "engagement": {"name": engagement_dir.name},
            "scope": {
                "in_scope": {"domains": domains, "ips": [], "cidrs": [], "endpoints": []},
                "out_of_scope": {"domains": [], "ips": [], "cidrs": [], "notes": []},
            },
            "operational_limits": {},
        }

    return {
        "engagement": {"name": engagement_dir.name},
        "scope": {
            "in_scope": {"domains": [], "ips": [], "cidrs": [], "endpoints": []},
            "out_of_scope": {"domains": [], "ips": [], "cidrs": [], "notes": []},
        },
        "operational_limits": {},
    }


def collect_recon_summary(engagement_dir: pathlib.Path) -> Dict[str, Any]:
    """Resume los archivos de reconocimiento encontrados en recon/ y fuzzing/."""
    recon_dir = engagement_dir / "recon"
    summary: Dict[str, Any] = {
        "live_hosts": [],
        "subdomains_count": 0,
        "urls_count": 0,
        "js_files_count": 0,
        "patterns": {},
        "fuzzing_files": [],
    }

    if recon_dir.is_dir():
        # Live hosts
        live_file = recon_dir / "live_hosts.txt"
        if live_file.is_file():
            hosts = [l.strip() for l in live_file.read_text(encoding="utf-8").splitlines() if l.strip()]
            summary["live_hosts"] = hosts

        # Subdomains
        sub_file = recon_dir / "subdomains.txt"
        if sub_file.is_file():
            subs = [l.strip() for l in sub_file.read_text(encoding="utf-8").splitlines() if l.strip()]
            summary["subdomains_count"] = len(subs)

        # URLs y endpoints
        for candidate_url_file in ("urls_all.txt", "urls.txt", "endpoints.txt"):
            uf = recon_dir / candidate_url_file
            if uf.is_file():
                urls = [l.strip() for l in uf.read_text(encoding="utf-8").splitlines() if l.strip()]
                summary["urls_count"] = max(summary["urls_count"], len(urls))

        # JS Files
        js_file = recon_dir / "js_files.txt"
        if js_file.is_file():
            js_lines = [l.strip() for l in js_file.read_text(encoding="utf-8").splitlines() if l.strip()]
            summary["js_files_count"] = len(js_lines)

        # Patterns (gf)
        pat_dir = recon_dir / "patterns"
        if pat_dir.is_dir():
            for pf in pat_dir.glob("*.txt"):
                p_lines = [l.strip() for l in pf.read_text(encoding="utf-8").splitlines() if l.strip()]
                if p_lines:
                    summary["patterns"][pf.stem] = len(p_lines)

    fuzz_dir = engagement_dir / "fuzzing"
    if fuzz_dir.is_dir():
        for ff in fuzz_dir.iterdir():
            if ff.is_file() and not ff.name.startswith("."):
                summary["fuzzing_files"].append(ff.name)

    return summary


def collect_findings(engagement_dir: pathlib.Path) -> List[Dict[str, Any]]:
    """Carga y estructura las fichas y sus estados declarados en evidence/."""
    ev_dir = engagement_dir / "evidence"
    if not ev_dir.is_dir():
        return []

    findings: List[Dict[str, Any]] = []
    for f in sorted(ev_dir.glob("*.md")):
        if f.name.startswith(("_", ".")) or f.name.lower() == "readme.md":
            continue
        try:
            content = f.read_text(encoding="utf-8")
            meta, body = parse_frontmatter(content)
            fid = meta.get("id", f.stem.upper())
            title = meta.get("title", "")
            if not title:
                match = re.search(r"^#\s+(?:\[.*?\]\s*)?(.+)$", body, re.MULTILINE)
                title = match.group(1).strip() if match else f.stem.replace("-", " ").title()

            severity = str(meta.get("severity", "MEDIUM")).strip().upper()
            if severity not in SEVERITY_ORDER:
                severity = "MEDIUM"

            cvss_score = 0.0
            if "cvss_score" in meta:
                try:
                    cvss_score = float(meta["cvss_score"])
                except ValueError:
                    cvss_score = 0.0

            findings.append({
                "id": fid,
                "file": f.name,
                "title": title,
                "severity": severity,
                "asset": meta.get("asset", "N/A"),
                "cwe": meta.get("cwe", "CWE-Unknown"),
                "cvss_score": cvss_score,
                "status": finding_status_from_markdown(content),
            })
        except Exception:
            continue

    findings.sort(
        key=lambda x: (SEVERITY_ORDER.get(x["severity"], 0), x["cvss_score"]),
        reverse=True,
    )
    return findings


def collect_audit_marks(engagement_dir: pathlib.Path, max_marks: int = 8) -> Tuple[int, str, List[str]]:
    """Extrae estadísticas y los últimos hitos de auditoría de terminal.log."""
    log_file = engagement_dir / "terminal.log"
    if not log_file.is_file():
        return 0, "0 B", []

    total_lines = 0
    size_str = "0 B"
    try:
        size_bytes = log_file.stat().st_size
        if size_bytes < 1024:
            size_str = f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            size_str = f"{size_bytes / 1024:.1f} KB"
        else:
            size_str = f"{size_bytes / (1024 * 1024):.1f} MB"
    except OSError:
        pass

    marks: List[str] = []
    mark_pattern = re.compile(r">>>\s*\[(.*?)\]\s*\[AUDIT-MARK\]\s*(.*?)\s*<<<")

    try:
        with log_file.open("r", encoding="utf-8", errors="replace") as f:
            for line in f:
                total_lines += 1
                m = mark_pattern.search(line)
                if m:
                    timestamp = m.group(1).split("T")[-1].split("+")[0]
                    text = m.group(2).strip()
                    marks.append(f"[{timestamp}] {text}")
    except OSError:
        pass

    recent_marks = marks[-max_marks:] if marks else []
    return total_lines, size_str, recent_marks


def resolve_skill_or_prompt(query: str) -> Optional[Dict[str, Any]]:
    """Encuentra y extrae directivas clave de una skill o prompt template."""
    cleaned = query.strip().lower().replace("_", "-")
    # Mapeo de alias comunes
    alias_map = {
        "recon": "recon-profiling",
        "fuzzing": "param-discovery",
        "fuzz": "param-discovery",
        "params": "param-discovery",
        "triage": "triage-gatekeeper",
        "report": "report-generation",
        "reporting": "report-generation",
        "auth": "auth-matrix-audit",
        "idor": "auth-matrix-audit",
        "logic": "business-logic-audit",
        "spa": "client-side-spa-audit",
        "client": "client-side-spa-audit",
        "api": "api-security-audit",
        "injection": "ssrf-injection-audit",
        "ssrf": "ssrf-injection-audit",
        "guard": "duplicate-scope-guard",
    }
    skill_target = alias_map.get(cleaned, cleaned)

    search_roots = [
        pathlib.Path("./skills"),
        pathlib.Path("./workspace-seed/skills"),
        pathlib.Path("/workspace/skills"),
        pathlib.Path(__file__).resolve().parent.parent / "skills",
        pathlib.Path(__file__).resolve().parent.parent / "workspace-seed" / "skills",
        pathlib.Path("/usr/local/share/seclab/skills"),
    ]

    # 1. Buscar en directivas de skills (SKILL.md)
    for root in search_roots:
        candidate_skill = root / skill_target / "SKILL.md"
        if candidate_skill.is_file():
            content = candidate_skill.read_text(encoding="utf-8")
            meta, body = parse_frontmatter(content)
            return {
                "type": "skill",
                "name": meta.get("name", skill_target),
                "category": meta.get("category", "general"),
                "description": meta.get("description", ""),
                "body": body.strip(),
            }

    # 2. Buscar en prompts de agentes (*.prompt.md)
    prompt_names = []
    if cleaned.endswith(".prompt.md"):
        prompt_names.append(cleaned)
    elif cleaned.endswith(".md"):
        prompt_names.append(cleaned)
        prompt_names.append(f"{cleaned[:-3]}.prompt.md")
    elif cleaned.endswith("-agent"):
        prompt_names.append(f"{cleaned}.prompt.md")
    else:
        prompt_names.append(f"{cleaned}-agent.prompt.md")
        prompt_names.append(f"{cleaned}.prompt.md")

    prompt_roots = [
        pathlib.Path("./skills/prompts"),
        pathlib.Path("./workspace-seed/templates/prompts"),
        pathlib.Path("/workspace/templates/prompts"),
        pathlib.Path(__file__).resolve().parent.parent / "skills" / "prompts",
        pathlib.Path(__file__).resolve().parent.parent / "workspace-seed" / "templates" / "prompts",
    ]
    for p_root in prompt_roots:
        for p_name in prompt_names:
            candidate_prompt = p_root / p_name
            if candidate_prompt.is_file():
                content = candidate_prompt.read_text(encoding="utf-8")
                return {
                    "type": "prompt",
                    "name": candidate_prompt.name,
                    "body": content.strip(),
                }


    return None


def _get_audit_checklist_module():
    """Carga dinámicamente el módulo pt-audit-checklist si está disponible."""
    candidate_paths = [
        pathlib.Path(__file__).resolve().parent / "pt-audit-checklist.py",
        pathlib.Path(__file__).resolve().parent / "pt-audit-checklist",
        pathlib.Path("/usr/local/bin/pt-audit-checklist"),
        pathlib.Path("./scripts/pt-audit-checklist.py"),
    ]
    for cp in candidate_paths:
        if cp.is_file():
            try:
                spec = importlib.util.spec_from_file_location("pt_audit_checklist", cp,
                    loader=importlib.machinery.SourceFileLoader("pt_audit_checklist", str(cp)))
                if spec and spec.loader:
                    mod = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(mod)
                    return mod
            except Exception:
                pass
    return None


def collect_coverage_summary(engagement_dir: pathlib.Path) -> Dict[str, Any]:
    """Extrae el resumen de cobertura metodológica y estado del checklist."""
    mod = _get_audit_checklist_module()
    if mod and hasattr(mod, "AuditChecklistEvaluator"):
        try:
            evaluator = mod.AuditChecklistEvaluator(engagement_dir)
            res = evaluator.evaluate()
            return {
                "coverage_score": res.get("coverage_score", 0.0),
                "completed_areas": res.get("completed_areas", 0),
                "in_progress_areas": res.get("in_progress_areas", 0),
                "total_areas": res.get("total_areas", 8),
                "ready_for_closure": res.get("readiness", {}).get("ready_for_closure", False),
                "blocking_issues": res.get("readiness", {}).get("blocking_issues", []),
                "recommendations": res.get("readiness", {}).get("recommendations", []),
                "matrix": [
                    {
                        "id": m.get("id"),
                        "name": m.get("name"),
                        "skill": m.get("skill"),
                        "status": m.get("status"),
                        "findings_count": m.get("findings_count", 0),
                    }
                    for m in res.get("matrix", [])
                ],
            }
        except Exception:
            pass

    return {
        "coverage_score": 0.0,
        "completed_areas": 0,
        "in_progress_areas": 0,
        "total_areas": 8,
        "ready_for_closure": False,
        "blocking_issues": [],
        "recommendations": [],
        "matrix": [],
    }


def generate_context_dict(engagement_dir: pathlib.Path, skill_query: Optional[str] = None) -> Dict[str, Any]:
    """Consolida todos los componentes de contexto en una estructura dict determinista."""
    scope_data = load_scope_data(engagement_dir)
    recon_data = collect_recon_summary(engagement_dir)
    findings = collect_findings(engagement_dir)
    log_lines, log_size, recent_marks = collect_audit_marks(engagement_dir)
    coverage_data = collect_coverage_summary(engagement_dir)

    sev_counts = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0, "INFO": 0}
    for f in findings:
        sev = f.get("severity", "MEDIUM")
        sev_counts[sev] = sev_counts.get(sev, 0) + 1

    context: Dict[str, Any] = {
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "engagement": {
            "name": scope_data.get("engagement", {}).get("name", engagement_dir.name),
            "directory": str(engagement_dir),
            "target": scope_data.get("engagement", {}).get("target", "N/A"),
        },
        "scope": scope_data.get("scope", {}),
        "operational_limits": scope_data.get("operational_limits", {}),
        "coverage": coverage_data,
        "recon": recon_data,
        "findings": {
            "total": len(findings),
            "severity_counts": sev_counts,
            "items": findings,
        },
        "audit": {
            "log_lines": log_lines,
            "log_size": log_size,
            "recent_marks": recent_marks,
        },
    }

    if skill_query:
        skill_info = resolve_skill_or_prompt(skill_query)
        if skill_info:
            context["active_skill"] = skill_info

    return context


def format_markdown_context(data: Dict[str, Any]) -> str:
    """Convierte el diccionario de contexto consolidado en un bloque Markdown limpio y denso."""
    eng = data["engagement"]
    scope = data.get("scope", {})
    in_scope = scope.get("in_scope", {})
    out_of_scope = scope.get("out_of_scope", {})
    limits = data.get("operational_limits", {})
    coverage = data.get("coverage", {})
    recon = data.get("recon", {})
    findings = data.get("findings", {})
    audit = data.get("audit", {})

    lines: List[str] = [
        f"# Contexto de Seguridad del Agente: {eng['name']}",
        f"> Directorio activo: `{eng['directory']}` | Timestamp: `{data['timestamp']}`",
        "",
        "---",
        "",
        "## 1. Alcance y Reglas de Compromiso (Scope & Limits)",
        "",
    ]

    # In-Scope
    in_domains = in_scope.get("domains", [])
    in_ips = in_scope.get("ips", [])
    in_cidrs = in_scope.get("cidrs", [])
    in_endpoints = in_scope.get("endpoints", [])

    lines.append("### Activos Autorizados (In-Scope)")
    if in_domains:
        lines.append(f"- **Dominios:** {', '.join(f'`{d}`' for d in in_domains)}")
    if in_ips:
        lines.append(f"- **IPs:** {', '.join(f'`{i}`' for i in in_ips)}")
    if in_cidrs:
        lines.append(f"- **CIDRs:** {', '.join(f'`{c}`' for c in in_cidrs)}")
    if in_endpoints:
        lines.append(f"- **Endpoints:** {', '.join(f'`{e}`' for e in in_endpoints)}")
    if not (in_domains or in_ips or in_cidrs or in_endpoints):
        lines.append("- _(No se especificaron activos in-scope en target.yaml / scope.txt)_")

    # Out-of-Scope
    out_domains = out_of_scope.get("domains", [])
    out_ips = out_of_scope.get("ips", [])
    out_notes = out_of_scope.get("notes", [])

    lines.append("")
    lines.append("### Activos Excluidos y Prohibidos (Out-of-Scope)")
    if out_domains:
        lines.append(f"- **Dominios Excluidos:** {', '.join(f'`{d}`' for d in out_domains)}")
    if out_ips:
        lines.append(f"- **IPs Excluidas:** {', '.join(f'`{i}`' for i in out_ips)}")
    if out_notes:
        lines.append(f"- **Restricciones:** {', '.join(out_notes)}")
    if not (out_domains or out_ips or out_notes):
        lines.append("- _(No hay exclusiones explícitas listadas)_")

    # Límites
    if limits:
        lines.append("")
        lines.append("### Límites Operacionales")
        for k, v in limits.items():
            lines.append(f"- **{k}:** {v}")

    # Cobertura Metodológica & Checklist
    lines.extend([
        "",
        "---",
        "",
        f"## 2. Cobertura Metodológica & Checklist ({coverage.get('coverage_score', 0.0)}%)",
        "",
    ])
    completed = coverage.get("completed_areas", 0)
    in_prog = coverage.get("in_progress_areas", 0)
    tot = coverage.get("total_areas", 8)
    lines.append(f"- **Progreso Metodológico:** {completed}/{tot} disciplinas completadas, {in_prog} en curso (Puntaje: **{coverage.get('coverage_score', 0.0)}%**)")
    ready = coverage.get("ready_for_closure", False)
    lines.append(f"- **Compuerta de Cierre:** {'Listo para cerrar' if ready else 'Requisitos de cierre pendientes'}")

    matrix = coverage.get("matrix", [])
    if matrix:
        lines.append("")
        lines.append("| Disciplina Metodológica | Skill Sugerida | Estado | Hallazgos |")
        lines.append("|---|---|---|---|")
        for m in matrix:
            status_badge = "COMPLETADO" if m["status"] == "COMPLETED" else ("EN CURSO" if m["status"] == "IN_PROGRESS" else "PENDIENTE")
            lines.append(f"| {m['name']} | `{m['skill']}` | {status_badge} | {m['findings_count']} |")

    blocking = coverage.get("blocking_issues", [])
    if blocking:
        lines.append("")
        lines.append("- **Bloqueos para Cierre:**")
        for b in blocking:
            lines.append(f"  - ⚠️ {b}")

    # Reconocimiento
    lines.extend([
        "",
        "---",
        "",
        "## 3. Superficie de Ataque y Reconocimiento",
        "",
    ])
    live_hosts = recon.get("live_hosts", [])
    sub_count = recon.get("subdomains_count", 0)
    urls_count = recon.get("urls_count", 0)
    js_count = recon.get("js_files_count", 0)
    patterns = recon.get("patterns", {})

    lines.append(f"- **Subdominios Descubiertos:** {sub_count}")
    lines.append(f"- **Servicios Web Activos:** {len(live_hosts)}")
    if live_hosts:
        sample_hosts = live_hosts[:8]
        lines.append(f"  - Muestra: {', '.join(f'`{h}`' for h in sample_hosts)}{' ...' if len(live_hosts) > 8 else ''}")
    lines.append(f"- **URLs / Endpoints Indexados:** {urls_count}")
    lines.append(f"- **Archivos JavaScript Analizados:** {js_count}")

    if patterns:
        pat_summary = ", ".join(f"{k}: {v}" for k, v in sorted(patterns.items()))
        lines.append(f"- **Patrones Sensibles Detectados (gf):** {pat_summary}")

    # Hallazgos
    lines.extend([
        "",
        "---",
        "",
        "## 4. Matriz de Hallazgos y Estados Declarados (Evidence-First)",
        "",
    ])
    total_findings = findings.get("total", 0)
    counts = findings.get("severity_counts", {})
    count_summary = f"Total: {total_findings} (Crítico: {counts.get('CRITICAL', 0)}, Alto: {counts.get('HIGH', 0)}, Medio: {counts.get('MEDIUM', 0)}, Bajo: {counts.get('LOW', 0)}, Info: {counts.get('INFO', 0)})"
    lines.append(f"- **Resumen:** {count_summary}")
    lines.append("")

    items = findings.get("items", [])
    if items:
        lines.append("| ID | Estado declarado | Severidad | Activo | CWE | Título |")
        lines.append("|---|---|---|---|---|---|")
        for it in items:
            lines.append(f"| `{it['id']}` | `{it['status']}` | **{it['severity']}** | `{it['asset']}` | {it['cwe']} | {it['title']} |")
    else:
        lines.append("_No hay fichas registradas aún en `evidence/`._")

    # Auditoría
    lines.extend([
        "",
        "---",
        "",
        "## 5. Trazabilidad de Auditoría",
        "",
        f"- **Bitácora Activa:** `{eng['directory']}/terminal.log` ({audit.get('log_lines', 0)} líneas, {audit.get('log_size', '0 B')})",
    ])
    recent_marks = audit.get("recent_marks", [])
    if recent_marks:
        lines.append("- **Últimos Hitos Registrados (`pt-log mark`):**")
        for mark in recent_marks:
            lines.append(f"  - {mark}")
    else:
        lines.append("- _(Sin hitos de auditoría registrados en la sesión actual)_")

    # Skill activa si aplica
    active_skill = data.get("active_skill")
    if active_skill:
        lines.extend([
            "",
            "---",
            "",
            f"## 6. Directivas de Agente: {active_skill.get('name', 'Especialidad')}",
            "",
        ])
        if active_skill.get("type") == "skill":
            lines.append(f"> **Categoría:** `{active_skill.get('category')}` | **Descripción:** {active_skill.get('description')}")
            lines.append("")
            lines.append(active_skill.get("body", ""))
        else:
            lines.append(active_skill.get("body", ""))

    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Agregador de Contexto para Agentes de Seguridad de SecLab-SBF (pt-context).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Ejemplos:
  pt-agent-context.py                      # Agrega contexto del engagement actual o activo
  pt-agent-context.py acme-corp            # Agrega contexto del engagement acme-corp
  pt-agent-context.py acme-corp auth       # Agrega contexto e inyecta directivas de auth
  pt-agent-context.py --json               # Salida en JSON para automatizaciones
  pt-agent-context.py --copy               # Copia el contexto al portapapeles
""",
    )
    parser.add_argument("engagement", nargs="?", help="Nombre o ruta del engagement a auditar.")
    parser.add_argument("skill", nargs="?", help="Nombre de la skill o prompt a inyectar como directiva.")
    parser.add_argument("-e", "--engagement-dir", dest="eng_opt", help="Ruta explícita al engagement.")
    parser.add_argument("-s", "--skill-name", dest="skill_opt", help="Nombre de skill o prompt.")
    parser.add_argument("-j", "--json", action="store_true", help="Emitir salida estructurada en formato JSON.")
    parser.add_argument("-o", "--output", help="Guardar el contexto generado en un archivo de destino.")
    parser.add_argument("-c", "--copy", action="store_true", help="Copiar la salida al portapapeles del sistema.")

    args = parser.parse_args()

    target_eng = args.eng_opt or args.engagement
    target_skill = args.skill_opt or args.skill

    eng_dir = resolve_engagement_dir(target_eng)
    if not eng_dir or not eng_dir.is_dir():
        print(
            f"Error: No se pudo localizar el directorio del engagement ({target_eng or 'no especificado'}).\n"
            f"Asegúrate de estar en un engagement o especifica el nombre: pt-context <engagement>",
            file=sys.stderr,
        )
        return 1

    context_data = generate_context_dict(eng_dir, target_skill)

    if args.json:
        output_text = json.dumps(context_data, indent=2, ensure_ascii=False)
    else:
        output_text = format_markdown_context(context_data)

    if args.output:
        out_p = pathlib.Path(args.output).resolve()
        out_p.parent.mkdir(parents=True, exist_ok=True)
        out_p.write_text(output_text, encoding="utf-8")
        print(f"[+] Contexto guardado exitosamente en: {out_p}")
    else:
        print(output_text)

    if args.copy:
        # Intentar copiar al portapapeles con xclip o pbcopy
        copied = False
        for cmd in (["pbcopy"], ["xclip", "-selection", "clipboard"], ["xsel", "--clipboard", "--input"]):
            try:
                proc = subprocess.run(cmd, input=output_text, text=True, check=False)
                if proc.returncode == 0:
                    copied = True
                    break
            except FileNotFoundError:
                continue
        if copied:
            print("\n[+] Contexto copiado al portapapeles del sistema.", file=sys.stderr)
        else:
            print("\n[!] No se encontró pbcopy ni xclip para copiar al portapapeles.", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
