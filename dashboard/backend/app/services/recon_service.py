import fcntl
import signal
import json
import os
import pathlib
import re
import subprocess
import sys
import threading
from typing import Any, Dict, List, Optional
from app.config import SCRIPTS_DIR, WORKSPACE_DIR, RECON_DB_PATH
from app.core.recon_jobs import ReconJobStore, ACTIVE_STATUSES
from app.core.recon_review import reviewed_plan
from app.core.workspace_paths import project_directory

class ReconService:
    def __init__(self, db_path=None):
        self.py_bin = sys.executable
        if (SCRIPTS_DIR / "pt-recon-pipeline.py").exists():
            self.pipeline_script = SCRIPTS_DIR / "pt-recon-pipeline.py"
        elif pathlib.Path("/usr/local/bin/pt-recon-pipeline").exists():
            self.pipeline_script = pathlib.Path("/usr/local/bin/pt-recon-pipeline")
        else:
            self.pipeline_script = SCRIPTS_DIR / "pt-recon-pipeline.py"
        self.store = ReconJobStore(RECON_DB_PATH if db_path is None else db_path)
        self._lock = threading.Lock()
        self._processes = {}
        self._threads = {}
        self._lease = None
        self._closing = False

    def startup(self):
        with self._lock:
            if self._lease is not None:
                return
            fd = os.open(str(self.store.path) + '.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
            try:
                os.fchmod(fd, 0o600)
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                self.store.recover()
            except BaseException:
                os.close(fd)
                raise
            self._lease = fd
            self._closing = False

    @staticmethod
    def _stop_processes(processes):
        # Callers hold _lock, so workers cannot reap/reuse the group leader's
        # PID before escalation. Signal descendants even if the leader exited.
        for proc in processes:
            try:
                os.killpg(proc.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
        if processes:
            threading.Event().wait(2)
        for proc in processes:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass

    def shutdown(self):
        with self._lock:
            self._closing = True
            for key in self._threads:
                self.store.request_cancel(key)
            self._stop_processes(list(self._processes.values()))
            threads = list(self._threads.values())
        for thread in threads:
            thread.join(timeout=5)
        with self._lock:
            if any(thread.is_alive() for thread in threads):
                raise RuntimeError('No se pudo detener el reconocimiento durante el cierre.')
            if self._lease is not None:
                os.close(self._lease)
                self._lease = None

    def get_target_dir(self, engagement_id: str, engagement_type: str = "engagement") -> Optional[pathlib.Path]:
        p = project_directory(WORKSPACE_DIR, engagement_id, engagement_type)
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
        probe_observations_path = recon_dir / "probe_observations.jsonl"

        # Leer resumen estructurado si existe
        summary: Dict[str, Any] = {
            "timestamp": None,
            "in_scope_domains": [],
            "subdomains_count": 0,
            "subdomains_discarded_out_of_scope": 0,
            "subdomains_new_count": 0,
            "live_hosts_count": 0,
            "live_hosts_new_count": 0,
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

        # Resultados crudos del sondeo HTTP/HTTPS (una fila por intento host+esquema)
        probe_results: List[Dict[str, Any]] = []
        if probe_observations_path.is_file():
            try:
                for line in probe_observations_path.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        probe_results.append(json.loads(line))
                    except ValueError:
                        continue
            except Exception:
                pass

        job = self.store.get((engagement_type, engagement_id)) or {
            'status': 'idle', 'stage': None, 'dry_run': False,
            'started_at': None, 'finished_at': None, 'error': None,
        }

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

        progress = None
        progress_path = recon_dir / 'progress.json'
        try:
            candidate = json.loads(progress_path.read_text(encoding='utf-8'))
            if isinstance(candidate, dict) and job.get('run_id') and candidate.get('run_id') == job['run_id']:
                progress = candidate
        except (OSError, ValueError):
            pass

        return {
            "progress": progress,
            "engagement_id": engagement_id,
            "engagement_type": engagement_type,
            "job": job,
            "summary": summary,
            "configured_domains": in_scope_domains,
            "discarded_out_of_scope": discarded_items,
            "probe_results": probe_results,
            "recent_logs": recent_logs,
            "has_recon_data": summary_path.is_file() or (recon_dir / "subdomains.txt").is_file(),
        }

    def get_history(self, engagement_id, engagement_type='engagement', limit=25, before=None):
        if not self.get_target_dir(engagement_id, engagement_type):
            return {'error': 'Proyecto no encontrado.'}
        return {'engagement_id': engagement_id, 'engagement_type': engagement_type,
                **self.store.history((engagement_type, engagement_id), limit, before)}

    @staticmethod
    def _completed_summary(target_dir, run_id):
        # A stale summary must never become provenance for a later job.
        path = target_dir / 'recon' / 'summary.json'
        try:
            if path.parent.is_symlink() or path.is_symlink() or path.stat().st_size > 2 * 1024 * 1024:
                return None
            summary = json.loads(path.read_text(encoding='utf-8'))
            if isinstance(summary, dict) and summary.get('run_id') == run_id:
                return summary
        except (OSError, ValueError, AttributeError):
            pass
        return None

    @classmethod
    def _completed_scope_revision(cls, target_dir, run_id):
        summary = cls._completed_summary(target_dir, run_id) or {}
        revision = summary.get('scope_revision')
        return revision if isinstance(revision, str) and re.fullmatch(r'[a-f0-9]{64}', revision) else None

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

    def preview_pipeline(self, engagement_id, stage='all', dry_run=False, engagement_type='engagement'):
        if stage not in ('all', 'subdomains', 'probe', 'urls', 'patterns'):
            return {'success': False, 'error': 'Etapa de reconocimiento no válida.'}
        target = self.get_target_dir(engagement_id, engagement_type)
        if target is None:
            return {'success': False, 'error': 'Directorio del engagement no encontrado.'}
        command = [self.py_bin, str(self.pipeline_script), 'preview', str(target), '--stage', stage]
        if dry_run:
            command.append('--dry-run')
        try:
            result = subprocess.run(command, capture_output=True, text=True, timeout=10)
            if result.returncode:
                return {'success': False, 'error': (result.stderr or 'No se pudo revisar el plan.')[:2000]}
            preview = json.loads(result.stdout)
            if not isinstance(preview, dict) or preview.get('success') is not True or not isinstance(preview.get('plan_revision'), str):
                raise ValueError('Contrato de vista previa inválido.')
            return preview
        except (OSError, subprocess.TimeoutExpired, ValueError) as error:
            return {'success': False, 'error': 'No se pudo revisar el plan: ' + str(error)[:500]}

    def run_pipeline(
        self,
        engagement_id: str,
        stage: str = "all",
        dry_run: bool = False,
        engagement_type: str = "engagement",
        expected_plan: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Inicia el pipeline de reconocimiento en un hilo en segundo plano."""
        if stage not in ('all', 'subdomains', 'probe', 'urls', 'patterns'):
            return {"success": False, "error": "Etapa de reconocimiento no válida."}
        review = None
        if expected_plan:
            preview = self.preview_pipeline(engagement_id, stage, dry_run, engagement_type)
            if not preview.get('success') or preview.get('plan_revision') != expected_plan or not preview.get('can_start'):
                return {'success': False, 'error': 'El plan cambió o está bloqueado; revisa targets, permisos y límites antes de iniciar.'}
            try:
                review = reviewed_plan(preview)
            except (KeyError, TypeError, ValueError):
                return {'success': False, 'error': 'La revisión está incompleta; vuelve a revisar antes de iniciar.'}
        with self._lock:
            if self._closing:
                return {'success': False, 'error': 'El dashboard se está cerrando.'}
            target_dir = self.get_target_dir(engagement_id, engagement_type)
            if not target_dir:
                return {'success': False, 'error': f'Directorio no encontrado: {engagement_id}'}
            job_key = (engagement_type, engagement_id)
            recon_dir = target_dir / 'recon'
            recon_dir.mkdir(parents=True, exist_ok=True)
            log_path = recon_dir / 'recon.log'
            try:
                job = self.store.begin(job_key, stage, dry_run, reviewed_plan=review)
            except (RuntimeError, ValueError) as error:
                return {'success': False, 'error': str(error), 'job': self.store.get(job_key)}
            thread = threading.Thread(target=self._execute_pipeline_worker,
                args=(job_key, target_dir, stage, dry_run, log_path, job['run_id'], expected_plan), daemon=True)
            self._threads[job_key] = thread
            try:
                thread.start()
            except Exception as error:
                self._threads.pop(job_key, None)
                self.store.finish(job_key, job['run_id'], 'failed', str(error))
                return {'success': False, 'error': 'No se pudo iniciar el reconocimiento.'}
        return {'success': True, 'message': 'Reconocimiento iniciado.', 'job': job}

    def cancel_pipeline(self, engagement_id, engagement_type='engagement'):
        with self._lock:
            if not self.get_target_dir(engagement_id, engagement_type):
                return {'success': False, 'error': 'Proyecto no encontrado.', 'code': 404}
            key = (engagement_type, engagement_id)
            job = self.store.get(key)
            if not job or job['status'] not in ACTIVE_STATUSES:
                return {'success': False, 'error': 'No hay reconocimiento activo para cancelar.', 'code': 409}
            self.store.request_cancel(key)
            proc = self._processes.get(key)
            if proc is not None:
                self._stop_processes([proc])
            return {'success': True, 'message': 'Cancelación solicitada.', 'job': self.store.get(key)}

    def delete_engagement(self, engagement_id: str, engagement_type: str = 'engagement'):
        from app.services.workspace_sync import workspace_service
        key = (engagement_type, engagement_id)
        with self._lock:
            if (self.store.get(key) or {}).get('status') in ACTIVE_STATUSES:
                raise RuntimeError('El reconocimiento está activo. Espera a que termine o cancélalo antes de eliminar el proyecto.')
            entry = workspace_service.delete_engagement(engagement_id, engagement_type)
            self.store.delete(key)
            return entry

    def restore_engagement(self, entry_id, engagement_id, engagement_type='engagement'):
        from app.services.workspace_sync import workspace_service
        key = (engagement_type, engagement_id)
        with self._lock:
            if (self.store.get(key) or {}).get('status') in ACTIVE_STATUSES:
                raise RuntimeError('El reconocimiento está activo. Espera a que termine o cancélalo antes de restaurar el proyecto.')
            entry = workspace_service.restore_engagement(entry_id, engagement_id, engagement_type)
            self.store.delete(key)
            return entry

    def _execute_pipeline_worker(self, job_key, target_dir, stage, dry_run, log_path, run_id, expected_plan=None):
        cmd = [self.py_bin, str(self.pipeline_script), 'run', str(target_dir), '--stage', stage]
        if expected_plan:
            cmd.extend(['--expected-plan', expected_plan])
        if dry_run:
            cmd.append('--dry-run')
        proc = None
        try:
            with open(log_path, 'a', encoding='utf-8') as log_f:
                with self._lock:
                    job = self.store.get(job_key)
                    if not job or job['run_id'] != run_id:
                        return
                    if job['status'] != 'running' or self._closing:
                        self.store.finish(job_key, run_id, 'cancelled')
                        return
                    log_f.write(f'\n--- [SECLAB RECON LAUNCH: {run_id} | Stage: {stage} | DryRun: {dry_run}] ---\n')
                    log_f.flush()
                    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                        text=True, bufsize=1, start_new_session=True,
                        env={**os.environ, 'SECLAB_RECON_RUN_ID': run_id},
                        pass_fds=(() if self._lease is None else (self._lease,)))
                    self._processes[job_key] = proc
                if proc.stdout:
                    with proc.stdout:
                        for line in proc.stdout:
                            log_f.write(line)
                            log_f.flush()
                with self._lock:
                    proc.wait()
                    job = self.store.get(job_key)
                    cancelled = job and job['status'] == 'cancelling'
                    status = 'cancelled' if cancelled else (('simulated' if dry_run else 'completed') if proc.returncode == 0 else 'failed')
                    error = None if cancelled or proc.returncode == 0 else f'Código de salida: {proc.returncode}'
                    outcome = self._completed_summary(target_dir, run_id) or {}
                    reason = outcome.get('error')
                    if status == 'failed' and outcome.get('status') == 'failed' and outcome.get('failure_kind') == 'scope_guard' and isinstance(reason, str) and reason.strip():
                        status, error = 'blocked', reason[:2000]
                    self.store.finish(job_key, run_id, status, error, self._completed_scope_revision(target_dir, run_id))
                    self._processes.pop(job_key, None)
        except Exception as error:
            with self._lock:
                if proc is not None:
                    self._stop_processes([proc])
                    proc.wait()
                    self._processes.pop(job_key, None)
                job = self.store.get(job_key)
                cancelled = job and job['status'] == 'cancelling'
                self.store.finish(job_key, run_id, 'cancelled' if cancelled else 'failed', None if cancelled else str(error))
        finally:
            with self._lock:
                if self._threads.get(job_key) is threading.current_thread():
                    self._threads.pop(job_key, None)


recon_service = ReconService()
