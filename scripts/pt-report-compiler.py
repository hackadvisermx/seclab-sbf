#!/usr/bin/env python3
"""Compilador y Linter de Informes y Hallazgos de Seguridad para SecLab-SBF.

Lee especificaciones de alcance (target.yaml), fichas estructuradas de evidencia
(evidence/*.md) y bitacoras de auditoria (terminal.log) para compilar reportes
consolidados profesionales de pentest y bug bounty.

Sin dependencias externas obligatorias (Python 3 stdlib).
"""

import datetime
import importlib.machinery
import importlib.util
import os
import pathlib
import re
import sys
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from seclab_artifacts import validate_artifact_refs

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
                    if key == 'artifact_refs':
                        metadata[key] = val.strip()
                        continue
                    val = val.strip().strip("'\"")
                    # Manejo de comentarios inline
                    if " #" in val:
                        val = val.split(" #")[0].strip().strip("'\"")
                    metadata[key] = val

    return metadata, body


def normalize_status(raw_status: str) -> str:
    """Normaliza estados heterogeneos de hallazgos al ciclo Evidence-First."""
    raw = str(raw_status or "").strip().upper()
    status_map = {
        "PROVEN": "PROVEN",
        "CONFIRMADO": "PROVEN",
        "VERIFIED": "PROVEN",
        "CANDIDATE": "CANDIDATE",
        "NULL": "CANDIDATE",
        "~": "CANDIDATE",
        "HIPOTESIS": "CANDIDATE",
        "DISPROVED": "DISPROVED",
        "FALSO_POSITIVO": "DISPROVED",
        "FALSO POSITIVO": "DISPROVED",
        "FALSE_POSITIVE": "DISPROVED",
        "MITIGATED": "MITIGATED",
        "MITIGADO": "MITIGATED",
        "REMEDIATED": "MITIGATED",
        "DRAFT": "DRAFT",
        "BORRADOR": "DRAFT",
        "BLOCKED": "BLOCKED",
    }
    return status_map.get(raw, raw if raw else "CANDIDATE")


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

    normalized_status = normalize_status(meta.get("status"))

    has_negative_control = (
        "## 2b. Control Negativo" in body
        or "control negativo" in body.lower()
        or "negative control" in body.lower()
    )
    has_bounded_proof = (
        "## 2c. Verificaci" in body
        or "bounded testing" in body.lower()
        or "no destructiv" in body.lower()
    )

    return {
        "file": file_path.name,
        "path": file_path,
        "id": finding_id,
        "title": title,
        "severity": severity,
        "cvss_v31": meta.get("cvss_vector", meta.get("cvss_v31", "")),
        "cvss_score": cvss_score,
        "cwe": meta.get("cwe", "CWE-Unknown"),
        "asset": meta.get("asset", "N/A"),
        "status": normalized_status,
        "auditor": meta.get("auditor", "tester"),
        "date": meta.get("date", datetime.date.today().isoformat()),
        "audit_log": meta.get("audit_log", "terminal.log"),
        "body": body.strip(),
        "artifact_refs_raw": meta.get('artifact_refs', []),
        "has_poc": "```bash" in body or "curl " in body or "## 2. Pasos" in body or "## Pasos para Reproducir" in body,
        "has_negative_control": has_negative_control,
        "has_bounded_proof": has_bounded_proof,
        "has_remediation": "## 5. Remediaci" in body or "## Remediaci" in body,
    }


def get_findings(evidence_dir: pathlib.Path, strict: bool = False) -> List[Dict[str, Any]]:
    """Carga y ordena todos los hallazgos en el directorio de evidencia."""
    if not evidence_dir.is_dir():
        return []

    if strict and evidence_dir.is_symlink():
        raise ValueError("El directorio de evidencia no puede ser un enlace simbólico.")
    findings = []
    for f in sorted(evidence_dir.glob("*.md")):
        if f.name.startswith("_") or f.name.lower() == "readme.md":
            continue
        try:
            if strict and f.is_symlink():
                raise ValueError("La ficha no puede ser un enlace simbólico.")
            findings.append(parse_evidence_file(f))
        except Exception as e:
            if strict:
                raise ValueError(f"No se pudo leer la ficha {f.name}: {e}") from e
            print(f"[!] Advertencia: No se pudo parsear {f}: {e}", file=sys.stderr)

    # Ordenar por severidad descendente y luego por CVSS score
    findings.sort(
        key=lambda x: (SEVERITY_ORDER.get(x["severity"], 0), x["cvss_score"]),
        reverse=True,
    )
    return findings


def find_duplicate_groups(findings: List[Dict[str, Any]]) -> List[List[Dict[str, Any]]]:
    """Agrupa hallazgos que comparten CWE y activo exacto: posible duplicado por
    causa raíz (mismo defecto subyacente afectando el mismo recurso), al estilo
    de la deduplicación de Faraday. Excluye CWE desconocido o activo ausente
    ("N/A"), ya que agrupar por esos valores produciría falsos positivos en
    cascada. No fusiona ni descarta nada automáticamente: solo lo señala para
    que el operador decida consolidar con `pt-finding` (ver
    skills/duplicate-scope-guard/SKILL.md, Paso 3b).
    """
    groups: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}
    for finding in findings:
        cwe = str(finding.get("cwe", "")).strip()
        asset = str(finding.get("asset", "")).strip()
        if not cwe or cwe.upper() == "CWE-UNKNOWN" or not asset or asset.upper() == "N/A":
            continue
        groups.setdefault((cwe.upper(), asset), []).append(finding)
    return [group for group in groups.values() if len(group) > 1]


def format_duplicate_warning(group: List[Dict[str, Any]]) -> str:
    ids = ", ".join(f["id"] for f in group)
    return (
        f"Posible duplicado por causa raíz: {ids} comparten {group[0]['cwe']} "
        f"en el activo '{group[0]['asset']}'. Si es el mismo defecto subyacente, "
        "consolida con pt-finding en vez de mantener fichas separadas."
    )


def load_scope_validator():
    """Carga dinamicamente scripts/pt-scope-validator.py si existe."""
    script_path = pathlib.Path(__file__).resolve().parent / "pt-scope-validator.py"
    if not script_path.is_file():
        script_path = pathlib.Path("/usr/local/bin/pt-scope-validator")
    if script_path.is_file():
        spec = importlib.util.spec_from_file_location("pt_scope_validator", script_path,
            loader=importlib.machinery.SourceFileLoader("pt_scope_validator", str(script_path)))
        if spec and spec.loader:
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            return mod
    return None


class ReportValidationError(ValueError):
    def __init__(self, issues):
        self.issues = issues
        super().__init__("Reporte bloqueado: " + "; ".join(issues))


def review_report_inputs(engagement_dir: pathlib.Path):
    evidence_dir = engagement_dir / "evidence"
    issues: List[str] = []
    findings = []
    if not evidence_dir.is_dir():
        issues.append(f"El directorio de evidencia no existe: {evidence_dir}")
    else:
        try:
            findings = get_findings(evidence_dir, strict=True)
        except (OSError, ValueError) as error:
            issues.append(str(error))

    scope_val = None
    scope_data = {}
    try:
        scope_val = load_scope_validator()
        if scope_val is None:
            issues.append("Scope Guard no está disponible; reconstruye la imagen del laboratorio.")
        else:
            scope_data = scope_val.load_target_yaml(engagement_dir / "target.yaml")
    except Exception as error:
        issues.append(f"No se pudo validar target.yaml: {error}")

    for f in findings:
        prefix = f"[{f['file']}]"
        try:
            f['artifact_refs'] = validate_artifact_refs(engagement_dir, f['artifact_refs_raw'])
        except (OSError, ValueError) as error:
            issues.append(f'{prefix} Evidencia vinculada no válida: {error}')
        if not f["title"]:
            issues.append(f"{prefix} Falta el título de la vulnerabilidad.")
        if not f["has_poc"]:
            issues.append(f"{prefix} Criterio Evidence-First incumplido: falta sección de PoC o comandos curl reproducibles.")
        if not f["has_remediation"]:
            issues.append(f"{prefix} Falta sección de recomendación o remediación técnica.")
        asset = str(f["asset"]).strip()
        if not asset or asset.upper() == "N/A":
            issues.append(f"{prefix} Falta el activo; indica un objetivo autorizado en target.yaml.")
        elif scope_val and scope_data:
            try:
                verdict, reason = scope_val.check_scope(asset, scope_data)
                if verdict == "OUT_OF_SCOPE":
                    issues.append(f"{prefix} ALERTA CRITICA: El activo evaluado '{asset}' esta marcado FUERA DE ALCANCE ({reason})")
                elif verdict != "IN_SCOPE":
                    issues.append(f"{prefix} Activo '{asset}' sin alcance confirmado ({verdict}: {reason}). Revisa target.yaml.")
            except Exception as error:
                issues.append(f"{prefix} No se pudo validar el activo: {error}")

    duplicates = [format_duplicate_warning(group) for group in find_duplicate_groups(findings)]
    return findings, scope_data, issues, duplicates


def check_findings(engagement_dir: pathlib.Path) -> Tuple[bool, List[str], List[str]]:
    """Devuelve (ok, issues, duplicate_warnings); los duplicados no bloquean."""
    findings, _, issues, duplicates = review_report_inputs(engagement_dir)
    if not findings and not issues:
        return True, ["No se encontraron fichas de evidencia (.md) en el directorio."], duplicates
    return not issues, issues, duplicates


def build_report(engagement_dir: pathlib.Path, output_path: Optional[pathlib.Path] = None, artifact_reference_output=None) -> pathlib.Path:
    """Compila el informe final REPORT.md a partir de target.yaml y evidence/*.md."""
    if output_path is None:
        output_path = engagement_dir / "REPORT.md"

    findings, target_data, issues, _ = review_report_inputs(engagement_dir)
    if issues:
        raise ReportValidationError(issues)
    if artifact_reference_output is not None:
        for finding in findings:
            for reference in finding.get('artifact_refs', []):
                artifact_reference_output[reference['path']] = reference['sha256']

    # Intentar leer metadatos de target.yaml
    eng_name = engagement_dir.name
    client = "Organización / Plataforma Objetivo"
    vpn_profile = "none"
    auditor = "tester"
    date_str = datetime.date.today().isoformat()
    eng_meta = target_data.get("engagement", {})
    eng_name = eng_meta.get("name", eng_name)
    client = eng_meta.get("client", client)
    auditor = eng_meta.get("auditor", auditor)
    vpn_profile = target_data.get("network", {}).get("vpn_profile", vpn_profile)

    confirmed = [f for f in findings if f["status"] == "PROVEN"]
    historical = sum(f["status"] == "MITIGATED" for f in findings)
    unconfirmed = len(findings) - len(confirmed) - historical

    # Solo evidencia confirmada activa determina el riesgo actual.
    counts = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0, "INFO": 0}
    for f in confirmed:
        counts[f["severity"]] = counts.get(f["severity"], 0) + 1

    total_vulns = len(confirmed)
    overall_posture = "Bajo" if confirmed else "Sin hallazgos confirmados activos"
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
        "- **Estado:** Borrador compilado / Pendiente de revisión",
        "",
        "---",
        "",
        "## 1. Resumen Ejecutivo",
        "",
        f"Este borrador consolida las fichas de **{eng_name}** frente al alcance declarado en `target.yaml`. "
        "Los estados son declaraciones del operador y requieren revisión humana; la compilación no acredita "
        "autorización legal, ejecución de una metodología ni suficiencia de la evidencia. "
        f"Las fichas registran **{total_vulns} hallazgos confirmados activos** distribuidos de la siguiente manera:",
        "",
        f"- **Crítica:** {counts['CRITICAL']}",
        f"- **Alta:** {counts['HIGH']}",
        f"- **Media:** {counts['MEDIUM']}",
        f"- **Baja:** {counts['LOW']}",
        f"- **Informativa:** {counts['INFO']}",
        f"- **Históricos mitigados (excluidos del riesgo actual):** {historical}",
        f"- **Otros registros no confirmados activos (excluidos del riesgo actual):** {unconfirmed}",
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
            lines.append("- Sin activos autorizados declarados; no se permite inferir alcance.")

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
        "## 3. Matriz Consolidada de Evidencias",
        "",
        "Incluye todos los registros para trazabilidad. Solo PROVEN se cuenta como hallazgo confirmado activo; MITIGATED es histórico y los demás estados no acreditan riesgo actual.",
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

    duplicate_groups = find_duplicate_groups(findings)
    if duplicate_groups:
        lines.extend(["", "**⚠ Posibles duplicados por causa raíz (revisión manual recomendada):**", ""])
        for group in duplicate_groups:
            lines.append(f"- {format_duplicate_warning(group)}")

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
                f"- **Estado de evidencia:** {f['status']}",
                f"- **Vector CVSS:** `{f['cvss_v31']}`",
                f"- **CWE:** {f['cwe']}",
                f"- **Activo:** `{f['asset']}`",
                f"- **Registro referido por la ficha:** `{f['audit_log']}` (vínculo e integridad no verificados)",
                *[f"- **Artefacto vinculado:** [{reference['path']}](./{reference['path']}) · SHA-256 `{reference['sha256']}`"
                  for reference in f.get('artifact_refs', [])],
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
        "El registro `terminal.log` está disponible en el engagement; no se acredita que sea completo ni sellado."
        if (engagement_dir / 'terminal.log').is_file() and not (engagement_dir / 'terminal.log').is_symlink()
        else "No hay un registro local `terminal.log` disponible; no se acredita trazabilidad de la terminal.",
        "En el export, `source-manifest.json` relaciona hashes de archivos originales y de sus copias entregadas. "
        "Los hashes permiten comparar contenido; no constituyen una firma ni prueban procedencia por sí solos.",
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

        duplicate_groups = find_duplicate_groups(findings)
        if duplicate_groups:
            print(f"[?] {len(duplicate_groups)} posible(s) duplicado(s) por causa raíz (mismo CWE + activo):")
            for group in duplicate_groups:
                print(f"    - {format_duplicate_warning(group)}")
            print("")
        return 0

    elif action == "check":
        ok, issues, duplicate_warnings = check_findings(eng_dir)
        if ok:
            print(f"[+] Verificación exitosa: Todas las evidencias en {eng_dir.name} cumplen con el estándar Evidence-First.")
            for msg in issues:
                print(f"    - {msg}")
        else:
            print(f"[!] Fallo de validación en las evidencias de {eng_dir.name}:", file=sys.stderr)
            for iss in issues:
                print(f"    [X] {iss}", file=sys.stderr)
        if duplicate_warnings:
            stream = sys.stdout if ok else sys.stderr
            print(f"\n[?] {len(duplicate_warnings)} posible(s) duplicado(s) por causa raíz (no bloquea la verificación):", file=stream)
            for msg in duplicate_warnings:
                print(f"    - {msg}", file=stream)
        return 0 if ok else 1

    elif action == "build":
        out_file = None
        if len(sys.argv) >= 4:
            out_file = pathlib.Path(sys.argv[3]).resolve()
        try:
            res_file = build_report(eng_dir, out_file)
        except (ValueError, OSError) as error:
            print(f"[!] {error}", file=sys.stderr)
            return 1
        print(f"[+] Reporte compilado exitosamente en: {res_file}")
        findings = get_findings(evidence_dir)
        print(f"    Total de hallazgos consolidados: {len(findings)}")
        return 0

    else:
        print(f"Error: Acción desconocida '{action}'. Usa list, check o build.", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
