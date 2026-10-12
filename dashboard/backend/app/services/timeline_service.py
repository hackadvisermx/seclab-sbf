"""
timeline_service.py
Construye la línea de tiempo unificada cronológica de un engagement o reto,
correlacionando eventos de alcance, jobs de reconocimiento, revisiones,
hallazgos registrados, notas y reportes técnicos.
"""
from __future__ import annotations

import datetime
import json
import pathlib
from typing import Any, Dict, List, Optional

from fastapi import HTTPException
from app.models.schemas import TimelineEvent, EngagementTimelineResponse
from app.services.workspace_sync import workspace_service
from app.services.recon_service import recon_service


class TimelineService:
    def get_timeline(self, eng_id: str, eng_type: str = "engagement") -> EngagementTimelineResponse:
        target_dir = workspace_service._resolve_dir(eng_id, eng_type)
        if not target_dir.exists():
            raise HTTPException(status_code=404, detail="Proyecto no encontrado")

        events: List[TimelineEvent] = []

        # 1. Alcance (target.yaml)
        target_yaml_path = target_dir / "target.yaml"
        if target_yaml_path.is_file():
            try:
                st = target_yaml_path.stat()
                ts = datetime.datetime.fromtimestamp(st.st_mtime, tz=datetime.timezone.utc).isoformat()
                target_yaml = workspace_service.get_target_yaml(eng_id, eng_type)
                scope = target_yaml.get("scope", {}) if isinstance(target_yaml, dict) else {}
                in_scope = scope.get("in_scope", {}) if isinstance(scope, dict) else {}
                domains = in_scope.get("domains", []) if isinstance(in_scope, dict) else []
                ips = in_scope.get("ips", []) if isinstance(in_scope, dict) else []
                events.append(
                    TimelineEvent(
                        id=f"scope-{eng_id}",
                        timestamp=ts,
                        category="scope",
                        type="scope_configured",
                        title="Alcance Autorizado (target.yaml)",
                        status="info",
                        summary=f"Alcance declarado con {len(domains)} dominio(s) y {len(ips)} IP(s).",
                        details={"domains": domains, "ips": ips, "version": target_yaml.get("version", "1.0") if isinstance(target_yaml, dict) else "1.0"},
                        source_ref="target.yaml",
                    )
                )
            except Exception:
                pass

        # 2. Jobs de Reconocimiento y Revisiones
        try:
            history_data = recon_service.store.history((eng_type, eng_id), limit=100)
            jobs = history_data.get("jobs", [])
            for job in jobs:
                status_str = job.get("status", "unknown")
                stage = job.get("stage", "default")
                run_id = job.get("run_id", "unknown")
                dry_run = bool(job.get("dry_run"))
                started_at = job.get("started_at")
                error_msg = job.get("error")

                if started_at:
                    if status_str == "completed":
                        status_kind = "success"
                    elif status_str in ("failed", "blocked", "interrupted"):
                        status_kind = "error"
                    elif status_str in ("cancelled", "cancelling"):
                        status_kind = "warning"
                    else:
                        status_kind = "info"

                    title_prefix = "Simulación de Reconocimiento" if dry_run else "Ejecución de Reconocimiento"
                    summary_text = f"Job {run_id} ({status_str}) en etapa '{stage}'"
                    if error_msg:
                        summary_text += f": {error_msg}"

                    events.append(
                        TimelineEvent(
                            id=f"job-{run_id}",
                            timestamp=started_at,
                            category="recon",
                            type="recon_job",
                            title=f"{title_prefix} [{stage}]",
                            status=status_kind,
                            summary=summary_text,
                            details={
                                "run_id": run_id,
                                "stage": stage,
                                "status": status_str,
                                "dry_run": dry_run,
                                "finished_at": job.get("finished_at"),
                                "error": error_msg,
                            },
                            source_ref=f"recon/{run_id}",
                        )
                    )

                # Revisión humana registrada del job
                outcome_review = job.get("outcome_review")
                if isinstance(outcome_review, dict) and outcome_review.get("reviewed_at"):
                    events.append(
                        TimelineEvent(
                            id=f"review-{run_id}",
                            timestamp=outcome_review["reviewed_at"],
                            category="recon",
                            type="recon_reviewed",
                            title=f"Revisión de Resultados (Job {run_id})",
                            status="success",
                            summary=f"El operador auditó y confirmó los resultados del Job {run_id}.",
                            details={"run_id": run_id},
                            source_ref=f"recon/{run_id}",
                        )
                    )
        except Exception:
            pass

        # 3. Hallazgos / Evidencias (evidence/*.md)
        try:
            findings = workspace_service.list_findings(eng_id, eng_type)
            for f in findings:
                ev_file = target_dir / "evidence" / f"{f.slug}.md"
                ev_ts = None
                if ev_file.is_file():
                    st = ev_file.stat()
                    ev_ts = datetime.datetime.fromtimestamp(st.st_mtime, tz=datetime.timezone.utc).isoformat()
                elif f.frontmatter.date:
                    ev_ts = f.frontmatter.date
                else:
                    ev_ts = datetime.datetime.now(datetime.timezone.utc).isoformat()

                sev = (f.frontmatter.severity or "MEDIUM").upper()
                stat = f.frontmatter.status or "CANDIDATE"
                status_kind = "error" if sev in ("CRITICAL", "HIGH") else "warning" if sev == "MEDIUM" else "info"

                summary_parts = [f"[{sev}] Estado: {stat}"]
                if f.frontmatter.asset:
                    summary_parts.append(f"Activo: {f.frontmatter.asset}")
                if f.frontmatter.source_job_id:
                    summary_parts.append(f"Origen: Job {f.frontmatter.source_job_id}")

                events.append(
                    TimelineEvent(
                        id=f"finding-{f.slug}",
                        timestamp=ev_ts,
                        category="finding",
                        type="finding_recorded",
                        title=f"Hallazgo: {f.frontmatter.title}",
                        status=status_kind,
                        summary=" | ".join(summary_parts),
                        details={
                            "slug": f.slug,
                            "severity": sev,
                            "status": stat,
                            "asset": f.frontmatter.asset,
                            "source_job_id": f.frontmatter.source_job_id,
                            "source_stage": f.frontmatter.source_stage,
                        },
                        source_ref=f"evidence/{f.slug}.md",
                    )
                )
        except Exception:
            pass

        # 4. Notas del engagement (notes.md)
        notes_path = target_dir / "notes.md"
        if notes_path.is_file():
            try:
                st = notes_path.stat()
                ts = datetime.datetime.fromtimestamp(st.st_mtime, tz=datetime.timezone.utc).isoformat()
                events.append(
                    TimelineEvent(
                        id=f"notes-{eng_id}",
                        timestamp=ts,
                        category="notes",
                        type="notes_updated",
                        title="Notas Técnicas (notes.md)",
                        status="info",
                        summary="Registro de apuntes y procedimientos manuales actualizado.",
                        details={"file": "notes.md"},
                        source_ref="notes.md",
                    )
                )
            except Exception:
                pass

        # 5. Reporte compilado (REPORT.md)
        report_path = target_dir / "REPORT.md"
        if report_path.is_file():
            try:
                st = report_path.stat()
                ts = datetime.datetime.fromtimestamp(st.st_mtime, tz=datetime.timezone.utc).isoformat()
                events.append(
                    TimelineEvent(
                        id=f"report-{eng_id}",
                        timestamp=ts,
                        category="report",
                        type="report_compiled",
                        title="Informe Compilado (REPORT.md)",
                        status="success",
                        summary="El informe técnico formal de la auditoría ha sido generado.",
                        details={"file": "REPORT.md"},
                        source_ref="REPORT.md",
                    )
                )
            except Exception:
                pass

        # 6. Entregables exportados (deliverables/)
        deliverables_dir = target_dir / "deliverables"
        if deliverables_dir.is_dir():
            try:
                for item in sorted(deliverables_dir.iterdir()):
                    if item.is_file() and (item.suffix in (".gz", ".zip") or item.name == "finding-manifest.json"):
                        st = item.stat()
                        ts = datetime.datetime.fromtimestamp(st.st_mtime, tz=datetime.timezone.utc).isoformat()
                        events.append(
                            TimelineEvent(
                                id=f"deliverable-{item.name}",
                                timestamp=ts,
                                category="report",
                                type="deliverable_exported",
                                title=f"Entregable Generado: {item.name}",
                                status="success",
                                summary=f"Paquete exportable ({round(st.st_size / 1024, 1)} KB).",
                                details={"filename": item.name, "size_bytes": st.st_size},
                                source_ref=f"deliverables/{item.name}",
                            )
                        )
            except Exception:
                pass

        # Ordenar cronológicamente (más recientes primero)
        events.sort(key=lambda e: e.timestamp, reverse=True)

        return EngagementTimelineResponse(
            engagement_id=eng_id,
            type=eng_type,
            total_events=len(events),
            events=events,
        )

    def export_timeline(self, eng_id: str, eng_type: str = "engagement", format: str = "json") -> str:
        timeline = self.get_timeline(eng_id, eng_type)
        fmt = (format or "json").lower()
        if fmt == "json":
            data = timeline.model_dump() if hasattr(timeline, "model_dump") else timeline.dict()
            return json.dumps(data, indent=2, ensure_ascii=False)
        elif fmt in ("markdown", "md"):
            now_iso = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
            lines = [
                f"# Línea de Tiempo de Auditoría: {eng_id}",
                "",
                f"- **Tipo de Proyecto**: {eng_type}",
                f"- **Total de Eventos**: {timeline.total_events}",
                f"- **Fecha de Exportación**: {now_iso}",
                "",
                "## Eventos Cronológicos",
                "",
            ]
            if not timeline.events:
                lines.append("_No se registran eventos en la línea de tiempo._\n")
            else:
                lines.extend([
                    "| Fecha / Hora (UTC) | Categoría | Estado | Título | Resumen | Referencia |",
                    "| --- | --- | --- | --- | --- | --- |",
                ])
                for ev in timeline.events:
                    ts = ev.timestamp or "-"
                    cat = ev.category or "-"
                    status = (ev.status or "info").upper()
                    title = (ev.title or "-").replace("|", "\\|")
                    summary = (ev.summary or "-").replace("|", "\\|").replace("\n", " ")
                    ref = (ev.source_ref or "-").replace("|", "\\|")
                    lines.append(f"| {ts} | {cat} | {status} | {title} | {summary} | {ref} |")
                lines.append("")
            return "\n".join(lines)
        else:
            raise HTTPException(status_code=400, detail=f"Formato no soportado: {format}")


timeline_service = TimelineService()
