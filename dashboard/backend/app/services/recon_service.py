import datetime
import json
import os
import pathlib
import subprocess
import sys
import threading
from typing import Any, Dict, List, Optional
from app.config import SCRIPTS_DIR, WORKSPACE_DIR

class ReconService:
    def __init__(self):
        self.py_bin = sys.executable
        self.pipeline_script = SCRIPTS_DIR / "pt-recon-pipeline.py"
        # Estructura: { engagement_id: { "status": "running"|"completed"|"failed"|"idle", ... } }
        self._jobs: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()

    def get_target_dir(self, engagement_id: str, engagement_type: str = "engagement") -> Optional[pathlib.Path]:
        folder = "engagements" if engagement_type == "engagement" else "retos"
        p = WORKSPACE_DIR / folder / engagement_id
        if p.is_dir():
            return p
        return None

    def get_status(self, engagement_id: str, engagement_type: str = "engagement") -> Dict[str, Any]:
        """Retorna el estado actual del reconocimiento para un engagement o reto."""
        target_dir = self.get_target_dir(engagement_id, engagement_type)
        if not target_dir:
            return {"error": f"Directorio no encontrado: {engagement_id}"}

        recon_dir = target_dir / "recon"
        summary_path = recon_dir / "summary.json"
        log_path = recon_dir / "recon.log"
        discarded_path = recon_dir / "out_of_scope_discarded.txt"

        # Leer resumen estructurado si existe
        summary: Dict[str, Any] = {
            "timestamp": None,
            "in_scope_domains": [],
            "subdomains_count": 0,
            "subdomains_discarded_out_of_scope": 0,
            "live_hosts_count": 0,
            "urls_count": 0,
            "js_files_count": 0,
            "gf_patterns": {},
        }
        if summary_path.is_file():
            try:
                summary = json.loads(summary_path.read_text(encoding="utf-8"))
            except Exception:
                pass

        # Descartados por Scope Guard
        discarded_items: List[Dict[str, str]] = []
        if discarded_path.is_file():
            try:
                for line in discarded_path.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    if " -> " in line:
                        tgt, rest = line.split(" -> ", 1)
                        discarded_items.append({"target": tgt.strip(), "reason": rest.strip()})
                    else:
                        discarded_items.append({"target": line, "reason": "OUT_OF_SCOPE"})
            except Exception:
                pass

        # Comprobar trabajo en memoria
        with self._lock:
            job = self._jobs.get(engagement_id, {
                "status": "idle",
                "stage": None,
                "dry_run": False,
                "started_at": None,
                "finished_at": None,
            })

        # Últimas líneas de log
        recent_logs = []
        if log_path.is_file():
            try:
                lines = log_path.read_text(encoding="utf-8", errors="ignore").splitlines()
                recent_logs = lines[-100:]
            except Exception:
                pass

        # Leer dominios de alcance base configurados
        in_scope_domains = []
        try:
            from app.services.workspace_sync import workspace_service
            scope_data = workspace_service.get_target_yaml(engagement_id, engagement_type) or {}
            in_scope_domains = scope_data.get("scope", {}).get("in_scope", {}).get("domains", [])
        except Exception:
            pass

        return {
            "engagement_id": engagement_id,
            "engagement_type": engagement_type,
            "job": job,
            "summary": summary,
            "configured_domains": in_scope_domains,
            "discarded_out_of_scope": discarded_items,
            "recent_logs": recent_logs,
            "has_recon_data": summary_path.is_file() or (recon_dir / "subdomains.txt").is_file(),
        }

    def get_log(self, engagement_id: str, lines: int = 200, engagement_type: str = "engagement") -> str:
        """Retorna el contenido del archivo de bitácora recon.log."""
        target_dir = self.get_target_dir(engagement_id, engagement_type)
        if not target_dir:
            return ""
        log_path = target_dir / "recon" / "recon.log"
        if not log_path.is_file():
            return ""
        try:
            all_lines = log_path.read_text(encoding="utf-8", errors="ignore").splitlines()
            return "\n".join(all_lines[-lines:])
        except Exception:
            return ""

    def run_pipeline(
        self,
        engagement_id: str,
        stage: str = "all",
        dry_run: bool = False,
        engagement_type: str = "engagement",
    ) -> Dict[str, Any]:
        """Inicia el pipeline de reconocimiento en un hilo en segundo plano."""
        target_dir = self.get_target_dir(engagement_id, engagement_type)
        if not target_dir:
            return {"success": False, "error": f"Directorio no encontrado: {engagement_id}"}

        with self._lock:
            existing = self._jobs.get(engagement_id)
            if existing and existing.get("status") == "running":
                return {
                    "success": False,
                    "error": "Ya hay una tarea de reconocimiento ejecutándose en este engagement.",
                    "job": existing,
                }

            recon_dir = target_dir / "recon"
            recon_dir.mkdir(parents=True, exist_ok=True)
            log_path = recon_dir / "recon.log"

            now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
            job_info = {
                "status": "running",
                "stage": stage,
                "dry_run": dry_run,
                "started_at": now_iso,
                "finished_at": None,
                "error": None,
            }
            self._jobs[engagement_id] = job_info

        # Iniciar hilo de ejecución desacoplado
        t = threading.Thread(
            target=self._execute_pipeline_worker,
            args=(engagement_id, target_dir, stage, dry_run, log_path),
            daemon=True,
        )
        t.start()

        return {
            "success": True,
            "message": f"Pipeline de reconocimiento iniciado (etapa: {stage}, dry_run: {dry_run})",
            "job": job_info,
        }

    def _execute_pipeline_worker(
        self,
        engagement_id: str,
        target_dir: pathlib.Path,
        stage: str,
        dry_run: bool,
        log_path: pathlib.Path,
    ):
        """Worker en segundo plano que ejecuta pt-recon-pipeline.py y registra logs."""
        cmd = [self.py_bin, str(self.pipeline_script), "run", str(target_dir), "--stage", stage]
        if dry_run:
            cmd.append("--dry-run")

        try:
            with open(log_path, "a", encoding="utf-8") as log_f:
                ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
                log_f.write(f"\n--- [SECLAB RECON LAUNCH: {ts} | Stage: {stage} | DryRun: {dry_run}] ---\n")
                log_f.flush()

                proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    universal_newlines=True,
                )

                if proc.stdout:
                    for line in proc.stdout:
                        log_f.write(line)
                        log_f.flush()

                proc.wait()

            with self._lock:
                status = "completed" if proc.returncode == 0 else "failed"
                self._jobs[engagement_id]["status"] = status
                self._jobs[engagement_id]["finished_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
                if proc.returncode != 0:
                    self._jobs[engagement_id]["error"] = f"Código de salida: {proc.returncode}"

        except Exception as e:
            with self._lock:
                self._jobs[engagement_id]["status"] = "failed"
                self._jobs[engagement_id]["finished_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
                self._jobs[engagement_id]["error"] = str(e)


recon_service = ReconService()
