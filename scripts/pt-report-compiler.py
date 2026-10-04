#!/usr/bin/env python3
"""Compilador y Linter de Informes y Hallazgos de Seguridad para SecLab-SBF.

Lee especificaciones de alcance (target.yaml), fichas estructuradas de evidencia
(evidence/*.md) y bitacoras de auditoria (terminal.log) para compilar reportes
consolidados profesionales de pentest y bug bounty.

Sin dependencias externas obligatorias (Python 3 stdlib).
"""

import datetime
import importlib.util
import os
import pathlib
import re
import sys
from typing import Any, Dict, List, Optional, Tuple

SEVERITY_ORDER = {
    "CRITICAL": 5,
    "HIGH": 4,
    "MEDIUM": 3,
    "LOW": 2,
    "INFO": 1,
}

SEVERITY_COLORS = {
    "CRITICAL": "\033[1;35m", # Magenta / Bold Red
    "HIGH": "\033[1;31m",     # Red
    "MEDIUM": "\033[1;33m",   # Yellow
    "LOW": "\033[1;34m",      # Blue
    "INFO": "\033[1;36m",     # Cyan
    "RESET": "\033[0m",
}


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
                    # Manejo de comentarios inline
                    if " #" in val:
                        val = val.split(" #")[0].strip().strip("'\"")
                    metadata[key] = val

    return metadata, body


def parse_evidence_file(file_path: pathlib.Path) -> Dict[str, Any]:
    """Lee y estructura un archivo de evidencia markdown."""
    content = file_path.read_text(encoding="utf-8")
    meta, body = parse_frontmatter(content)

    # Valores por defecto derivados del contenido o del nombre de archivo
    stem_id = file_path.stem.upper()
    finding_id = meta.get("id", stem_id)
    title = meta.get("title", "")
    if not title:
        # Intentar extraer del primer encabezado #
        header_match = re.search(r"^#\s+(?:\[.*?\]\s*)?(.+)$", body, re.MULTILINE)
        if header_match:
            title = header_match.group(1).strip()
        else:
            title = file_path.stem.replace("-", " ").title()

    severity = str(meta.get("severity", "Medium")).strip().upper()
    if severity not in SEVERITY_ORDER:
        severity = "MEDIUM"

    cvss_score = 0.0
    if "cvss_score" in meta:
        try:
            cvss_score = float(meta["cvss_score"])
        except ValueError:
            cvss_score = 0.0

    return {
        "file": file_path.name,
        "path": file_path,
        "id": finding_id,
        "title": title,
        "severity": severity,
        "cvss_v31": meta.get("cvss_v31", ""),
        "cvss_score": cvss_score,
        "cwe": meta.get("cwe", "CWE-Unknown"),
        "asset": meta.get("asset", "N/A"),
        "status": meta.get("status", "Confirmado"),
        "auditor": meta.get("auditor", "tester"),
        "date": meta.get("date", datetime.date.today().isoformat()),
        "audit_log": meta.get("audit_log", "terminal.log"),
        "body": body.strip(),
        "has_poc": "```bash" in body or "curl " in body or "## 2. Pasos" in body,
        "has_remediation": "## 5. Remediaci" in body or "## Remediaci" in body,
    }


def get_findings(evidence_dir: pathlib.Path) -> List[Dict[str, Any]]:
    """Carga y ordena todos los hallazgos en el directorio de evidencia."""
    if not evidence_dir.is_dir():
        return []

    findings = []
    for f in sorted(evidence_dir.glob("*.md")):
        if f.name.startswith("_") or f.name.lower() == "readme.md":
            continue
        try:
            findings.append(parse_evidence_file(f))
        except Exception as e:
            print(f"[!] Advertencia: No se pudo parsear {f}: {e}", file=sys.stderr)

    # Ordenar por severidad descendente y luego por CVSS score
    findings.sort(
        key=lambda x: (SEVERITY_ORDER.get(x["severity"], 0), x["cvss_score"]),
        reverse=True,
    )
    return findings


def load_scope_validator():
    """Carga dinamicamente scripts/pt-scope-validator.py si existe."""
    script_path = pathlib.Path(__file__).resolve().parent / "pt-scope-validator.py"
    if not script_path.is_file():
        script_path = pathlib.Path("/usr/local/bin/pt-scope-validator")
    if script_path.is_file():
        spec = importlib.util.spec_from_file_location("pt_scope_validator", script_path)
        if spec and spec.loader:
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            return mod
    return None


def check_findings(engagement_dir: pathlib.Path) -> Tuple[bool, List[str]]:
    """Verifica la validez y disciplina evidence-first de los hallazgos."""
    evidence_dir = engagement_dir / "evidence"
    if not evidence_dir.is_dir():
        return False, [f"El directorio de evidencia no existe: {evidence_dir}"]

    findings = get_findings(evidence_dir)
    if not findings:
        return True, ["No se encontraron fichas de evidencia (.md) en el directorio."]

    issues: List[str] = []
    scope_val = load_scope_validator()
    target_yaml = engagement_dir / "target.yaml"
    scope_data = None
    if scope_val and target_yaml.is_file():
        try:
            scope_data = scope_val.load_target_yaml(target_yaml)
        except Exception:
            pass

    for f in findings:
        prefix = f"[{f['file']}]"
        if not f["title"]:
            issues.append(f"{prefix} Falta el título de la vulnerabilidad.")
        if f["severity"] not in SEVERITY_ORDER:
            issues.append(f"{prefix} Severidad inválida '{f['severity']}'. Debe ser Critical, High, Medium, Low o Info.")
        if not f["has_poc"]:
            issues.append(f"{prefix} Criterio Evidence-First incumplido: falta sección de PoC o comandos curl reproducibles.")
        if not f["has_remediation"]:
            issues.append(f"{prefix} Falta sección de recomendación o remediación técnica.")

        # Verificar activo contra target.yaml si está disponible
        if scope_val and scope_data and f["asset"] and f["asset"] != "N/A":
            verdict, reason = scope_val.check_scope(f["asset"], scope_data)
            if verdict == "OUT_OF_SCOPE":
                issues.append(f"{prefix} ALERTA CRITICA: El activo evaluado '{f['asset']}' esta marcado FUERA DE ALCANCE ({reason})")

    return len(issues) == 0, issues


def build_report(engagement_dir: pathlib.Path, output_path: Optional[pathlib.Path] = None) -> pathlib.Path:
    """Compila el informe final REPORT.md a partir de target.yaml y evidence/*.md."""
    if output_path is None:
        output_path = engagement_dir / "REPORT.md"

    evidence_dir = engagement_dir / "evidence"
    findings = get_findings(evidence_dir)

    # Intentar leer metadatos de target.yaml
    eng_name = engagement_dir.name
    client = "Organización / Plataforma Objetivo"
    vpn_profile = "none"
    auditor = "tester"
    date_str = datetime.date.today().isoformat()
    scope_val = load_scope_validator()
    target_yaml = engagement_dir / "target.yaml"
    target_data: Dict[str, Any] = {}

    if scope_val and target_yaml.is_file():
        try:
            target_data = scope_val.load_target_yaml(target_yaml)
            eng_meta = target_data.get("engagement", {})
            eng_name = eng_meta.get("name", eng_name)
            client = eng_meta.get("client", client)
            auditor = eng_meta.get("auditor", auditor)
            vpn_profile = target_data.get("network", {}).get("vpn_profile", vpn_profile)
        except Exception:
            pass

    # Conteo por severidad
    counts = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0, "INFO": 0}
    for f in findings:
        counts[f["severity"]] = counts.get(f["severity"], 0) + 1

    total_vulns = len(findings)
    overall_posture = "Bajo"
    if counts["CRITICAL"] > 0:
        overall_posture = "Crítico"
    elif counts["HIGH"] > 0:
        overall_posture = "Alto"
    elif counts["MEDIUM"] > 0:
        overall_posture = "Medio"

    # Construir contenido markdown
    lines: List[str] = [
        f"# Informe de Auditoría de Seguridad: {eng_name}",
        "",
        f"- **Cliente / Entorno:** {client}",
        f"- **Fecha de Emisión:** {date_str}",
        f"- **Auditor Responsable:** {auditor}",
        f"- **Perfil de Conexión:** {vpn_profile}",
        f"- **Postura General de Riesgo:** **{overall_posture}**",
        "- **Estado:** Finalizado / Reportado",
        "",
        "---",
        "",
        "## 1. Resumen Ejecutivo",
        "",
        f"Durante el periodo de evaluación sobre el objetivo **{eng_name}**, se llevaron a cabo pruebas técnicas autorizadas "
        "bajo enfoque de caja negra/gris, siguiendo los lineamientos metodológicos de OWASP y PTES con trazabilidad continua. "
        f"Se identificaron un total de **{total_vulns} hallazgos confirmados** distribuidos de la siguiente manera:",
        "",
        f"- **Crítica:** {counts['CRITICAL']}",
        f"- **Alta:** {counts['HIGH']}",
        f"- **Media:** {counts['MEDIUM']}",
        f"- **Baja:** {counts['LOW']}",
        f"- **Informativa:** {counts['INFO']}",
        "",
        "---",
        "",
        "## 2. Alcance y Límites Operacionales",
        "",
    ]

    # Desglosar alcance si existe target.yaml
    if target_data and "scope" in target_data:
        in_s = target_data["scope"].get("in_scope", {})
        out_s = target_data["scope"].get("out_of_scope", {})
        lines.append("### Activos Autorizados (In-Scope):")
        for d in in_s.get("domains", []):
            lines.append(f"- `[dominio]` {d}")
        for ip in in_s.get("ips", []):
            lines.append(f"- `[ip]` {ip}")
        for c in in_s.get("cidrs", []):
            lines.append(f"- `[cidr]` {c}")
        for ep in in_s.get("endpoints", []):
            lines.append(f"- `[endpoint]` {ep}")
        if not any(in_s.values()):
            lines.append("- (Definido en scope.txt o sin restricciones listadas)")

        if any(out_s.values()):
            lines.append("\n### Exclusiones Estrictas (Out-of-Scope):")
            for d in out_s.get("domains", []):
                lines.append(f"- `[exclusión]` {d}")
            for ip in out_s.get("ips", []):
                lines.append(f"- `[exclusión]` {ip}")
            for n in out_s.get("notes", []):
                lines.append(f"- *Nota:* {n}")
        lines.append("")
    else:
        lines.append("- Alcance definido según `scope.txt` en la raíz del engagement.\n")

    lines.extend([
        "---",
        "",
        "## 3. Matriz Consolidada de Hallazgos",
        "",
        "| ID | Vulnerabilidad / Hallazgo | Severidad | CVSS v3.1 | Activo Afectado | Estado |",
        "|---|---|---|---|---|---|",
    ])

    if findings:
        for f in findings:
            lines.append(
                f"| {f['id']} | [{f['title']}](#{f['id'].lower()}-{re.sub(r'[^a-zA-Z0-9]+', '-', f['title'].lower()).strip('-')}) "
                f"| {f['severity'].capitalize()} | {f['cvss_score']} | `{f['asset']}` | {f['status']} |"
            )
    else:
        lines.append("| - | No se registraron vulnerabilidades confirmadas | - | - | - | - |")

    lines.extend([
        "",
        "---",
        "",
        "## 4. Detalle Técnico de Hallazgos y Reproducción",
        "",
    ])

    if findings:
        for f in findings:
            lines.extend([
                f"### {f['id']}: {f['title']}",
                "",
                f"- **Severidad:** {f['severity'].capitalize()} (Score: {f['cvss_score']})",
                f"- **Vector CVSS:** `{f['cvss_v31']}`",
                f"- **CWE:** {f['cwe']}",
                f"- **Activo:** `{f['asset']}`",
                f"- **Auditoría Forense:** Registro sellado en `{f['audit_log']}`",
                "",
                f"{f['body']}",
                "",
                "---",
                "",
            ])
    else:
        lines.append("_No se han adjuntado fichas técnicas en `evidence/`._\n")

    lines.extend([
        "## 5. Registro de Limpieza (Post-Engagement)",
        "",
        "- [x] Artefactos temporales y cargas de prueba en `evidence/` consolidados.",
        "- [ ] Scripts de prueba y shells efímeras retiradas de servidores objetivo.",
        "- [ ] Cuentas o credenciales temporales solicitadas para revocación.",
        "",
        "---",
        "",
        "## 6. Trazabilidad Forense",
        "",
        f"El registro determinista y continuo de todas las acciones de terminal asociadas a esta evaluación "
        f"permanece archivado en `{engagement_dir / 'terminal.log'}` para fines de auditoría y no repudio.",
        "",
    ])

    output_path.write_text("\n".join(lines), encoding="utf-8")
    return output_path


def main() -> int:
    if len(sys.argv) < 3:
        print("Uso: pt-report-compiler.py <list|check|build> <ruta_engagement> [salida_reporte]", file=sys.stderr)
        return 2

    action = sys.argv[1].lower()
    eng_dir = pathlib.Path(sys.argv[2]).resolve()

    if not eng_dir.is_dir():
        print(f"Error: La ruta especificada no es un directorio válido: {eng_dir}", file=sys.stderr)
        return 2

    evidence_dir = eng_dir / "evidence"

    if action == "list":
        findings = get_findings(evidence_dir)
        use_color = sys.stdout.isatty() or os.environ.get("SECLAB_COLOR", "1") == "1"

        print(f"SECLAB-SBF - Hallazgos en {eng_dir.name} ({len(findings)} registrados):\n")
        if not findings:
            print("  (No hay fichas de evidencia en evidence/)")
            return 0

        print(f"  {'ID':<10} {'SEVERIDAD':<12} {'CVSS':<6} {'ACTIVO':<30} {'TITULO'}")
        print("  " + "-" * 78)
        for f in findings:
            sev = f["severity"].capitalize()
            color = SEVERITY_COLORS.get(f["severity"], "") if use_color else ""
            reset = SEVERITY_COLORS["RESET"] if use_color else ""
            print(f"  {f['id']:<10} {color}{sev:<12}{reset} {f['cvss_score']:<6} {f['asset'][:28]:<30} {f['title']}")
        print("")
        return 0

    elif action == "check":
        ok, issues = check_findings(eng_dir)
        if ok:
            print(f"[+] Verificación exitosa: Todas las evidencias en {eng_dir.name} cumplen con el estándar Evidence-First.")
            for msg in issues:
                print(f"    - {msg}")
            return 0
        else:
            print(f"[!] Fallo de validación en las evidencias de {eng_dir.name}:", file=sys.stderr)
            for iss in issues:
                print(f"    [X] {iss}", file=sys.stderr)
            return 1

    elif action == "build":
        out_file = None
        if len(sys.argv) >= 4:
            out_file = pathlib.Path(sys.argv[3]).resolve()
        res_file = build_report(eng_dir, out_file)
        print(f"[+] Reporte compilado exitosamente en: {res_file}")
        findings = get_findings(evidence_dir)
        print(f"    Total de hallazgos consolidados: {len(findings)}")
        return 0

    else:
        print(f"Error: Acción desconocida '{action}'. Usa list, check o build.", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
