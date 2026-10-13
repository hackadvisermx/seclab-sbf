import datetime
import json
import pathlib
from typing import Any, Dict, List, Optional
from app.services.workspace_sync import workspace_service
from app.services.recon_service import recon_service
from seclab_supervision import load_supervision_responses, save_checkpoint_response


class SupervisionService:
    def get_supervision_state(self, eng_id: str, eng_type: str = "engagement") -> Dict[str, Any]:
        """Calcula el estado consolidado de supervisión y checkpoints de auditoría para un engagement."""
        target_dir = workspace_service._resolve_dir(eng_id, eng_type)
        if not target_dir.exists():
            raise FileNotFoundError(f"Engagement {eng_id} no encontrado")

        # 1. Alcance y contrato
        target_yaml = workspace_service.get_target_yaml(eng_id, eng_type)
        scope_txt_file = target_dir / "scope.txt"
        scope_txt_present = scope_txt_file.is_file()

        auth_meta = target_yaml.get("authorization", {}) if isinstance(target_yaml, dict) else {}
        allow_passive = bool(auth_meta.get("allow_passive", False))
        allow_active = bool(auth_meta.get("allow_active", False))

        scope_meta = target_yaml.get("scope", {}).get("in_scope", {}) if isinstance(target_yaml, dict) else {}
        in_scope_domains = scope_meta.get("domains") or []
        in_scope_ips = scope_meta.get("ips") or []
        in_scope_cidrs = scope_meta.get("cidrs") or []
        total_targets_in_scope = len(in_scope_domains) + len(in_scope_ips) + len(in_scope_cidrs)

        # 2. Reconocimiento y jobs
        recon_jobs_data = recon_service.store.history(eng_id, eng_type)
        jobs = recon_jobs_data.get("jobs", []) if isinstance(recon_jobs_data, dict) else []
        latest_job = jobs[0] if jobs else None

        recon_dir = target_dir / "recon"
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

        # 3. Hallazgos y evidencias
        findings = workspace_service.list_findings(eng_id, eng_type)
        total_findings = len(findings)
        candidates_count = sum(1 for f in findings if f.get("status") == "CANDIDATE")
        proven_count = sum(1 for f in findings if f.get("status") == "PROVEN")
        disproved_count = sum(1 for f in findings if f.get("status") == "DISPROVED")

        by_severity = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0, "INFO": 0}
        findings_with_evidence = 0
        for f in findings:
            sev = (f.get("severity") or "INFO").upper()
            if sev in by_severity:
                by_severity[sev] += 1
            if f.get("artifact_refs") and len(f.get("artifact_refs")) > 0:
                findings_with_evidence += 1

        ev_dir = target_dir / "evidence"
        total_evidence_files = len(list(ev_dir.glob("*.md"))) if ev_dir.is_dir() else 0

        # 4. Reporte y entregables
        report_file = target_dir / "REPORT.md"
        report_present = report_file.is_file()

        deliverables_dir = target_dir / "deliverables"
        exports_dir = target_dir / "exports"
        deliverables_count = 0
        if deliverables_dir.is_dir():
            deliverables_count += len(list(deliverables_dir.iterdir()))
        if exports_dir.is_dir():
            deliverables_count += len(list(exports_dir.iterdir()))

        # 5. Determinación de etapa actual
        current_stage = "scope"
        if not target_yaml:
            current_stage = "scope"
        elif total_findings > 0 and report_present:
            current_stage = "reporting"
        elif total_findings > 0:
            current_stage = "triage"
        elif live_hosts_count > 0:
            current_stage = "probing"
        elif subdomains_count > 0 or latest_job:
            current_stage = "recon"
        else:
            current_stage = "scope"

        # 6. Checkpoints de auditoría pedagógicos
        # Checkpoint 1: Alcance y Autorización
        cp_scope_status = "PASSED" if (target_yaml and (allow_passive or allow_active)) else ("PENDING" if target_yaml else "BLOCKED")
        cp_scope_reason = "Alcance definido y permisos formalmente autorizados." if cp_scope_status == "PASSED" else "Falta autorización explícita (allow_passive o allow_active) en target.yaml."

        # Checkpoint 2: Reconocimiento
        cp_recon_status = "PASSED" if live_hosts_count > 0 else ("IN_PROGRESS" if (subdomains_count > 0 or latest_job) else "NOT_STARTED")
        cp_recon_reason = f"Superficie identificada ({live_hosts_count} hosts vivos, {subdomains_count} subdominios)." if cp_recon_status == "PASSED" else "Sin hosts vivos detectados todavía."

        # Checkpoint 3: Evidencias y Triage
        cp_ev_status = "PASSED" if proven_count > 0 or findings_with_evidence > 0 else ("IN_PROGRESS" if total_findings > 0 else "NOT_STARTED")
        cp_ev_reason = f"Evidencias estructuradas ({proven_count} confirmadas, {findings_with_evidence} vinculadas)." if cp_ev_status == "PASSED" else "Sin hallazgos documentados con evidencia."

        # Checkpoint 4: Reporte Técnico y Cierre
        cp_rep_status = "PASSED" if (report_present and deliverables_count > 0) else ("IN_PROGRESS" if report_present else "NOT_STARTED")
        cp_rep_reason = "Reporte compilado y paquete de entregables exportado." if cp_rep_status == "PASSED" else "Falta compilar o exportar el reporte final."

        checkpoints = [
            {
                "id": "cp_scope",
                "title": "Definición y Autorización de Alcance",
                "stage": "scope",
                "status": cp_scope_status,
                "reason": cp_scope_reason,
                "hint": "Revisa y autoriza target.yaml habilitando permisos pasivos o activos.",
            },
            {
                "id": "cp_recon",
                "title": "Mapeo de Superficie y Hosts Vivos",
                "stage": "recon",
                "status": cp_recon_status,
                "reason": cp_recon_reason,
                "hint": "Ejecuta el reconocimiento o sondeo web sobre los dominios en alcance.",
            },
            {
                "id": "cp_evidence",
                "title": "Documentación y Evidencia de Hallazgos",
                "stage": "triage",
                "status": cp_ev_status,
                "reason": cp_ev_reason,
                "hint": "Crea fichas en evidence/*.md vinculando comandos reproducibles.",
            },
            {
                "id": "cp_report",
                "title": "Informe Técnico de Auditoría y Cierre",
                "stage": "reporting",
                "status": cp_rep_status,
                "reason": cp_rep_reason,
                "hint": "Compila REPORT.md y genera el paquete de entregables.",
            },
        ]

        responses = load_supervision_responses(target_dir)
        for cp in checkpoints:
            resp = responses.get(cp["id"])
            cp["learner_response"] = resp
            cp["is_justified"] = bool(resp and resp.get("justification"))

        return {
            "engagement_id": eng_id,
            "type": eng_type,
            "current_stage": current_stage,
            "scope": {
                "target_yaml_present": bool(target_yaml),
                "scope_txt_present": scope_txt_present,
                "allow_passive": allow_passive,
                "allow_active": allow_active,
                "targets_in_scope_count": total_targets_in_scope,
            },
            "recon": {
                "latest_job_id": latest_job.get("id") if latest_job else None,
                "latest_job_status": latest_job.get("status") if latest_job else None,
                "live_hosts_count": live_hosts_count,
                "subdomains_count": subdomains_count,
            },
            "findings": {
                "total": total_findings,
                "candidates": candidates_count,
                "proven": proven_count,
                "disproved": disproved_count,
                "with_evidence": findings_with_evidence,
                "by_severity": by_severity,
            },
            "evidence": {
                "total_files": total_evidence_files,
            },
            "report": {
                "report_present": report_present,
                "deliverables_count": deliverables_count,
            },
            "checkpoints": checkpoints,
        }

    def export_supervision_report(self, eng_id: str, eng_type: str = "engagement", format: str = "json") -> str:
        """Exporta el informe consolidado de supervisión pedagógica en formato JSON o Markdown."""
        state = self.get_supervision_state(eng_id, eng_type)
        fmt = (format or "json").lower()
        if fmt == "json":
            return json.dumps(state, indent=2, ensure_ascii=False)
        elif fmt in ("markdown", "md"):
            now_iso = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
            lines = [
                f"# Informe de Supervisión Pedagógica: {eng_id}",
                "",
                f"- **Tipo de Proyecto**: {eng_type}",
                f"- **Etapa Actual**: `{state.get('current_stage', 'scope')}`",
                f"- **Fecha de Evaluación**: {now_iso}",
                "",
                "## 1. Checkpoints Pedagógicos Formativos",
                "",
                "| Checkpoint | Etapa | Estado | Evaluación | Guía / Siguiente Acción |",
                "| --- | --- | --- | --- | --- |",
            ]
            for cp in state.get("checkpoints", []):
                cid = cp.get("title", cp.get("id"))
                stage = cp.get("stage", "-")
                status = cp.get("status", "NOT_STARTED")
                reason = (cp.get("reason") or "-").replace("|", "\\|")
                hint = (cp.get("hint") or "-").replace("|", "\\|")
                lines.append(f"| {cid} | {stage} | {status} | {reason} | {hint} |")

            lines.extend([
                "",
                "## 2. Resumen Operacional por Disciplina",
                "",
                f"- **Alcance y Autorización**: target.yaml: {'Presente' if state['scope']['target_yaml_present'] else 'Ausente'} · Pasivo: {'Sí' if state['scope']['allow_passive'] else 'No'} · Activo: {'Sí' if state['scope']['allow_active'] else 'No'} · Objetivos en alcance: {state['scope']['targets_in_scope_count']}",
                f"- **Reconocimiento y Sondeo**: Hosts vivos: {state['recon']['live_hosts_count']} · Subdominios: {state['recon']['subdomains_count']} · Último job: {state['recon']['latest_job_id'] or 'Ninguno'} ({state['recon']['latest_job_status'] or 'N/A'})",
                f"- **Hallazgos y Evidencias**: Total: {state['findings']['total']} (Confirmados: {state['findings']['proven']}, Candidatos: {state['findings']['candidates']}, Descartados: {state['findings']['disproved']}) · Con evidencia vinculada: {state['findings']['with_evidence']} · Archivos de evidencia: {state['evidence']['total_files']}",
                f"- **Informe y Entregables**: REPORT.md: {'Presente' if state['report']['report_present'] else 'Pendiente'} · Entregables exportados: {state['report']['deliverables_count']}",
                "",
            ])
            return "\n".join(lines)
        else:
            raise ValueError(f"Formato no soportado: '{format}'. Debe ser 'json' o 'markdown'.")

    def save_checkpoint_response(
        self,
        eng_id: str,
        checkpoint_id: str,
        justification: str,
        learner_action: Optional[str] = None,
        eng_type: str = "engagement",
    ) -> Dict[str, Any]:
        """Guarda la respuesta pedagógica y justificación del estudiante para un checkpoint."""
        target_dir = workspace_service._resolve_dir(eng_id, eng_type)
        if not target_dir.exists():
            raise FileNotFoundError(f"Engagement {eng_id} no encontrado")
        return save_checkpoint_response(target_dir, checkpoint_id, justification, learner_action)

    def get_cohort_supervision_summary(self) -> Dict[str, Any]:
        """Calcula el resumen agregado de supervisión pedagógica para la cohorte docente a través de todo el workspace (V3-06e)."""
        from seclab_supervision import compute_cohort_supervision_summary
        return compute_cohort_supervision_summary(workspace_service.ws_path)


supervision_service = SupervisionService()

