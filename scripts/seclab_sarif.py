#!/usr/bin/env python3
"""seclab_sarif.py - Exportador de hallazgos al estándar OASIS SARIF v2.1.0."""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
from typing import Any, Dict, List, Optional

try:
    import yaml
except ImportError:
    yaml = None


def _parse_finding_file(file_path: pathlib.Path) -> Optional[Dict[str, Any]]:
    """Extrae metadatos y secciones de una ficha de hallazgo Markdown."""
    try:
        content = file_path.read_text(encoding="utf-8")
    except Exception:
        return None

    if not content.startswith("---"):
        return None

    parts = content.split("---", 2)
    if len(parts) < 3:
        return None

    frontmatter_raw = parts[1]
    body_raw = parts[2]

    metadata = {}
    if yaml is not None:
        try:
            metadata = yaml.safe_load(frontmatter_raw) or {}
        except Exception:
            metadata = {}
    else:
        for line in frontmatter_raw.splitlines():
            line = line.strip()
            if ":" in line and not line.startswith("#"):
                k, v = line.split(":", 1)
                metadata[k.strip()] = v.strip().strip("\"'")

    if not isinstance(metadata, dict):
        return None

    # Parsear secciones del cuerpo
    description = ""
    evidence = ""
    remediation = ""

    current_section = "desc"
    desc_lines = []
    ev_lines = []
    rem_lines = []

    for line in body_raw.splitlines():
        lower = line.strip().lower()
        if lower.startswith("## ") or lower.startswith("# "):
            if "evidencia" in lower or "pasos" in lower or "reproducción" in lower:
                current_section = "ev"
                continue
            elif "remediación" in lower or "mitigación" in lower or "solución" in lower:
                current_section = "rem"
                continue
            elif "descripción" in lower:
                current_section = "desc"
                continue

        if current_section == "desc":
            desc_lines.append(line)
        elif current_section == "ev":
            ev_lines.append(line)
        elif current_section == "rem":
            rem_lines.append(line)

    description = "\n".join(desc_lines).strip()
    evidence = "\n".join(ev_lines).strip()
    remediation = "\n".join(rem_lines).strip()

    slug = file_path.stem
    return {
        "slug": slug,
        "filename": file_path.name,
        "title": str(metadata.get("title") or metadata.get("name") or slug),
        "severity": str(metadata.get("severity", "MEDIUM")).upper(),
        "cvss_score": float(metadata.get("cvss_score") or metadata.get("cvss", 0.0)),
        "cvss_vector": str(metadata.get("cvss_vector", "")),
        "status": str(metadata.get("status", "draft")),
        "target": str(metadata.get("target") or metadata.get("asset") or ""),
        "source_job_id": metadata.get("source_job_id"),
        "source_stage": metadata.get("source_stage"),
        "description": description,
        "evidence": evidence,
        "remediation": remediation,
    }


def severity_to_sarif_level(severity: str) -> str:
    """Convierte la severidad pentest/CVSS al nivel estándar de SARIF."""
    s = (severity or "").upper().strip()
    if s in ("CRITICAL", "CRITICA", "HIGH", "ALTA"):
        return "error"
    elif s in ("MEDIUM", "MEDIA"):
        return "warning"
    else:
        return "note"


def export_findings_to_sarif(target_dir: pathlib.Path | str) -> Dict[str, Any]:
    """Genera un reporte SARIF v2.1.0 formal para todos los hallazgos en evidence/*.md."""
    target_path = pathlib.Path(target_dir)
    evidence_dir = target_path / "evidence"

    findings: List[Dict[str, Any]] = []
    if evidence_dir.is_dir():
        for f in sorted(evidence_dir.glob("*.md")):
            if f.is_file() and not f.name.startswith("."):
                item = _parse_finding_file(f)
                if item:
                    findings.append(item)

    rules = []
    results = []

    for f in findings:
        rule_id = f["slug"]
        sarif_level = severity_to_sarif_level(f["severity"])

        rules.append({
            "id": rule_id,
            "name": rule_id.replace("-", "_"),
            "shortDescription": {
                "text": f["title"]
            },
            "fullDescription": {
                "text": f["description"] or f["title"]
            },
            "defaultConfiguration": {
                "level": sarif_level
            },
            "properties": {
                "security_severity": str(f["cvss_score"]),
                "cvss_vector": f["cvss_vector"],
                "tags": ["security", "pentest", f["severity"].lower()]
            }
        })

        message_text = f["title"]
        if f["description"]:
            message_text += f"\n\n{f['description']}"
        if f["remediation"]:
            message_text += f"\n\nRemediación sugerida:\n{f['remediation']}"

        result_item = {
            "ruleId": rule_id,
            "level": sarif_level,
            "message": {
                "text": message_text
            },
            "locations": [
                {
                    "physicalLocation": {
                        "artifactLocation": {
                            "uri": f"evidence/{f['filename']}",
                            "uriBaseId": "%SRCROOT%"
                        }
                    }
                }
            ],
            "properties": {
                "status": f["status"],
                "target": f["target"],
                "severity": f["severity"],
                "cvss_score": f["cvss_score"],
                "cvss_vector": f["cvss_vector"],
                "source_job_id": f["source_job_id"],
                "source_stage": f["source_stage"],
            }
        }
        results.append(result_item)

    sarif_doc = {
        "$schema": "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/Schemata/sarif-schema-2.1.0.json",
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "SecLab-SBF",
                        "version": "3.0.0",
                        "informationUri": "https://github.com/hackadvisermx/seclab-sbf",
                        "rules": rules,
                    }
                },
                "results": results,
            }
        ]
    }

    return sarif_doc


def main():
    parser = argparse.ArgumentParser(description="Exporta hallazgos a formato SARIF v2.1.0")
    parser.add_argument("workspace_dir", help="Directorio raíz del engagement")
    parser.add_argument("--output", "-o", help="Archivo de destino (stdout por defecto)")

    args = parser.parse_args()
    target_path = pathlib.Path(args.workspace_dir)
    if not target_path.is_dir():
        print(f"Error: Directorio no encontrado: {target_path}", file=sys.stderr)
        sys.exit(1)

    doc = export_findings_to_sarif(target_path)
    output_str = json.dumps(doc, indent=2, ensure_ascii=False)

    if args.output:
        out_file = pathlib.Path(args.output)
        out_file.write_text(output_str, encoding="utf-8")
        print(f"SARIF exportado correctamente en: {out_file}")
    else:
        print(output_str)


if __name__ == "__main__":
    main()
