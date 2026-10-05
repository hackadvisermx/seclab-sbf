import json
import os
import pathlib
import subprocess
import sys
from typing import Any, Dict, Optional
from app.config import SCRIPTS_DIR

ALLOWED_PROFILES = {"tryhackme", "hackthebox", "client"}
PROFILE_ALIASES = {
    "try": "tryhackme",
    "thm": "tryhackme",
    "htb": "hackthebox",
    "cli": "client",
}


class VpnService:
    def __init__(self):
        self.control_dir = pathlib.Path(os.environ.get("VPN_CONTROL_DIR", "/var/lib/seclab/vpn-control"))
        self.control_sock = self.control_dir / "control.sock"
        installed_control = pathlib.Path("/usr/local/bin/vpn-control")
        self.vpn_control_script = installed_control if installed_control.is_file() else SCRIPTS_DIR / "vpn-control.py"

    def canonical_profile(self, profile: str) -> Optional[str]:
        p = profile.strip().lower()
        if p in ALLOWED_PROFILES:
            return p
        return PROFILE_ALIASES.get(p)

    def get_tun0_ip(self) -> Optional[str]:
        """Obtiene la IP asignada a tun0 usando ip addr o ifconfig."""
        try:
            proc = subprocess.run(["ip", "addr", "show", "tun0"], capture_output=True, text=True, timeout=2)
            if proc.returncode == 0:
                for line in proc.stdout.splitlines():
                    line = line.strip()
                    if line.startswith("inet "):
                        return line.split()[1].split("/")[0]
        except Exception:
            pass

        try:
            proc = subprocess.run(["ifconfig", "tun0"], capture_output=True, text=True, timeout=2)
            if proc.returncode == 0:
                for line in proc.stdout.splitlines():
                    if "inet " in line:
                        parts = line.split("inet ")
                        if len(parts) > 1:
                            return parts[1].split()[0]
        except Exception:
            pass

        return None

    def get_vpn_status(self) -> Dict[str, Any]:
        """Obtiene el estado completo y verificado de la VPN en el laboratorio."""
        tun0_ip = self.get_tun0_ip()
        tun0_present = tun0_ip is not None or pathlib.Path("/sys/class/net/tun0").exists()

        socket_available = self.control_sock.is_socket()
        result = self._execute_vpn_control("status") if socket_available else None
        state = {}
        if result and result["success"]:
            state = dict(line.split("=", 1) for line in result["stdout"].splitlines() if "=" in line)
        active_profile = state.get("active", "none")
        pid_parts = state.get("pid", "").split()
        pid_val = int(pid_parts[0]) if pid_parts and pid_parts[0].isdigit() else None
        pid_running = pid_val is not None and pid_parts[1:] == ["running"] and active_profile in ALLOWED_PROFILES
        connected = pid_running and tun0_ip is not None

        return {
            "connected": connected,
            "connecting": pid_running and not connected,
            "profile": active_profile if pid_running else "none",
            "ip": tun0_ip if connected else None,
            "interface": "tun0",
            "tun0_present": tun0_present,
            "control_socket": socket_available,
            "pid": pid_val,
            "pid_running": pid_running,
            "control_error": result["stderr"] if result and not result["success"] else None,
            "allowed_profiles": sorted(list(ALLOWED_PROFILES)),
        }

    def _execute_vpn_control(self, action: str, profile: Optional[str] = None, credentials=None) -> Dict[str, Any]:
        """Solicita una acción al daemon con los permisos de tester."""
        if not self.vpn_control_script.exists():
            return {
                "success": False,
                "code": 78,
                "stdout": "",
                "stderr": f"Script {self.vpn_control_script} no encontrado",
            }

        cmd = [sys.executable, str(self.vpn_control_script), "client", action]
        if profile:
            cmd.append(profile)
        env = {key: value for key, value in os.environ.items() if key not in {"VPN_AUTH_USER", "VPN_AUTH_PASSWORD"}}
        if credentials:
            env["VPN_AUTH_USER"], env["VPN_AUTH_PASSWORD"] = credentials

        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=65, env=env)
            return {
                "success": proc.returncode == 0,
                "code": proc.returncode,
                "stdout": proc.stdout.strip(),
                "stderr": proc.stderr.strip(),
            }
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "code": 124,
                "stdout": "",
                "stderr": "Tiempo de espera agotado al comunicar con vpn-control",
            }
        except Exception as e:
            return {
                "success": False,
                "code": 1,
                "stdout": "",
                "stderr": str(e),
            }

    def get_saved_credentials(self, profile: str) -> Optional[Dict[str, str]]:
        """Recupera credenciales guardadas en el Vault cifrado para un perfil VPN."""
        canonical = self.canonical_profile(profile)
        if not canonical:
            return None
        try:
            from app.services.vault_service import vault_service
            raw = vault_service.get_raw_key(f"vpn_{canonical}")
            if raw:
                data = json.loads(raw)
                return {"username": data.get("username", ""), "password": data.get("password", "")}
        except Exception:
            pass
        return None

    def save_credentials(self, profile: str, username: str, password: str) -> bool:
        """Guarda credenciales de VPN en el Vault cifrado con AES-256-GCM."""
        canonical = self.canonical_profile(profile)
        if not canonical:
            return False
        try:
            from app.services.vault_service import vault_service
            from app.models.schemas import ApiKeyCreate
            payload = json.dumps({"username": username, "password": password})
            vault_service.upsert_key(
                ApiKeyCreate(
                    provider=f"vpn_{canonical}",
                    label=f"Credenciales VPN ({canonical})",
                    service_type="vpn",
                    api_key=payload,
                )
            )
            return True
        except Exception:
            return False

    def delete_saved_credentials(self, profile: str) -> bool:
        """Elimina credenciales guardadas de VPN del Vault."""
        canonical = self.canonical_profile(profile)
        if not canonical:
            return False
        try:
            from app.services.vault_service import vault_service
            return vault_service.delete_key(f"vpn_{canonical}")
        except Exception:
            return False

    def list_saved_profiles(self) -> Dict[str, Any]:
        """Lista qué perfiles tienen credenciales registradas en el Vault."""
        res = {}
        for p in ALLOWED_PROFILES:
            creds = self.get_saved_credentials(p)
            res[p] = {
                "has_credentials": creds is not None,
                "username": creds["username"] if creds else None,
            }
        return res

    def _resolve_credentials(self, canonical: str, username: Optional[str], password: Optional[str]):
        if password is None:
            saved = self.get_saved_credentials(canonical)
            if saved and (username is None or username == saved.get("username")):
                username, password = saved.get("username"), saved.get("password")
            elif username is None:
                return None
        for value in (username, password):
            if not isinstance(value, str) or not 0 < len(value) <= 256 or any(ch in value for ch in ("\n", "\r", "\x00")):
                raise ValueError("Usuario y contraseña requeridos, máximo 256 caracteres y sin saltos de línea.")
        return username, password

    def _connect_profile(self, action, profile, username, password, save_in_vault):
        canonical = self.canonical_profile(profile)
        if not canonical:
            return {"success": False, "message": f"Perfil '{profile}' no autorizado. Use: tryhackme, hackthebox o client."}
        try:
            credentials = self._resolve_credentials(canonical, username, password)
        except ValueError as error:
            return {"success": False, "message": str(error)}
        if save_in_vault and credentials and not self.save_credentials(canonical, *credentials):
            return {"success": False, "message": "No se pudieron guardar las credenciales en el Vault."}
        result = self._execute_vpn_control(action, canonical, credentials)
        return {
            "success": result["success"],
            "profile": canonical,
            "message": f"Conexión VPN iniciada: {canonical}" if result["success"] else (result["stderr"] or result["stdout"] or "Error al conectar"),
            "raw": result,
        }

    def connect(
        self,
        profile: str,
        username: Optional[str] = None,
        password: Optional[str] = None,
        save_in_vault: bool = False,
    ) -> Dict[str, Any]:
        """Conecta un perfil VPN validado, con o sin credenciales de usuario/contraseña."""
        return self._connect_profile("connect", profile, username, password, save_in_vault)

    def disconnect(self) -> Dict[str, Any]:
        """Solicita al daemon desconectar y limpiar el estado privado de root."""
        res = self._execute_vpn_control("disconnect")

        return {
            "success": res["success"],
            "message": "VPN apagada" if res["success"] else (res["stderr"] or res["stdout"] or "Error al desconectar"),
            "raw": res,
        }

    def switch(
        self,
        profile: str,
        username: Optional[str] = None,
        password: Optional[str] = None,
        save_in_vault: bool = False,
    ) -> Dict[str, Any]:
        """Conmuta al perfil VPN especificado con o sin credenciales."""
        return self._connect_profile("switch", profile, username, password, save_in_vault)


vpn_service = VpnService()
