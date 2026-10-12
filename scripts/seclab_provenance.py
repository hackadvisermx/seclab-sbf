#!/usr/bin/env python3
"""Módulo de Grafo Estructurado de Procedencia y Trazabilidad de Auditoría (V3-02s).

Construye un grafo dirigido (DAG) que correlaciona:
1. Alcance formal (target.yaml)
2. Tareas de reconocimiento y escaneo (recon_jobs.db)
3. Fichas de hallazgo y evidencias (evidence/*.md)
4. Entregables y reportes técnicos (REPORT.md, artifact-manifest.json)

Permite visualizar la cadena completa de custodia técnica desde el objetivo
hasta el informe final compilado y sellado.
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import sqlite3
import sys
from typing import Any, Dict, List, Optional, Set, Union

try:
    import yaml
except ImportError:
    yaml = None


def _parse_yaml_basic(content: str) -> Dict[str, Any]:
    """Parser liviano para target.yaml en entornos sin PyYAML."""
    data: Dict[str, Any] = {}
    current_key: Optional[str] = None
    sub_data: Dict[str, Any] = {}
    sub_list: List[Any] = []
    is_list = False

    for line in content.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        if stripped.endswith(":") and ":" not in stripped[:-1]:
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


def _load_yaml_file(path: pathlib.Path) -> Dict[str, Any]:
    if not path.is_file():
        return {}
    content = path.read_text(encoding="utf-8")
    if yaml is not None:
        try:
            loaded = yaml.safe_load(content)
            if isinstance(loaded, dict):
                return loaded
        except Exception:
            pass
    return _parse_yaml_basic(content)


def build_provenance_graph(engagement_dir: Union[str, pathlib.Path]) -> Dict[str, Any]:
    """Construye el grafo dirigido de procedencia de auditoría para un engagement."""
    eng_path = pathlib.Path(engagement_dir).resolve()
    if not eng_path.is_dir():
        raise FileNotFoundError(f"El directorio de engagement no existe: {eng_path}")

    eng_id = eng_path.name
    nodes: List[Dict[str, Any]] = []
    edges: List[Dict[str, Any]] = []

    node_ids: Set[str] = set()

    def add_node(node_id: str, node_type: str, label: str, status: str, details: Optional[Dict[str, Any]] = None):
        if node_id not in node_ids:
            nodes.append({
                "id": node_id,
                "type": node_type,
                "label": label,
                "status": status,
                "details": details or {},
            })
            node_ids.add(node_id)

    def add_edge(source: str, target: str, edge_type: str, label: str):
        edge_id = f"e_{source}_{target}"
        edges.append({
            "id": edge_id,
            "source": source,
            "target": target,
            "type": edge_type,
            "label": label,
        })

    # 1. Nodo de Alcance (target.yaml)
    target_yaml_path = eng_path / "target.yaml"
    target_data = _load_yaml_file(target_yaml_path)
    scope_data = target_data.get("scope", {}) if isinstance(target_data, dict) else {}
    in_scope = scope_data.get("in_scope", {}) if isinstance(scope_data, dict) else {}
    domains = in_scope.get("domains", []) if isinstance(in_scope, dict) else []
    ips = in_scope.get("ips", []) if isinstance(in_scope, dict) else []

    scope_status = "active" if target_yaml_path.is_file() else "missing"
    scope_node_id = "scope:root"
    add_node(
        node_id=scope_node_id,
        node_type="scope",
        label=f"Alcance ({eng_id})",
        status=scope_status,
        details={
            "file": "target.yaml",
            "domains": domains,
            "ips": ips,
            "targets_count": len(domains) + len(ips),
        },
    )

    # 2. Nodos de Jobs de Reconocimiento (recon_jobs.db)
    db_path = eng_path / "recon_jobs.db"
    job_ids: Set[str] = set()
    if db_path.is_file():
        try:
            conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
            cur = conn.cursor()
            cur.execute("SELECT id, tool, stage, status, command FROM recon_jobs ORDER BY id ASC")
            for j_id, tool, stage, status, cmd in cur.fetchall():
                jid_str = str(j_id)
                job_node_id = f"job:{jid_str}"
                job_ids.add(jid_str)
                st_lower = (status or "unknown").lower()
                add_node(
                    node_id=job_node_id,
                    node_type="job",
                    label=f"{tool or 'recon'} ({stage or 'probe'}) #{jid_str}",
                    status=st_lower,
                    details={
                        "job_id": jid_str,
                        "tool": tool,
                        "stage": stage,
                        "command": cmd,
                    },
                )
                # Enlace de alcance a job
                add_edge(
                    source=scope_node_id,
                    target=job_node_id,
                    edge_type="targets",
                    label="ejecuta en alcance",
                )
            conn.close()
        except Exception:
            pass

    # 3. Nodos de Hallazgos y Evidencias (evidence/*.md)
    evidence_dir = eng_path / "evidence"
    finding_nodes: List[Dict[str, Any]] = []
    unlinked_findings = 0
    with_provenance_count = 0

    if evidence_dir.is_dir():
        for md_file in sorted(evidence_dir.glob("*.md")):
            slug = md_file.stem
            try:
                text = md_file.read_text(encoding="utf-8")
                title = slug
                status = "CANDIDATE"
                sev = "medium"
                asset = ""
                source_job_id = None
                source_stage = None

                if text.startswith("---"):
                    parts = text.split("---", 2)
                    if len(parts) >= 3:
                        for line in parts[1].splitlines():
                            line = line.strip()
                            if line.startswith("title:"):
                                title = line.split(":", 1)[1].strip().strip("\"'")
                            elif line.startswith("status:"):
                                status = line.split(":", 1)[1].strip().upper()
                            elif line.startswith("severity:"):
                                sev = line.split(":", 1)[1].strip().lower()
                            elif line.startswith("asset:"):
                                asset = line.split(":", 1)[1].strip().strip("\"'")
                            elif line.startswith("source_job_id:"):
                                val = line.split(":", 1)[1].strip().strip("\"'")
                                if val:
                                    source_job_id = val
                            elif line.startswith("source_stage:"):
                                val = line.split(":", 1)[1].strip().strip("\"'")
                                if val:
                                    source_stage = val

                finding_node_id = f"finding:{slug}"
                add_node(
                    node_id=finding_node_id,
                    node_type="finding",
                    label=f"[{sev.upper()}] {title}",
                    status=status,
                    details={
                        "slug": slug,
                        "title": title,
                        "severity": sev,
                        "asset": asset,
                        "source_job_id": source_job_id,
                        "source_stage": source_stage,
                        "file": f"evidence/{slug}.md",
                    },
                )
                finding_nodes.append({
                    "id": finding_node_id,
                    "slug": slug,
                    "title": title,
                    "source_job_id": source_job_id,
                })

                if source_job_id and str(source_job_id) in job_ids:
                    # Enlace directo desde el job
                    with_provenance_count += 1
                    add_edge(
                        source=f"job:{source_job_id}",
                        target=finding_node_id,
                        edge_type="evidences",
                        label="produce evidencia",
                    )
                elif source_job_id:
                    # Job externo o referenciado
                    ext_job_node = f"job:{source_job_id}"
                    if ext_job_node not in node_ids:
                        add_node(
                            node_id=ext_job_node,
                            node_type="job",
                            label=f"Job Externo #{source_job_id}",
                            status="external",
                            details={"job_id": str(source_job_id), "type": "external"},
                        )
                        add_edge(
                            source=scope_node_id,
                            target=ext_job_node,
                            edge_type="targets",
                            label="job externo",
                        )
                    with_provenance_count += 1
                    add_edge(
                        source=ext_job_node,
                        target=finding_node_id,
                        edge_type="evidences",
                        label="produce evidencia",
                    )
                else:
                    unlinked_findings += 1
                    add_edge(
                        source=scope_node_id,
                        target=finding_node_id,
                        edge_type="manual_unlinked",
                        label="origen manual / sin job",
                    )
            except Exception:
                pass

    # 4. Nodos de Entregables (REPORT.md y artifact-manifest.json)
    report_path = eng_path / "REPORT.md"
    has_report = report_path.is_file()
    report_node_id = "deliverable:report"
    report_text = ""

    if has_report:
        try:
            report_text = report_path.read_text(encoding="utf-8")
        except Exception:
            pass

        add_node(
            node_id=report_node_id,
            node_type="deliverable",
            label="Reporte (REPORT.md)",
            status="compiled",
            details={"file": "REPORT.md"},
        )

        for fn in finding_nodes:
            slug = fn["slug"]
            # Si el slug aparece en el reporte o si el título está incluido
            if (slug in report_text) or (fn["title"] in report_text) or ("# " in report_text):
                add_edge(
                    source=fn["id"],
                    target=report_node_id,
                    edge_type="compiled_in",
                    label="incluido en informe",
                )

    manifest_path = eng_path / "artifact-manifest.json"
    if manifest_path.is_file():
        manifest_node_id = "deliverable:manifest"
        add_node(
            node_id=manifest_node_id,
            node_type="deliverable",
            label="Manifiesto (artifact-manifest.json)",
            status="sealed",
            details={"file": "artifact-manifest.json"},
        )
        if has_report:
            add_edge(
                source=report_node_id,
                target=manifest_node_id,
                edge_type="verified_by",
                label="integridad sellada",
            )

    # 5. Cálculo de métricas agregadas del grafo
    total_findings = len(finding_nodes)
    coverage_pct = round((with_provenance_count / total_findings * 100.0), 1) if total_findings > 0 else 100.0

    # Cadenas completas: hallazgo con procedencia de job y salida a reporte
    incoming_job_targets = {
        e["target"] for e in edges if e["type"] == "evidences"
    }
    outgoing_report_sources = {
        e["source"] for e in edges if e["type"] == "compiled_in"
    }
    complete_chains = len(incoming_job_targets.intersection(outgoing_report_sources))

    summary = {
        "engagement_id": eng_id,
        "total_nodes": len(nodes),
        "total_edges": len(edges),
        "findings_count": total_findings,
        "with_provenance_count": with_provenance_count,
        "unlinked_findings_count": unlinked_findings,
        "provenance_coverage_pct": coverage_pct,
        "complete_chains_count": complete_chains,
    }

    return {
        "engagement_id": eng_id,
        "summary": summary,
        "nodes": nodes,
        "edges": edges,
    }


def export_provenance_graph_mermaid(graph: Dict[str, Any]) -> str:
    """Genera una representación en sintaxis Mermaid Flowchart del grafo de procedencia."""
    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])

    lines = ["flowchart LR"]

    # Agrupar por subgrafos según el tipo
    groups: Dict[str, List[Dict[str, Any]]] = {
        "scope": [],
        "job": [],
        "finding": [],
        "deliverable": [],
    }

    for n in nodes:
        ntype = n.get("type", "other")
        if ntype in groups:
            groups[ntype].append(n)

    group_titles = {
        "scope": "1. Alcance Formal",
        "job": "2. Reconocimiento y Escaneos",
        "finding": "3. Hallazgos y Evidencias",
        "deliverable": "4. Entregables y Cierre",
    }

    for g_key, g_title in group_titles.items():
        g_nodes = groups.get(g_key, [])
        if g_nodes:
            lines.append(f'  subgraph sub_{g_key} ["{g_title}"]')
            for n in g_nodes:
                nid = n["id"].replace(":", "_").replace("-", "_").replace(".", "_")
                label = n["label"].replace('"', "'")
                lines.append(f'    {nid}["{label}"]')
            lines.append("  end")

    # Aristas
    for e in edges:
        s_id = e["source"].replace(":", "_").replace("-", "_").replace(".", "_")
        t_id = e["target"].replace(":", "_").replace("-", "_").replace(".", "_")
        lbl = e.get("label", "")
        if lbl:
            lines.append(f'  {s_id} -->|"{lbl}"| {t_id}')
        else:
            lines.append(f"  {s_id} --> {t_id}")

    return "\n".join(lines)


def export_provenance_graph_markdown(graph: Dict[str, Any]) -> str:
    """Exporta el grafo de procedencia como informe Markdown con diagrama Mermaid y resumen."""
    summary = graph.get("summary", {})
    eng_id = graph.get("engagement_id", "auditoria")
    mermaid_code = export_provenance_graph_mermaid(graph)

    lines = [
        f"# Grafo de Procedencia de Auditoría: {eng_id}",
        "",
        "## Resumen de Trazabilidad Técnica",
        "",
        f"- **Total de Nodos en Grafo**: {summary.get('total_nodes', 0)}",
        f"- **Total de Relaciones (Aristas)**: {summary.get('total_edges', 0)}",
        f"- **Hallazgos Totales**: {summary.get('findings_count', 0)}",
        f"- **Hallazgos con Procedencia de Job**: {summary.get('with_provenance_count', 0)}",
        f"- **Hallazgos Sin Job (Manuales)**: {summary.get('unlinked_findings_count', 0)}",
        f"- **Cobertura de Procedencia**: {summary.get('provenance_coverage_pct', 0.0)}%",
        f"- **Cadenas Completas (Alcance ➔ Job ➔ Hallazgo ➔ Informe)**: {summary.get('complete_chains_count', 0)}",
        "",
        "## Diagrama de Flujo (Mermaid)",
        "",
        "```mermaid",
        mermaid_code,
        "```",
        "",
    ]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Grafo Estructurado de Procedencia SecLab-SBF")
    parser.add_argument("engagement_dir", help="Ruta al directorio del engagement o reto")
    parser.add_argument(
        "--format",
        choices=["json", "mermaid", "markdown"],
        default="json",
        help="Formato de exportación del grafo (default: json)",
    )
    args = parser.parse_args()

    try:
        graph = build_provenance_graph(args.engagement_dir)
        if args.format == "mermaid":
            print(export_provenance_graph_mermaid(graph))
        elif args.format == "markdown":
            print(export_provenance_graph_markdown(graph))
        else:
            print(json.dumps(graph, indent=2, ensure_ascii=False))
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
