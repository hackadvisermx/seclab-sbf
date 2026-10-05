import json
import os
import pathlib
import re
import socket
import subprocess
import sys
from typing import Any, Dict, Optional
from app.config import SCRIPTS_DIR, REPO_ROOT

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
        self.state_dir = pathlib.Path(os.environ.get("VPN_STATE_DIR", "/var/lib/seclab/vpn"))
        self.active_file = self.state_dir / "active"
        self.pid_file = self.state_dir / "openvpn.pid"
        self.vpn_control_script = SCRIPTS_DIR / "vpn-control.py"

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

        active_profile = "none"
        if self.active_file.is_file():
            try:
                content = self.active_file.read_text(encoding="utf-8").strip()
                if content:
                    active_profile = content
            except Exception:
                pass

        # Si hay IP pero active_file no existe (ej. host o docker bridge manual)
        if tun0_present and active_profile == "none":
            active_profile = "active"

        # Verificar socket de control
        socket_available = self.control_sock.exists()

        # Verificar PID de OpenVPN
        pid_running = False
        pid_val = None
        if self.pid_file.is_file():
            try:
                val = self.pid_file.read_text(encoding="utf-8").strip()
                if val.isdigit():
                    pid_val = int(val)
                    # Comprobar si el proceso sigue vivo
                    try:
                        os.kill(pid_val, 0)
                        pid_running = True
                    except OSError:
                        pid_running = False
            except Exception:
                pass

        connected = tun0_present or pid_running or (active_profile not in ("none", ""))

        return {
            "connected": connected,
            "profile": active_profile,
            "ip": tun0_ip,
            "interface": "tun0",
            "tun0_present": tun0_present,
            "control_socket": socket_available,
            "pid": pid_val,
            "pid_running": pid_running,
            "allowed_profiles": sorted(list(ALLOWED_PROFILES)),
        }

    def _execute_vpn_control(self, action: str, profile: Optional[str] = None) -> Dict[str, Any]:
        """Invoca vpn-control.py client <action> [profile]."""
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

        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=65)
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
            payload = json.dumps({"username": username.strip(), "password": password.strip()})
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

    def _prepare_auth_file(self, canonical: str, username: Optional[str] = None, password: Optional[str] = None) -> bool:
        """Crea el archivo efímero .auth con permisos 0600 en el directorio de estado."""
        u = username
        pw = password
        if not (u and pw):
            saved = self.get_saved_credentials(canonical)
            if saved:
                u = saved.get("username")
                pw = saved.get("password")

        if u and pw:
            try:
                self.state_dir.mkdir(parents=True, exist_ok=True)
                auth_file = self.state_dir / f"{canonical}.auth"
                auth_file.write_text(f"{u.strip()}\n{pw.strip()}\n", encoding="utf-8")
                try:
                    os.chmod(str(auth_file), 0o600)
                except Exception:
                    pass
                return True
            except Exception:
                pass
        return False

    def connect(
        self,
        profile: str,
        username: Optional[str] = None,
        password: Optional[str] = None,
        save_in_vault: bool = False,
    ) -> Dict[str, Any]:
        """Conecta un perfil VPN validado, con o sin credenciales de usuario/contraseña."""
        canonical = self.canonical_profile(profile)
        if not canonical:
            return {
                "success": False,
                "message": f"Perfil '{profile}' no autorizado. Use: tryhackme, hackthebox o client.",
            }

        # Guardar en Vault si se solicitó explícitamente
        if save_in_vault and username and password:
            self.save_credentials(canonical, username, password)

        # Preparar archivo efímero .auth si hay credenciales
        self._prepare_auth_file(canonical, username, password)

        res = self._execute_vpn_control("connect", canonical)
        return {
            "success": res["success"],
            "profile": canonical,
            "message": res["stdout"] or res["stderr"] or ("VPN conectada" if res["success"] else "Error al conectar"),
            "raw": res,
        }

    def disconnect(self) -> Dict[str, Any]:
        """Desconecta la VPN activa y limpia archivos temporales de autenticación."""
        res = self._execute_vpn_control("disconnect")
        try:
            if self.state_dir.is_dir():
                for f in self.state_dir.glob("*.auth"):
                    try:
                        f.unlink()
                    except Exception:
                        pass
        except Exception:
            pass

        return {
            "success": res["success"],
            "message": res["stdout"] or res["stderr"] or ("VPN desconectada" if res["success"] else "Error al desconectar"),
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
        canonical = self.canonical_profile(profile)
        if not canonical:
            return {
                "success": False,
                "message": f"Perfil '{profile}' no autorizado. Use: tryhackme, hackthebox o client.",
            }

        if save_in_vault and username and password:
            self.save_credentials(canonical, username, password)

        self._prepare_auth_file(canonical, username, password)

        res = self._execute_vpn_control("switch", canonical)
        return {
            "success": res["success"],
            "profile": canonical,
            "message": res["stdout"] or res["stderr"] or ("VPN conmutada" if res["success"] else "Error al conmutar"),
            "raw": res,
        }


vpn_service = VpnService()
