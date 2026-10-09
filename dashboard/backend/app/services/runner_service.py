import json
import os
import pathlib
import subprocess
import sys
from typing import Any, Dict, Optional
from app.config import SCRIPTS_DIR, REPO_ROOT, WORKSPACE_DIR, DATA_DIR
from app.models.schemas import ScopeCheckResponse


class RunnerService:
    def __init__(self):
        self.py_bin = sys.executable

    def _script(self, source_name: str, installed_name: str) -> pathlib.Path:
        source = SCRIPTS_DIR / source_name
        return source if source.is_file() else SCRIPTS_DIR / installed_name

    def check_scope(self, target: str, config_or_dir_path: str) -> ScopeCheckResponse:
        """Invoca pt-scope-validator.py para verificar si un target está autorizado o prohibido."""
        script = self._script("pt-scope-validator.py", "pt-scope-validator")
        if not script.exists():
            return ScopeCheckResponse(
                target=target,
                normalized=target,
                allowed=False,
                status="INVALID_INPUT",
                reason=f"Herramienta de alcance no encontrada: {script.name}",
            )

        cmd = [self.py_bin, str(script), "check", str(config_or_dir_path), target]
        proc = subprocess.run(cmd, capture_output=True, text=True)

        stdout = proc.stdout.strip()
        stderr = proc.stderr.strip()
        code = proc.returncode

        # Código 0: DENTRO DE ALCANCE
        # Código 1: FUERA DE ALCANCE O ERROR
        # Código 2: USO / CONFIG ERROR
        allowed = (code == 0)

        status = "ALLOWED" if allowed else "BLOCKED_NOT_IN_SCOPE"
        if "FUERA DE ALCANCE" in stdout or "excluido" in stdout.lower():
            status = "BLOCKED_EXCLUSION"

        reason = stdout or stderr or ("Objetivo autorizado" if allowed else "Objetivo no contemplado en target.yaml")

        return ScopeCheckResponse(
            target=target,
            normalized=target.strip().lower(),
            allowed=allowed,
            status=status,
            reason=reason,
        )

    def compile_report(self, engagement_dir: str, output_file: Optional[str] = None) -> Dict[str, Any]:
        """Compila el informe técnico y ejecutivo utilizando pt-report-compiler.py."""
        script = self._script("pt-report-compiler.py", "pt-report-compiler")
        target_dir = pathlib.Path(engagement_dir)

        if not output_file:
            output_file = str(target_dir / "REPORT.md")

        cmd = [self.py_bin, str(script), "build", str(target_dir), str(output_file)]
        proc = subprocess.run(cmd, capture_output=True, text=True)

        success = (proc.returncode == 0)
        report_content = ""
        if success and pathlib.Path(output_file).exists():
            report_content = pathlib.Path(output_file).read_text(encoding="utf-8", errors="ignore")

        return {
            "success": success,
            "output_file": str(output_file),
            "log": proc.stdout + ("\n" + proc.stderr if proc.stderr else ""),
            "content": report_content,
        }

    def get_audit_checklist(self, engagement_dir: str) -> Dict[str, Any]:
        """Obtiene la cobertura de las 8 disciplinas metodológicas mediante pt-audit-checklist.py -j."""
        script = self._script("pt-audit-checklist.py", "pt-audit-checklist")
        cmd = [self.py_bin, str(script), "-j", str(engagement_dir)]
        proc = subprocess.run(cmd, capture_output=True, text=True)

        try:
            return json.loads(proc.stdout)
        except Exception:
            return {
                "overall_score": 0,
                "coverage_pct": 0,
                "areas": [],
                "raw_output": proc.stdout or proc.stderr,
            }

    def get_audit_next_step(self, engagement_dir: str, prompt_mode: bool = False) -> Dict[str, Any]:
        """Obtiene el próximo paso recomendado por pt-audit-next.py."""
        script = self._script("pt-audit-next.py", "pt-next")
        args = ["-j"]
        if prompt_mode:
            args.append("-p")
        cmd = [self.py_bin, str(script)] + args + [str(engagement_dir)]
        proc = subprocess.run(cmd, capture_output=True, text=True, env={**os.environ,
            "WORKSPACE_DIR": str(WORKSPACE_DIR), "SECLAB_DATA_DIR": str(DATA_DIR)})

        try:
            return json.loads(proc.stdout)
        except Exception:
            return {
                "recommendation": proc.stdout.strip() or "No se pudo generar recomendación.",
                "raw": proc.stdout or proc.stderr,
            }

    def pack_engagement(self, engagement_dir: str, sanitize: bool = True, output_path: Optional[str] = None) -> Dict[str, Any]:
        """Empaqueta y calcula hashes SHA-256 usando pt-engagement-packer.py."""
        script = self._script("pt-engagement-packer.py", "pt-engagement-packer")
        cmd = [self.py_bin, str(script), "pack", str(engagement_dir), "-j"]
        if sanitize:
            cmd.append("--sanitize")
        if output_path:
            cmd.extend(["-o", str(output_path)])

        proc = subprocess.run(cmd, capture_output=True, text=True)
        try:
            result = json.loads(proc.stdout)
        except (ValueError, TypeError):
            result = {}
        if not isinstance(result, dict):
            result = {}
        return {
            "success": proc.returncode == 0 and result.get("status") == "success",
            "stdout": proc.stdout,
            "stderr": proc.stderr,
            "archive_path": result.get("archive_path") if proc.returncode == 0 else None,
        }

    def get_agent_context(self, engagement_dir: str, skill_name: Optional[str] = None) -> str:
        """Sintetiza el contexto del proyecto y directivas de skill mediante pt-agent-context.py."""
        script = self._script("pt-agent-context.py", "pt-agent-context")
        cmd = [self.py_bin, str(script), str(engagement_dir)]
        if skill_name:
            cmd.append(skill_name)
        proc = subprocess.run(cmd, capture_output=True, text=True, env={**os.environ,
            "WORKSPACE_DIR": str(WORKSPACE_DIR), "SECLAB_DATA_DIR": str(DATA_DIR)})
        return proc.stdout or proc.stderr


runner_service = RunnerService()
