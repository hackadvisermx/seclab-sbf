import os
import pathlib
import shutil
import socket
import subprocess
from typing import Any, Dict
from app.config import WORKSPACE_DIR


class TelemetryService:
    def get_system_telemetry(self) -> Dict[str, Any]:
        """Obtiene métricas operativas de red, VPN, Tailscale y almacenamiento."""
        # 1. Almacenamiento en Workspace
        disk_stats = {"total_gb": 0.0, "used_gb": 0.0, "free_gb": 0.0, "percent": 0}
        try:
            total, used, free = shutil.disk_usage(str(WORKSPACE_DIR))
            disk_stats = {
                "total_gb": round(total / (1024**3), 2),
                "used_gb": round(used / (1024**3), 2),
                "free_gb": round(free / (1024**3), 2),
                "percent": round((used / total) * 100, 1) if total > 0 else 0,
            }
        except Exception:
            pass

        # 2. Estado de VPN (tun0 y perfiles con vpn_service)
        try:
            from app.services.vpn_service import vpn_service
            tun0_status = vpn_service.get_vpn_status()
        except Exception:
            tun0_status = {"connected": False, "ip": None, "profile": "none", "interface": "tun0"}

        # 3. Estado de Tailscale
        tailscale_status = {"installed": False, "online": False, "ip": None}
        try:
            ts_proc = subprocess.run(["tailscale", "ip", "-4"], capture_output=True, text=True)
            if ts_proc.returncode == 0:
                tailscale_status["installed"] = True
                ts_ip = ts_proc.stdout.strip()
                if ts_ip and ts_ip.startswith("100."):
                    tailscale_status["online"] = True
                    tailscale_status["ip"] = ts_ip
        except Exception:
            pass

        # 4. Hostname e IP local
        hostname = socket.gethostname()

        # 5. Sesiones de tmux activas
        tmux_sessions = []
        try:
            tm_proc = subprocess.run(["tmux", "list-sessions"], capture_output=True, text=True)
            if tm_proc.returncode == 0:
                for line in tm_proc.stdout.splitlines():
                    if line.strip():
                        tmux_sessions.append(line.strip().split(":")[0])
        except Exception:
            pass

        return {
            "hostname": hostname,
            "workspace_path": str(WORKSPACE_DIR),
            "disk": disk_stats,
            "vpn": tun0_status,
            "tailscale": tailscale_status,
            "tmux_sessions": tmux_sessions,
        }


telemetry_service = TelemetryService()
