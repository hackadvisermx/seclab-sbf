#!/usr/bin/env python3
"""Evaluador de Cobertura y Checklist Metodológico de Auditoría para SecLab-SBF.

Analiza el estado integral de un engagement o reto (/workspace/engagements/<id>),
inspeccionando target.yaml, recon/, fuzzing/, evidence/*.md, terminal.log y REPORT.md
para calcular el porcentaje de cobertura contra el estándar de 8 disciplinas ofensivas:
1. Reconocimiento & Scope (recon-profiling)
2. Descubrimiento de Parámetros (param-discovery)
3. Matriz de Control de Acceso (auth-matrix-audit / IDOR)
4. Lógica de Negocio & Estados (business-logic-audit / TOCTOU)
5. Client-Side & SPAs (client-side-spa-audit / CORS / postMessage)
6. Seguridad de APIs & Webhooks (api-security-audit / GraphQL)
7. Inyecciones de Servidor & SSRF (ssrf-injection-audit / Callbacks)
8. Triaje Evidence-First & Calidad (triage-gatekeeper)

Sin dependencias externas obligatorias (Python 3 stdlib).
"""

import argparse
import datetime
import json
import os
import pathlib
import re
import subprocess
import sys
from typing import Any, Dict, List, Optional, Set, Tuple

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from seclab_findings import requires_finding_review, finding_status_from_markdown

# Constantes de severidad y metodologías
METHODOLOGY_AREAS = [
    {
        "id": "recon",
        "name": "Reconocimiento & Perfilado",
        "skill": "recon-profiling",
        "cwes": [],
        "keywords": ["recon", "subdomain", "live_hosts", "assets", "surface"],
    },
    {
        "id": "fuzzing",
        "name": "Descubrimiento de Parámetros",
        "skill": "param-discovery",
        "cwes": [],
        "keywords": ["param", "parameter", "hidden", "x8", "fuzzing", "endpoints"],
    },
    {
        "id": "auth",
        "name": "Control de Acceso & Auth Matrix",
        "skill": "auth-matrix-audit",
        "cwes": ["CWE-639", "CWE-284", "CWE-285", "CWE-287", "CWE-306", "CWE-862", "CWE-863"],
        "keywords": ["idor", "bfla", "bola", "jwt", "privilege", "authorization", "auth", "session", "impersonation"],
    },
    {
        "id": "logic",
        "name": "Lógica de Negocio & Estados",
        "skill": "business-logic-audit",
        "cwes": ["CWE-840", "CWE-362", "CWE-799", "CWE-670", "CWE-20"],
        "keywords": ["logic", "race", "toctou", "price", "step", "state", "tampering", "workflow", "concurrency"],
    },
    {
        "id": "client",
        "name": "Client-Side & SPAs",
        "skill": "client-side-spa-audit",
        "cwes": ["CWE-79", "CWE-942", "CWE-345", "CWE-1021"],
        "keywords": ["xss", "cors", "postmessage", "spa", "react", "client-side", "dom", "bundle", "js_files"],
    },
    {
        "id": "api",
        "name": "Seguridad de APIs & Webhooks",
        "skill": "api-security-audit",
        "cwes": ["CWE-915", "CWE-650", "CWE-347"],
        "keywords": ["api", "graphql", "mass-assignment", "hmac", "verb", "rest", "webhook"],
    },
    {
        "id": "injection",
        "name": "Inyecciones de Servidor & SSRF",
        "skill": "ssrf-injection-audit",
        "cwes": ["CWE-89", "CWE-78", "CWE-918", "CWE-1336", "CWE-22", "CWE-94"],
        "keywords": ["sqli", "ssrf", "ssti", "rce", "command", "lfi", "rfi", "injection", "callback"],
    },
    {
        "id": "triage",
        "name": "Triaje Evidence-First & Reporte",
        "skill": "triage-gatekeeper",
        "cwes": [],
        "keywords": ["evidence", "poc", "verified", "confirmed", "triage", "report"],
    },
]

METHODOLOGY_AREA_IDS = {area["id"] for area in METHODOLOGY_AREAS}

# Marcador explicito y reconocible para notes.md: '## Disciplina: <id>'. Señal
# confiable adicional a la heuristica de palabras clave (backlog A18): deja
# que el operador confirme a mano que una disciplina ya se cubrio, incluso
# cuando no arrojo ningun hallazgo que la heuristica pueda emparejar.
DISCIPLINE_MARKER_RE = re.compile(r"^##\s*Disciplina:\s*([A-Za-z_-]+)\s*$", re.IGNORECASE | re.MULTILINE)


def parse_simple_yaml_frontmatter(content: str) -> Tuple[Dict[str, str], str]:
    """Extrae y parsea el frontmatter YAML básico de un archivo markdown."""
    metadata: Dict[str, str] = {}
    body = content

    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            raw_meta = parts[1]
            body = parts[2]
            for line in raw_meta.splitlines():
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
    if target_arg:
        p = pathlib.Path(target_arg).expanduser()
        if p.is_dir():
            return p.resolve()

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
            if candidate_direct.is_dir():
                return candidate_direct.resolve()

    cwd = pathlib.Path.cwd().resolve()
    if (cwd / "target.yaml").is_file() or (cwd / "evidence").is_dir() or (cwd / "scope.txt").is_file() or (cwd / "recon").is_dir():
        return cwd

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

    return None


class AuditChecklistEvaluator:
    """Evalúa la cobertura metodológica y preparación de cierre de un engagement."""

    def __init__(self, engagement_dir: pathlib.Path):
        self.engagement_dir = engagement_dir.resolve()
        self.target_yaml = self.engagement_dir / "target.yaml"
        self.scope_txt = self.engagement_dir / "scope.txt"
        self.recon_dir = self.engagement_dir / "recon"
        self.fuzzing_dir = self.engagement_dir / "fuzzing"
        self.evidence_dir = self.engagement_dir / "evidence"
        self.report_file = self.engagement_dir / "REPORT.md"
        self.terminal_log = self.engagement_dir / "terminal.log"
        self.notes_file = self.engagement_dir / "notes.md"

    def collect_evidence_findings(self) -> List[Dict[str, Any]]:
        """Lee y normaliza todos los hallazgos documentados en evidence/*.md."""
        findings = []
        if not self.evidence_dir.is_dir():
            return findings

        for md_file in sorted(self.evidence_dir.glob("*.md")):
            if md_file.name.startswith("_") or md_file.name.startswith(".") or md_file.name.lower() == "readme.md":
                continue
            try:
                content = md_file.read_text(encoding="utf-8")
                meta, body = parse_simple_yaml_frontmatter(content)
                title = meta.get("title", md_file.stem)
                status = finding_status_from_markdown(content)
                cwe = meta.get("cwe", "").strip()
                severity = meta.get("severity", "Medium").strip()

                # Verificar si cuenta con PoC y raw evidence
                has_poc = bool(re.search(r"##\s*2\.\s*Pasos|```bash|curl\s+", body, re.IGNORECASE))
                has_raw = bool(re.search(r"##\s*3\.\s*Petición|HTTP/1\.[01]|HTTP/2", body, re.IGNORECASE))

                findings.append({
                    "file": md_file.name,
                    "path": str(md_file),
                    "id": meta.get("id", md_file.stem),
                    "title": title,
                    "status": status,
                    "severity": severity,
                    "cwe": cwe,
                    "has_poc": has_poc,
                    "has_raw_evidence": has_raw,
                    "body_snippet": body[:500].lower(),
                })
            except Exception:
                pass

        return findings

    def collect_recon_metrics(self) -> Dict[str, Any]:
        """Extrae conteos y estado de artefactos de reconocimiento."""
        metrics = {
            "subdomains": 0,
            "live_hosts": 0,
            "urls": 0,
            "js_files": 0,
            "patterns": {},
            "summary_exists": False,
        }

        if self.recon_dir.is_dir():
            sub_f = self.recon_dir / "subdomains.txt"
            if sub_f.is_file():
                metrics["subdomains"] = len([l for l in sub_f.read_text(encoding="utf-8").splitlines() if l.strip()])

            live_f = self.recon_dir / "live_hosts.txt"
            if live_f.is_file():
                metrics["live_hosts"] = len([l for l in live_f.read_text(encoding="utf-8").splitlines() if l.strip()])

            urls_f = self.recon_dir / "urls_all.txt"
            if urls_f.is_file():
                metrics["urls"] = len([l for l in urls_f.read_text(encoding="utf-8").splitlines() if l.strip()])

            js_f = self.recon_dir / "js_files.txt"
            if js_f.is_file():
                metrics["js_files"] = len([l for l in js_f.read_text(encoding="utf-8").splitlines() if l.strip()])

            pat_dir = self.recon_dir / "patterns"
            if pat_dir.is_dir():
                for p in pat_dir.glob("*.txt"):
                    cnt = len([l for l in p.read_text(encoding="utf-8").splitlines() if l.strip()])
                    if cnt > 0:
                        metrics["patterns"][p.stem] = cnt

            summary_f = self.recon_dir / "summary.json"
            if summary_f.is_file():
                metrics["summary_exists"] = True

        return metrics

    def read_terminal_log_keywords(self) -> Set[str]:
        """Identifica palabras clave e hitos presentes en terminal.log."""
        keywords_found: Set[str] = set()
        if not self.terminal_log.is_file():
            return keywords_found

        try:
            content = self.terminal_log.read_text(encoding="utf-8", errors="ignore")
            # Buscar menciones a tools y comandos
            for word in ["x8", "fuzz", "idor", "bfla", "jwt", "race", "toctou", "cors", "postmessage", "graphql", "api", "ssrf", "callback", "report"]:
                if re.search(r"\b" + re.escape(word) + r"\b", content, re.IGNORECASE):
                    keywords_found.add(word.lower())
        except Exception:
            pass

        return keywords_found

    def read_discipline_markers(self) -> Set[str]:
        """Lee marcadores explícitos '## Disciplina: <id>' en notes.md.

        Señal confiable adicional a la heurística de palabras clave: el
        operador puede confirmar a mano que una disciplina ya se cubrió,
        incluso sin hallazgos que mostrar (p. ej. porque la prueba no
        encontró nada explotable) — algo que la heurística por coincidencia
        de hallazgos nunca puede detectar por sí sola. IDs no reconocidos se
        ignoran en silencio: notes.md es texto libre, no una fuente de
        verdad de alcance o seguridad.
        """
        markers: Set[str] = set()
        if not self.notes_file.is_file():
            return markers
        try:
            content = self.notes_file.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            return markers
        for match in DISCIPLINE_MARKER_RE.finditer(content):
            area_id = match.group(1).strip().lower()
            if area_id in METHODOLOGY_AREA_IDS:
                markers.add(area_id)
        return markers

    def evaluate_area_status(
        self,
        area: Dict[str, Any],
        recon: Dict[str, Any],
        findings: List[Dict[str, Any]],
        log_keywords: Set[str],
        discipline_markers: Set[str],
    ) -> Dict[str, Any]:
        """Evalúa el estado individual de una disciplina metodológica."""
        area_id = area["id"]
        status = "PENDING"
        details = []
        matching_findings = []

        # 1. Evaluar si hay hallazgos asociados
        for f in findings:
            is_match = False
            # Coincidencia por CWE
            if f["cwe"] and any(f["cwe"].upper() == cwe.upper() for cwe in area["cwes"]):
                is_match = True
            # Coincidencia por palabras clave en título/cuerpo
            text_to_search = (f["title"] + " " + f["body_snippet"]).lower()
            if any(re.search(r"\b" + re.escape(kw) + r"\b", text_to_search) for kw in area["keywords"]):
                is_match = True

            if is_match:
                matching_findings.append(f)

        # 2. Marcador explícito del operador (notes.md): señal confiable que
        # prevalece sobre la heurística, incluso sin hallazgos que emparejar.
        explicit_marker = area_id in discipline_markers

        # 3. Lógica específica por área (heurística, se mantiene como respaldo)
        if explicit_marker and (area_id != "triage" or not findings):
            status = "COMPLETED"
            marker_detail = f"Confirmado explícitamente por el operador (marcador '## Disciplina: {area_id}' en notes.md)"
            if matching_findings:
                marker_detail += f"; {len(matching_findings)} hallazgo(s) asociado(s)"
            details.append(marker_detail)
        elif area_id == "recon":
            if recon["live_hosts"] > 0 or (recon["subdomains"] > 0 and recon["urls"] > 0):
                status = "COMPLETED"
                details.append(f"{recon['subdomains']} subdominios, {recon['live_hosts']} hosts vivos, {recon['urls']} URLs")
            elif recon["subdomains"] > 0 or self.target_yaml.is_file() or self.scope_txt.is_file():
                status = "IN_PROGRESS"
                details.append("Alcance definido; reconocimiento parcial iniciado")
            else:
                details.append("Sin datos de reconocimiento registrados")

        elif area_id == "fuzzing":
            has_fuzz_files = self.fuzzing_dir.is_dir() and any(self.fuzzing_dir.glob("*"))
            has_patterns = len(recon["patterns"]) > 0
            if has_fuzz_files or (has_patterns and "x8" in log_keywords):
                status = "COMPLETED"
                details.append(f"Fuzzing ejecutado ({len(recon['patterns'])} patrones clasificados)")
            elif has_patterns or "x8" in log_keywords or "fuzz" in log_keywords:
                status = "IN_PROGRESS"
                details.append("Patrones detectados; análisis de parámetros en curso")
            else:
                details.append("Sin evidencias de descubrimiento de parámetros")

        elif area_id == "client":
            if matching_findings:
                status = "COMPLETED"
                details.append(f"{len(matching_findings)} hallazgo(s) client-side documentados")
            elif recon["js_files"] > 0:
                status = "IN_PROGRESS"
                details.append(f"{recon['js_files']} archivos JS archivados para auditoría")
            elif "cors" in log_keywords or "postmessage" in log_keywords:
                status = "IN_PROGRESS"
                details.append("Actividad client-side registrada en terminal.log")
            else:
                details.append("Sin auditoría client-side iniciada")

        elif area_id == "api":
            if matching_findings:
                status = "COMPLETED"
                details.append(f"{len(matching_findings)} hallazgo(s) de API documentados")
            elif any(kw in log_keywords for kw in ["api", "graphql", "mass-assignment"]):
                status = "IN_PROGRESS"
                details.append("Pruebas de API registradas en log de terminal")
            else:
                details.append("Sin pruebas de seguridad de API registradas")

        elif area_id == "auth":
            if matching_findings:
                status = "COMPLETED"
                details.append(f"{len(matching_findings)} hallazgo(s) de control de acceso/IDOR")
            elif any(kw in log_keywords for kw in ["idor", "bfla", "jwt", "auth"]):
                status = "IN_PROGRESS"
                details.append("Pruebas de matriz de autorización en curso")
            else:
                details.append("Sin evaluación de control de acceso registrada")

        elif area_id == "logic":
            if matching_findings:
                status = "COMPLETED"
                details.append(f"{len(matching_findings)} hallazgo(s) de lógica de negocio")
            elif any(kw in log_keywords for kw in ["race", "toctou", "logic"]):
                status = "IN_PROGRESS"
                details.append("Pruebas de lógica y condiciones de carrera en curso")
            else:
                details.append("Sin pruebas de lógica de negocio registradas")

        elif area_id == "injection":
            if matching_findings:
                status = "COMPLETED"
                details.append(f"{len(matching_findings)} hallazgo(s) de inyección/SSRF")
            elif any(p in recon["patterns"] for p in ["ssrf", "sqli", "rce", "lfi"]):
                status = "IN_PROGRESS"
                details.append("Parámetros de inyección identificados en reconocimiento")
            elif "callback" in log_keywords:
                status = "IN_PROGRESS"
                details.append("Receptor pt-callback utilizado en auditoría")
            else:
                details.append("Sin hallazgos ni pruebas de inyección registradas")

        elif area_id == "triage":
            if findings:
                unverified = [f for f in findings if requires_finding_review(f["status"])]
                if not unverified and self.report_file.is_file():
                    status = "COMPLETED"
                    details.append(f"Triaje resuelto para {len(findings)} ficha(s) y REPORT.md generado")
                elif not unverified:
                    status = "IN_PROGRESS"
                    details.append(f"Triaje resuelto para {len(findings)} ficha(s); falta compilar REPORT.md")
                else:
                    status = "IN_PROGRESS"
                    details.append(f"{len(unverified)} hallazgo(s) pendientes de verificación formal")
            else:
                details.append("Sin hallazgos cargados para triaje")

        return {
            "id": area_id,
            "name": area["name"],
            "skill": area["skill"],
            "status": status,
            "findings_count": len(matching_findings),
            "findings": [f["id"] for f in matching_findings],
            "details": "; ".join(details),
        }

    def evaluate(self) -> Dict[str, Any]:
        """Ejecuta la evaluación completa de cobertura y checklist."""
        recon = self.collect_recon_metrics()
        findings = self.collect_evidence_findings()
        log_keywords = self.read_terminal_log_keywords()
        discipline_markers = self.read_discipline_markers()

        matrix = []
        completed_count = 0
        in_progress_count = 0

        for area in METHODOLOGY_AREAS:
            res = self.evaluate_area_status(area, recon, findings, log_keywords, discipline_markers)
            matrix.append(res)
            if res["status"] == "COMPLETED":
                completed_count += 1
            elif res["status"] == "IN_PROGRESS":
                in_progress_count += 1

        total_areas = len(METHODOLOGY_AREAS)
        # Score ponderado: COMPLETED = 1.0, IN_PROGRESS = 0.5
        score_points = completed_count * 1.0 + in_progress_count * 0.5
        coverage_percent = round((score_points / total_areas) * 100, 1)

        # Preparación para el cierre (Readiness for Closure)
        blocking_issues = []
        recommendations = []

        if not self.target_yaml.is_file() and not self.scope_txt.is_file():
            blocking_issues.append("No se encontró target.yaml ni scope.txt")

        unverified_findings = [f["id"] for f in findings if requires_finding_review(f["status"])]
        if unverified_findings:
            blocking_issues.append(f"Existen hallazgos sin verificar formalmente: {', '.join(unverified_findings)}")

        if not self.report_file.is_file() and len(findings) > 0:
            blocking_issues.append("El informe final REPORT.md no ha sido compilado (ejecute: pt-report build)")

        if recon["live_hosts"] == 0 and recon["subdomains"] == 0:
            recommendations.append("Ejecutar el pipeline de reconocimiento (pt-recon) para registrar superficie de ataque")

        if coverage_percent < 50.0:
            recommendations.append(f"La cobertura metodológica es baja ({coverage_percent}%); audite más disciplinas antes del cierre")

        ready_for_close = len(blocking_issues) == 0

        # Metadatos del engagement
        status_raw = "active"
        if self.target_yaml.is_file():
            try:
                for line in self.target_yaml.read_text(encoding="utf-8").splitlines():
                    if "status:" in line:
                        status_raw = line.split(":", 1)[1].strip().strip("'\"")
                        break
            except Exception:
                pass

        return {
            "engagement": self.engagement_dir.name,
            "engagement_path": str(self.engagement_dir),
            "engagement_status": status_raw,
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "coverage_score": coverage_percent,
            "completed_areas": completed_count,
            "in_progress_areas": in_progress_count,
            "total_areas": total_areas,
            "total_findings": len(findings),
            "findings_summary": {
                "verified": len([f for f in findings if f["status"] == "PROVEN"]),
                "unverified": len(unverified_findings),
                "disproved": sum(f["status"] == "DISPROVED" for f in findings),
                "mitigated": sum(f["status"] == "MITIGATED" for f in findings),
            },
            "matrix": matrix,
            "readiness": {
                "ready_for_closure": ready_for_close,
                "blocking_issues": blocking_issues,
                "recommendations": recommendations,
            },
        }


def format_terminal_output(eval_data: Dict[str, Any]) -> str:
    """Genera la vista interactiva con formato visual para la terminal."""
    use_color = sys.stdout.isatty() and not os.environ.get("NO_COLOR")

    C_RESET = "\033[0m" if use_color else ""
    C_BOLD = "\033[1m" if use_color else ""
    C_GREEN = "\033[32m" if use_color else ""
    C_YELLOW = "\033[33m" if use_color else ""
    C_RED = "\033[31m" if use_color else ""
    C_CYAN = "\033[36m" if use_color else ""

    lines = []
    lines.append(f"\n{C_BOLD}SECLAB-SBF Checklist Metodológico & Cobertura de Auditoría{C_RESET}")
    lines.append(f"Engagement: {C_CYAN}{eval_data['engagement']}{C_RESET} ({eval_data['engagement_status'].upper()})")
    lines.append(f"Directorio: {eval_data['engagement_path']}")

    score = eval_data["coverage_score"]
    score_color = C_GREEN if score >= 75 else (C_YELLOW if score >= 40 else C_RED)
    lines.append(f"Cobertura Metodológica: {score_color}{score}%{C_RESET} ({eval_data['completed_areas']}/{eval_data['total_areas']} disciplinas completadas)")
    lines.append(f"Total Hallazgos: {eval_data['total_findings']} ({eval_data['findings_summary']['verified']} verificados, {eval_data['findings_summary']['unverified']} borradores)\n")

    lines.append(f"{'#':<3} {'Disciplina Metodológica':<32} {'Estado':<14} {'Hallazgos':<11} {'Detalles'}")
    lines.append("-" * 95)

    for idx, row in enumerate(eval_data["matrix"], 1):
        st = row["status"]
        if st == "COMPLETED":
            st_fmt = f"{C_GREEN}[✓] COMPLETO{C_RESET}"
        elif st == "IN_PROGRESS":
            st_fmt = f"{C_YELLOW}[~] EN CURSO{C_RESET}"
        else:
            st_fmt = f"{C_RED}[ ] PENDIENTE{C_RESET}"

        f_cnt = str(row["findings_count"]) if row["findings_count"] > 0 else "-"
        lines.append(f"{idx:<3} {row['name']:<32} {st_fmt:<23} {f_cnt:<11} {row['details']}")

    lines.append("-" * 95)

    # Estado de Preparación de Cierre
    ready = eval_data["readiness"]["ready_for_closure"]
    ready_fmt = f"{C_GREEN}LISTO PARA CIERRE (pt-eng close){C_RESET}" if ready else f"{C_RED}BLOQUEADO PARA CIERRE{C_RESET}"
    lines.append(f"\nPreparación de Cierre: {ready_fmt}")

    if eval_data["readiness"]["blocking_issues"]:
        lines.append(f"{C_RED}Bloqueos pendientes:{C_RESET}")
        for b in eval_data["readiness"]["blocking_issues"]:
            lines.append(f"  ✖ {b}")

    if eval_data["readiness"]["recommendations"]:
        lines.append(f"{C_YELLOW}Recomendaciones:{C_RESET}")
        for r in eval_data["readiness"]["recommendations"]:
            lines.append(f"  ⚡ {r}")

    lines.append("")
    return "\n".join(lines)


def format_markdown_output(eval_data: Dict[str, Any]) -> str:
    """Genera informe en Markdown para exportación o anexo a REPORT.md."""
    lines = [
        f"## Matriz de Cobertura Metodológica ({eval_data['coverage_score']}%)",
        "",
        f"**Engagement:** `{eval_data['engagement']}` | **Fecha:** `{eval_data['timestamp']}`  ",
        f"**Estado:** `{eval_data['engagement_status']}` | **Disciplinas Completadas:** `{eval_data['completed_areas']}/{eval_data['total_areas']}`",
        "",
        "| # | Disciplina Metodológica | Habilidad Asociada | Estado | Hallazgos | Evidencia y Observaciones |",
        "|---|---|---|---|---|---|",
    ]

    for idx, row in enumerate(eval_data["matrix"], 1):
        st_icon = "✅ Completo" if row["status"] == "COMPLETED" else ("🟡 En Curso" if row["status"] == "IN_PROGRESS" else "⚪ Pendiente")
        lines.append(
            f"| {idx} | {row['name']} | `{row['skill']}` | {st_icon} | {row['findings_count']} | {row['details']} |"
        )

    lines.append("")
    lines.append("### Estado de Preparación de Cierre")
    if eval_data["readiness"]["ready_for_closure"]:
        lines.append("Auditoría lista para cierre formal (`pt-eng close`) y empaquetado seguro.")
    else:
        lines.append("Existen bloqueos pendientes antes del cierre:")
        for b in eval_data["readiness"]["blocking_issues"]:
            lines.append(f"- **Bloqueo:** {b}")

    lines.append("")
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    """Construye el parser CLI para pt-audit-checklist."""
    parser = argparse.ArgumentParser(
        prog="pt-audit-checklist",
        description="Evaluador de Cobertura y Checklist Metodológico de Auditoría para SecLab-SBF.",
    )
    parser.add_argument("target", nargs="?", default=None, help="Nombre del engagement o directorio de trabajo.")
    parser.add_argument("-j", "--json", action="store_true", help="Salida en formato JSON estructurado.")
    parser.add_argument("-m", "--markdown", action="store_true", help="Salida en formato Markdown.")
    parser.add_argument("--strict", action="store_true", help="Falla (exit code 1) si hay bloqueos de cierre o cobertura < 50%%.")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    eng_dir = resolve_engagement_dir(args.target)
    if not eng_dir:
        sys.stderr.write(f"Error: No se pudo localizar el directorio del engagement: {args.target or 'actual'}\n")
        return 1

    evaluator = AuditChecklistEvaluator(eng_dir)
    res = evaluator.evaluate()

    if args.json:
        print(json.dumps(res, indent=2, ensure_ascii=False))
    elif args.markdown:
        print(format_markdown_output(res))
    else:
        print(format_terminal_output(res))

    if args.strict:
        if not res["readiness"]["ready_for_closure"] or res["coverage_score"] < 50.0:
            return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
