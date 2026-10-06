import os
import pathlib
import shutil
import socket
import subprocess
from typing import Any, Dict
from app.config import WORKSPACE_DIR


class TelemetryService:
    def get_local_ip(self) -> str:
        """Determina la IP local del laboratorio (interfaz LAN/Docker), descartando loopback, tun y tailscale."""
        # 1. Intentar inspeccionar interfaces IPv4 vía 'ip -4 addr show' (Linux/contenedor)
        try:
            proc = subprocess.run(["ip", "-4", "addr", "show"], capture_output=True, text=True, timeout=2)
            if proc.returncode == 0:
                current_iface = None
                for line in proc.stdout.splitlines():
                    line = line.strip()
                    if line and line[0].isdigit() and ":" in line:
                        parts = line.split(":")
                        if len(parts) >= 2:
                            current_iface = parts[1].strip().split("@")[0]
                    elif line.startswith("inet ") and current_iface:
                        if (
                            current_iface == "lo"
                            or current_iface.startswith(("tun", "tap", "tailscale", "wg", "docker", "br-"))
                        ):
                            continue
                        ip = line.split()[1].split("/")[0]
                        if not ip.startswith("127."):
                            return ip
        except Exception:
            pass

        # 2. Intentar 'hostname -I' (Linux)
        try:
            proc = subprocess.run(["hostname", "-I"], capture_output=True, text=True, timeout=2)
            if proc.returncode == 0 and proc.stdout.strip():
                ips = [x for x in proc.stdout.strip().split() if not x.startswith("127.")]
                if ips:
                    return ips[0]
        except Exception:
            pass

        # 3. Fallback mediante socket UDP (no envía tráfico a la red)
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("10.255.255.255", 1))
                ip = s.getsockname()[0]
                if ip and not ip.startswith("127."):
                    return ip
        except Exception:
            pass

        # 4. Fallback estándar gethostbyname
        try:
            ip = socket.gethostbyname(socket.gethostname())
            if ip and not ip.startswith("127."):
                return ip
        except Exception:
            pass

        return "127.0.0.1"

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
        local_ip = self.get_local_ip()

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
            "local_ip": local_ip,
            "workspace_path": str(WORKSPACE_DIR),
            "disk": disk_stats,
            "vpn": tun0_status,
            "tailscale": tailscale_status,
            "tmux_sessions": tmux_sessions,
        }


telemetry_service = TelemetryService()
