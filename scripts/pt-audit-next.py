#!/usr/bin/env python3
"""Recomendador de Próximo Paso Metodológico y Guía de Auditoría para SecLab-SBF (pt-next).

Analiza el estado integral de un engagement o reto (/workspace/engagements/<id>),
inspeccionando la cobertura actual de las 8 disciplinas metodológicas, los hallazgos
validados y el checklist de preparación para el cierre, y recomienda de forma determinista
la siguiente acción táctica prioritaria para el operador o agente autónomo de IA.

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

# Colores ANSI respetando NO_COLOR y TERM=dumb
NO_COLOR = bool(os.environ.get("NO_COLOR")) or os.environ.get("TERM") == "dumb"
C_RESET = "" if NO_COLOR else "\033[0m"
C_BOLD = "" if NO_COLOR else "\033[1m"
C_RED = "" if NO_COLOR else "\033[31m"
C_GREEN = "" if NO_COLOR else "\033[32m"
C_YELLOW = "" if NO_COLOR else "\033[33m"
C_BLUE = "" if NO_COLOR else "\033[34m"
C_CYAN = "" if NO_COLOR else "\033[36m"


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
                ["tmux", "show-option", "-pv", "@seclab_log_eng"],
                capture_output=True,
                text=True,
                check=False,
            )
            eng_name = res.stdout.strip()
            if eng_name:
                is_reto = eng_name.startswith("reto:")
                clean_name = eng_name.replace("reto:", "")
                sub_folder = "retos" if is_reto else "engagements"

                ws_env = os.environ.get("WORKSPACE_DIR")
                ws_candidates = [pathlib.Path(ws_env)] if ws_env else []
                ws_candidates.extend([
                    pathlib.Path("/workspace"),
                    pathlib.Path("./workspace"),
                    pathlib.Path("."),
                ])
                for ws in ws_candidates:
                    p = ws / sub_folder / clean_name
                    if p.is_dir():
                        return p.resolve()
        except Exception:
            pass

    return None


def determine_roadmap(engagement_dir: pathlib.Path) -> List[Dict[str, Any]]:
    """Analiza exhaustivamente el engagement y genera una lista ordenada de pasos pendientes."""
    mod = _get_audit_checklist_module()
    if mod and hasattr(mod, "AuditChecklistEvaluator"):
        try:
            eval_data = mod.AuditChecklistEvaluator(engagement_dir).evaluate()
        except Exception:
            eval_data = {}
    else:
        eval_data = {}

    eng_name = engagement_dir.name
    target_yaml = engagement_dir / "target.yaml"
    scope_txt = engagement_dir / "scope.txt"
    report_file = engagement_dir / "REPORT.md"
    ev_dir = engagement_dir / "evidence"

    # Verificar si target.yaml está cerrado
    is_closed = False
    if target_yaml.is_file():
        try:
            content = target_yaml.read_text(encoding="utf-8")
            for line in content.splitlines():
                if line.strip().startswith("status:") and "closed" in line.lower():
                    is_closed = True
                    break
        except Exception:
            pass

    if is_closed:
        return [{
            "id": "closed",
            "phase": "Auditoría Cerrada",
            "title": "Engagement Cerrado Formalmente",
            "discipline": "N/A",
            "skill": "N/A",
            "prompt_template": "report-agent",
            "priority": "INFO",
            "reason": "El engagement ya cuenta con status: closed en target.yaml.",
            "command": f"pt-eng export {eng_name} /workspace/exports",
            "ready_for_closure": True,
        }]

    steps: List[Dict[str, Any]] = []

    # 1. Scope / Alcance
    has_scope = False
    try:
        from seclab_scope import load_scope_rules
        scope_data = load_scope_rules(engagement_dir)
        has_scope = any(scope_data['scope'].get('in_scope', {}).get(key) for key in ('domains', 'ips', 'cidrs', 'endpoints'))
    except (ValueError, OSError, ImportError):
        has_scope = False
    if not has_scope:
        steps.append({
            "id": "scope",
            "phase": "1. Gobierno & Alcance",
            "title": "Definir Objetivos In-Scope y Exclusiones",
            "discipline": "recon",
            "skill": "duplicate-scope-guard",
            "prompt_template": "recon-agent",
            "priority": "HIGH",
            "reason": "No hay alcance autorizado válido en target.yaml o scope.txt; define y revisa los objetivos antes de probarlos.",
            "command": "pt-scope show  # Revisar y editar el alcance del proyecto existente",
            "ready_for_closure": False,
        })

    if has_scope:
        try:
            from seclab_scope import require_authorization
            require_authorization(scope_data, 'passive')
            require_authorization(scope_data, 'active')
        except (ValueError, OSError) as error:
            steps.append({
                "id": "authorization",
                "phase": "1. Gobierno & Alcance",
                "title": "Revisar autorización y vigencia del reconocimiento",
                "discipline": "recon",
                "skill": "duplicate-scope-guard",
                "prompt_template": "recon-agent",
                "priority": "HIGH",
                "reason": str(error),
                "command": "pt-recon --dry-run  # Simular; configura los permisos en Alcance antes de enviar tráfico",
                "ready_for_closure": False,
            })

    # Extraer métricas de la evaluación del checklist
    matrix_map: Dict[str, Dict[str, Any]] = {}
    if eval_data and "matrix" in eval_data:
        for row in eval_data["matrix"]:
            matrix_map[row["id"]] = row

    # 2. Reconocimiento
    recon_status = matrix_map.get("recon", {}).get("status", "PENDING")
    if recon_status != "COMPLETED":
        steps.append({
            "id": "recon",
            "phase": "2. Reconocimiento & Perfilado",
            "title": "Mapeo de Activos, Subdominios y Hosts Vivos",
            "discipline": "recon",
            "skill": "recon-profiling",
            "prompt_template": "recon-agent",
            "priority": "HIGH",
            "reason": "Superficie de ataque sin mapear o datos incompletos en recon/ (subdomains.txt, live_hosts.txt).",
            "command": f"pt-recon",
            "ready_for_closure": False,
        })

    # 3. Descubrimiento de Parámetros (Fuzzing)
    fuzz_status = matrix_map.get("fuzzing", {}).get("status", "PENDING")
    if fuzz_status != "COMPLETED":
        steps.append({
            "id": "fuzzing",
            "phase": "3. Descubrimiento de Parámetros",
            "title": "Fuzzing Heurístico de Parámetros con x8",
            "discipline": "fuzzing",
            "skill": "param-discovery",
            "prompt_template": "recon-agent",
            "priority": "HIGH",
            "reason": "Parámetros HTTP ocultos o no documentados sin explorar en endpoints vivos.",
            "command": f"pt-fuzz-params <url_objetivo>",
            "ready_for_closure": False,
        })

    # 4. Control de Acceso & Auth Matrix (IDOR / BFLA)
    auth_status = matrix_map.get("auth", {}).get("status", "PENDING")
    if auth_status != "COMPLETED":
        steps.append({
            "id": "auth",
            "phase": "4. Control de Acceso & Auth Matrix",
            "title": "Auditoría de Matriz de Autorización, IDOR y JWT",
            "discipline": "auth",
            "skill": "auth-matrix-audit",
            "prompt_template": "auth-agent",
            "priority": "HIGH",
            "reason": "No se han documentado pruebas cruzadas entre roles (BFLA) o intercambio de identificadores (IDOR).",
            "command": f"pt-context {eng_name} auth",
            "ready_for_closure": False,
        })

    # 5. Seguridad de APIs & Webhooks
    api_status = matrix_map.get("api", {}).get("status", "PENDING")
    if api_status != "COMPLETED":
        steps.append({
            "id": "api",
            "phase": "5. Seguridad de APIs & Webhooks",
            "title": "Auditoría de APIs REST/GraphQL y Asignación Masiva",
            "discipline": "api",
            "skill": "api-security-audit",
            "prompt_template": "auth-agent",
            "priority": "MEDIUM",
            "reason": "Endpoints API sin validación de verbos HTTP, esquemas GraphQL o manipulación de parámetros JSON.",
            "command": f"pt-context {eng_name} api",
            "ready_for_closure": False,
        })

    # 6. Lógica de Negocio & Estados
    logic_status = matrix_map.get("logic", {}).get("status", "PENDING")
    if logic_status != "COMPLETED":
        steps.append({
            "id": "logic",
            "phase": "6. Lógica de Negocio & Estados",
            "title": "Auditoría de Flujos, Salto de Pasos y Carreras (TOCTOU)",
            "discipline": "logic",
            "skill": "business-logic-audit",
            "prompt_template": "logic-agent",
            "priority": "MEDIUM",
            "reason": "Flujos transaccionales o estados de sesión sin pruebas de condiciones de carrera o alteración de pasos.",
            "command": f"pt-context {eng_name} logic",
            "ready_for_closure": False,
        })

    # 7. Client-Side & SPAs
    client_status = matrix_map.get("client", {}).get("status", "PENDING")
    if client_status != "COMPLETED":
        steps.append({
            "id": "client",
            "phase": "7. Client-Side & SPAs",
            "title": "Análisis de Bundles JS, CORS Permisivo y postMessage",
            "discipline": "client",
            "skill": "client-side-spa-audit",
            "prompt_template": "recon-agent",
            "priority": "MEDIUM",
            "reason": "Archivos JavaScript descargados sin análisis de secretos o configuraciones de CORS con credenciales.",
            "command": f"pt-context {eng_name} spa",
            "ready_for_closure": False,
        })

    # 8. Inyecciones de Servidor & SSRF (OOB)
    inj_status = matrix_map.get("injection", {}).get("status", "PENDING")
    if inj_status != "COMPLETED":
        steps.append({
            "id": "injection",
            "phase": "8. Inyecciones de Servidor & SSRF",
            "title": "Pruebas de Inyecciones Críticas y Callbacks Fuera de Banda (OOB)",
            "discipline": "injection",
            "skill": "ssrf-injection-audit",
            "prompt_template": "injection-agent",
            "priority": "MEDIUM",
            "reason": "Parámetros susceptibles a inyección sin evaluación con receptor OOB pt-callback.",
            "command": f"pt-callback start && pt-context {eng_name} injection",
            "ready_for_closure": False,
        })

    # 9. Hallazgos en borrador sin verificar
    unverified_findings = []
    if ev_dir.is_dir():
        for f in sorted(ev_dir.glob("*.md")):
            if f.name.startswith("_") or f.name.lower() == "readme.md":
                continue
            try:
                txt = f.read_text(encoding="utf-8")
                if "status: borrador" in txt.lower() or "status: unverified" in txt.lower() or "status: draft" in txt.lower():
                    unverified_findings.append(f.name)
            except Exception:
                pass

    if unverified_findings:
        steps.append({
            "id": "verify_findings",
            "phase": "9. Triaje Evidence-First",
            "title": "Verificación Formal de Hallazgos en Borrador",
            "discipline": "triage",
            "skill": "triage-gatekeeper",
            "prompt_template": "triage-agent",
            "priority": "CRITICAL",
            "reason": f"Existen {len(unverified_findings)} hallazgo(s) en borrador ({', '.join(unverified_findings[:3])}) que requieren PoC reproducible y petición/respuesta crudas.",
            "command": f"pt-finding check",
            "ready_for_closure": False,
        })

    # 10. Compilación de REPORT.md
    findings_count = 0
    if ev_dir.is_dir():
        findings_count = len([f for f in ev_dir.glob("*.md") if not f.name.startswith("_") and f.name.lower() != "readme.md"])

    if not report_file.is_file() and findings_count > 0:
        steps.append({
            "id": "report_build",
            "phase": "10. Compilación de Reporte",
            "title": "Compilar Informe Final Consolidado (REPORT.md)",
            "discipline": "report",
            "skill": "report-generation",
            "prompt_template": "report-agent",
            "priority": "HIGH",
            "reason": f"Hay {findings_count} hallazgo(s) registrados pero el informe final REPORT.md aún no ha sido generado.",
            "command": f"pt-report build",
            "ready_for_closure": False,
        })

    # 11. Empaquetado y Cierre si todo lo demás está listo
    readiness = eval_data.get("readiness", {})
    ready_for_closure = readiness.get("ready_for_closure", False)

    if not steps or ready_for_closure:
        steps.append({
            "id": "pack_and_close",
            "phase": "11. Empaquetado y Cierre",
            "title": "Generar Entrega Sanitizada y Sellar Engagement",
            "discipline": "closure",
            "skill": "report-generation",
            "prompt_template": "report-agent",
            "priority": "HIGH",
            "reason": "Todos los requisitos de calidad y evidencia se encuentran satisfechos. La auditoría está lista para ser sellada.",
            "command": f"pt-eng pack --sanitize && pt-eng close {eng_name}",
            "ready_for_closure": True,
        })

    return steps


def generate_llm_prompt(engagement_dir: pathlib.Path, step: Dict[str, Any]) -> str:
    """Genera un System Prompt + Contexto especializado listo para alimentar a un Agente LLM."""
    eng_name = engagement_dir.name
    skill_name = step.get("skill", "recon-profiling")
    prompt_name = step.get("prompt_template", "recon-agent")

    # Intentar cargar plantilla de prompt si existe
    system_prompt_text = ""
    candidate_roots = [
        pathlib.Path("./skills/prompts"),
        pathlib.Path("./workspace-seed/templates/prompts"),
        pathlib.Path("/workspace/templates/prompts"),
        pathlib.Path(__file__).resolve().parent.parent / "skills" / "prompts",
        pathlib.Path(__file__).resolve().parent.parent / "workspace-seed" / "templates" / "prompts",
    ]
    prompt_filename = f"{prompt_name}.prompt.md" if not prompt_name.endswith(".md") else prompt_name
    for r in candidate_roots:
        p_path = r / prompt_filename
        if p_path.is_file():
            try:
                system_prompt_text = p_path.read_text(encoding="utf-8").strip()
                break
            except Exception:
                pass

    if not system_prompt_text:
        system_prompt_text = f"Eres un Agente Especialista en Ciberseguridad Ofensiva operando dentro de SecLab-SBF para la disciplina `{step['discipline']}`."

    prompt_lines = [
        f"<!-- SYSTEM PROMPT ({step['prompt_template']}) -->",
        system_prompt_text,
        "",
        "---",
        "",
        f"<!-- MISSION DIRECTIVE: {eng_name} | {step['title']} -->",
        f"# Misión Táctica: {step['title']}",
        f"- **Engagement Objetivo:** `{eng_name}` (`{engagement_dir}`)",
        f"- **Fase Metodológica:** {step['phase']}",
        f"- **Habilidad Especializada:** `{skill_name}`",
        f"- **Diagnóstico de Necesidad:** {step['reason']}",
        "",
        "## Instrucciones Operativas Inmediatas",
        f"1. Inspecciona el alcance autorizado ejecutando: `pt-scope show`",
        f"2. Ejecuta la acción recomendada: `{step['command']}`",
        "3. Aplica la compuerta Evidence-First: todo hallazgo debe documentarse con PoC reproducible y petición/respuesta cruda.",
        f"4. Registra cada vector confirmado en la bitácora con: `pt-log mark \"{step['id'].upper()}: <detalle_tecnico>\"`",
        "5. Al concluir, verifica la nueva cobertura con: `pt-checklist`",
        "",
        "Inicia el razonamiento y ejecuta el primer paso en el contenedor.",
    ]

    return "\n".join(prompt_lines)


def format_terminal_output(engagement_dir: pathlib.Path, next_step: Dict[str, Any], all_steps: List[Dict[str, Any]], show_all: bool = False) -> str:
    """Formatea la recomendación con visualización limpia en consola."""
    eng_name = engagement_dir.name
    lines = [
        f"{C_BOLD}{C_CYAN}=== SecLab-SBF: Recomendador de Próximo Paso Metodológico (pt-next) ==={C_RESET}",
        f"Engagement activo: {C_BOLD}{eng_name}{C_RESET} ({engagement_dir})",
        "",
    ]

    if show_all:
        lines.append(f"{C_BOLD}Hoja de Ruta Metodológica Completa ({len(all_steps)} pasos restantes):{C_RESET}")
        lines.append("-" * 80)
        for idx, s in enumerate(all_steps, 1):
            is_current = (s["id"] == next_step["id"])
            marker = f"{C_GREEN}▶{C_RESET}" if is_current else " "
            prio_color = C_RED if s["priority"] == "CRITICAL" else (C_YELLOW if s["priority"] == "HIGH" else C_BLUE)
            lines.append(f"{marker} [{idx}] {prio_color}[{s['priority']}]{C_RESET} {C_BOLD}{s['title']}{C_RESET}")
            lines.append(f"     Fase: {s['phase']} | Skill: `{s['skill']}`")
            lines.append(f"     Comando: {C_CYAN}{s['command']}{C_RESET}")
        lines.append("-" * 80)
        lines.append("")

    lines.extend([
        f"{C_BOLD}Próximo Paso Recomendado:{C_RESET}",
        f"  {C_GREEN}●{C_RESET} {C_BOLD}{next_step['title']}{C_RESET} ({next_step['phase']})",
        f"  {C_YELLOW}Motivo:{C_RESET} {next_step['reason']}",
        f"  {C_BLUE}Habilidad / Prompt:{C_RESET} `{next_step['skill']}` ({next_step['prompt_template']})",
        f"  {C_CYAN}Comando Sugerido:{C_RESET} {C_BOLD}{next_step['command']}{C_RESET}",
        "",
    ])

    if next_step.get("ready_for_closure"):
        lines.append(f"{C_GREEN}[✓] ¡Auditoría lista para cierre! Ejecuta el comando sugerido para sellar.{C_RESET}\n")
    else:
        lines.append(f"Tip: Para obtener el prompt completo listo para LLM ejecuta: {C_CYAN}pt-next --prompt{C_RESET}\n")

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Recomendador de Próximo Paso Metodológico y Guía de Auditoría de SecLab-SBF (pt-next).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Ejemplos:
  pt-next                          # Recomienda el siguiente paso táctico para el engagement activo
  pt-next acme-corp                # Recomienda el siguiente paso para acme-corp
  pt-next --prompt                 # Genera un System Prompt + Contexto listo para LLM / subagentes
  pt-next --all                    # Muestra la hoja de ruta completa de pasos pendientes
  pt-next --json                   # Salida en JSON para automatizaciones
""",
    )
    parser.add_argument("engagement", nargs="?", help="Nombre o ruta del engagement a auditar.")
    parser.add_argument("-p", "--prompt", action="store_true", help="Generar un prompt formateado para LLM / Agentes.")
    parser.add_argument("-a", "--all", action="store_true", help="Mostrar la hoja de ruta completa de pasos pendientes.")
    parser.add_argument("-j", "--json", action="store_true", help="Emitir salida estructurada en formato JSON.")
    parser.add_argument("-c", "--copy", action="store_true", help="Copiar la recomendación o prompt al portapapeles.")

    args = parser.parse_args()

    eng_dir = resolve_engagement_dir(args.engagement)
    if not eng_dir or not eng_dir.is_dir():
        print(
            f"Error: No se pudo localizar el directorio del engagement ({args.engagement or 'no especificado'}).\n"
            f"Asegúrate de estar dentro de un engagement o especifícalo: pt-next <engagement>",
            file=sys.stderr,
        )
        return 1

    all_steps = determine_roadmap(eng_dir)
    if not all_steps:
        print(f"Error: No se pudieron determinar pasos para {eng_dir.name}", file=sys.stderr)
        return 1

    next_step = all_steps[0]

    if args.json:
        out_dict = {
            "engagement": eng_dir.name,
            "directory": str(eng_dir),
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "next_step": next_step,
            "total_pending_steps": len(all_steps),
            "roadmap": all_steps if args.all else None,
        }
        if args.prompt:
            out_dict["prompt"] = generate_llm_prompt(eng_dir, next_step)
        output_text = json.dumps(out_dict, indent=2, ensure_ascii=False)
    elif args.prompt:
        output_text = generate_llm_prompt(eng_dir, next_step)
    else:
        output_text = format_terminal_output(eng_dir, next_step, all_steps, show_all=args.all)

    print(output_text)

    if args.copy:
        copied = False
        text_to_copy = generate_llm_prompt(eng_dir, next_step) if args.prompt else next_step["command"]
        for cmd in (["pbcopy"], ["xclip", "-selection", "clipboard"], ["xsel", "--clipboard", "--input"]):
            try:
                proc = subprocess.run(cmd, input=text_to_copy, text=True, check=False)
                if proc.returncode == 0:
                    copied = True
                    break
            except FileNotFoundError:
                continue
        if copied:
            target_desc = "Prompt completo" if args.prompt else f"Comando '{next_step['command']}'"
            print(f"[+] {target_desc} copiado al portapapeles del sistema.", file=sys.stderr)
        else:
            print("[!] No se encontró pbcopy ni xclip para copiar al portapapeles.", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
