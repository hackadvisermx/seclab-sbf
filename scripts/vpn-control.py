#!/usr/bin/env python3
import json
import os
import signal
import socket
import struct
import subprocess
import sys
import threading
from pathlib import Path

LAB_UID = 1000
TUN_INTERFACE = "tun0"
ALLOWED_ACTIONS = {"list", "status", "doctor", "connect", "disconnect", "switch"}
ALLOWED_PROFILES = {"tryhackme", "try", "hackthebox", "htb", "client", "cli"}
CONTROL_DIR = Path(os.environ.get("VPN_CONTROL_DIR", "/var/lib/seclab/vpn-control"))
CONTROL_SOCKET = CONTROL_DIR / "control.sock"
MANAGER = "/usr/local/bin/vpn-manager"
request_lock = threading.Lock()
server_socket = None
stop_requested = False


def output_limit(value):
    return value[:16000]


def ensure_tun_interface():
    tun_sysfs = Path("/sys/class/net") / TUN_INTERFACE
    if tun_sysfs.exists():
        return
    if not Path("/dev/net/tun").is_char_device():
        raise RuntimeError("/dev/net/tun no esta disponible")
    result = subprocess.run(
        ["ip", "tuntap", "add", "dev", TUN_INTERFACE, "mode", "tun"],
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
    )
    if result.returncode != 0 and not tun_sysfs.exists():
        raise RuntimeError("no se pudo crear tun0")


def manager_command(action, profile=None):
    command = [MANAGER, action]
    if profile is not None:
        command.append(profile)
    return command


MAX_CREDENTIAL_LENGTH = 256


def valid_credential(value):
    """Usuario o password puntual: texto corto, sin saltos de linea ni NUL.

    Un salto de linea romperia el formato de dos lineas del .auth de openvpn y
    permitiria inyectar una tercera linea, asi que se rechaza en el daemon.
    """
    return (
        isinstance(value, str)
        and 0 < len(value) <= MAX_CREDENTIAL_LENGTH
        and not any(ch in value for ch in ("\n", "\r", "\x00"))
    )


def manager_env(credentials=None):
    env = {key: value for key, value in os.environ.items() if key not in {"VPN_AUTH_USER", "VPN_AUTH_PASSWORD"}}
    if credentials:
        env["VPN_AUTH_USER"], env["VPN_AUTH_PASSWORD"] = credentials
    return env


def run_manager(action, profile=None, credentials=None):
    try:
        result = subprocess.run(
            manager_command(action, profile),
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
            env=manager_env(credentials),
        )
    except subprocess.TimeoutExpired:
        return 124, "", "La operacion VPN excedio el tiempo limite."
    return result.returncode, output_limit(result.stdout.strip()), output_limit(result.stderr.strip())


def peer_is_lab(connection):
    raw_credentials = connection.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i"))
    peer_pid, peer_uid, peer_gid = struct.unpack("3i", raw_credentials)
    return peer_uid == LAB_UID


def response_payload(code, stdout, stderr):
    return json.dumps({"code": code, "stdout": stdout, "stderr": stderr}, ensure_ascii=False) + "\n"


def read_request(connection):
    chunks = []
    total = 0
    while total <= 4096:
        chunk = connection.recv(4096)
        if not chunk:
            break
        chunks.append(chunk)
        total += len(chunk)
        if b"\n" in chunk:
            break
    raw = b"".join(chunks).split(b"\n", 1)[0]
    if not raw or len(raw) > 4096:
        raise ValueError("solicitud vacia o demasiado grande")
    return json.loads(raw.decode("utf-8"))


def discard_request(connection):
    total = 0
    while total <= 4096:
        chunk = connection.recv(4096)
        if not chunk:
            return
        total += len(chunk)
        if b"\n" in chunk:
            return


def handle_connection(connection):
    try:
        connection.settimeout(5)
        if not peer_is_lab(connection):
            try:
                discard_request(connection)
            except OSError:
                pass
            connection.sendall(response_payload(77, "", "Solo el usuario lab puede controlar la VPN.").encode("utf-8"))
            return
        request = read_request(connection)
        if not isinstance(request, dict):
            raise ValueError("solicitud invalida")
        action = request.get("action")
        profile = request.get("profile")
        if not isinstance(action, str) or action not in ALLOWED_ACTIONS:
            raise ValueError("accion no permitida")
        if action in {"connect", "switch"} and (not isinstance(profile, str) or profile not in ALLOWED_PROFILES):
            raise ValueError("perfil no permitido")
        if action in {"list", "status", "doctor", "disconnect"}:
            profile = None
        credentials = None
        username = request.get("username")
        password = request.get("password")
        if action in {"connect", "switch"} and (username is not None or password is not None):
            if not (valid_credential(username) and valid_credential(password)):
                raise ValueError("credenciales invalidas: usuario y password requeridos, sin saltos de linea")
            credentials = (username, password)
        with request_lock:
            code, stdout, stderr = run_manager(action, profile, credentials)
        connection.sendall(response_payload(code, stdout, stderr).encode("utf-8"))
    except (OSError, ValueError, json.JSONDecodeError) as error:
        try:
            connection.sendall(response_payload(65, "", str(error)).encode("utf-8"))
        except OSError:
            pass
    finally:
        connection.close()


def prepare_socket():
    CONTROL_DIR.mkdir(parents=True, exist_ok=True)
    os.chown(CONTROL_DIR, 0, 0)
    os.chmod(CONTROL_DIR, 0o711)
    if CONTROL_SOCKET.exists():
        CONTROL_SOCKET.unlink()
    control = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    control.bind(str(CONTROL_SOCKET))
    os.chmod(CONTROL_SOCKET, 0o660)
    os.chown(CONTROL_SOCKET, LAB_UID, LAB_UID)
    control.listen(4)
    return control


def stop_handler(_signum, _frame):
    global stop_requested
    stop_requested = True
    if server_socket is not None:
        server_socket.close()


def serve():
    global server_socket
    if os.environ.get("VPN_MODE") != "inside":
        print("vpn-control: el socket requiere VPN_MODE=inside", file=sys.stderr)
        return 78
    if os.geteuid() != 0:
        print("vpn-control: el servidor requiere root", file=sys.stderr)
        return 77
    try:
        ensure_tun_interface()
    except (OSError, RuntimeError, subprocess.SubprocessError) as error:
        print(f"vpn-control: {error}", file=sys.stderr)
        return 78
    server_socket = prepare_socket()
    signal.signal(signal.SIGTERM, stop_handler)
    signal.signal(signal.SIGINT, stop_handler)
    print("vpn-control=ready tun0=present", flush=True)
    try:
        while not stop_requested:
            try:
                connection, _ = server_socket.accept()
            except socket.timeout:
                continue
            except OSError:
                if stop_requested:
                    break
                raise
            handle_connection(connection)
    finally:
        try:
            server_socket.close()
        except OSError:
            pass
        try:
            CONTROL_SOCKET.unlink()
        except FileNotFoundError:
            pass
        run_manager("disconnect")
    return 0


def print_response(response):
    if response.get("stdout"):
        print(response["stdout"])
    if response.get("stderr"):
        print(response["stderr"], file=sys.stderr)
    return int(response.get("code", 1))


def request(action, profile=None):
    try:
        if not CONTROL_SOCKET.exists():
            if action in {"connect", "switch", "disconnect"}:
                print("vpn-control: servicio VPN no activo; ejecuta make compose vpn-up", file=sys.stderr)
                return 78
            return subprocess.run(manager_command(action, profile), check=False).returncode
        payload = {"action": action}
        if profile is not None:
            payload["profile"] = profile
        # Credenciales puntuales: solo por entorno (no aparecen en ps ni en
        # el historial) y solo para acciones que conectan.
        auth_user = os.environ.get("VPN_AUTH_USER")
        auth_password = os.environ.get("VPN_AUTH_PASSWORD")
        if action in {"connect", "switch"} and auth_user and auth_password:
            payload["username"] = auth_user
            payload["password"] = auth_password
        encoded = (json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8")
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
            client.settimeout(65)
            client.connect(str(CONTROL_SOCKET))
            client.sendall(encoded)
            chunks = []
            try:
                while True:
                    chunk = client.recv(4096)
                    if not chunk:
                        break
                    chunks.append(chunk)
            except ConnectionResetError:
                if not chunks:
                    raise
        raw = b"".join(chunks)
        if not raw:
            print("vpn-control: respuesta vacia", file=sys.stderr)
            return 70
        return print_response(json.loads(raw.decode("utf-8")))
    except (OSError, ValueError, json.JSONDecodeError) as error:
        if action in {"connect", "switch", "disconnect"}:
            print(f"vpn-control: daemon no disponible: {error}", file=sys.stderr)
            return 78
        return subprocess.run(manager_command(action, profile), check=False).returncode


def main():
    if len(sys.argv) < 2:
        print("Uso: vpn-control serve|client <accion> [perfil]", file=sys.stderr)
        return 64
    mode = sys.argv[1]
    if mode == "serve":
        return serve()
    if mode != "client" or len(sys.argv) < 3:
        print("Uso: vpn-control serve|client <accion> [perfil]", file=sys.stderr)
        return 64
    action = sys.argv[2]
    profile = sys.argv[3] if len(sys.argv) == 4 else None
    if action not in ALLOWED_ACTIONS:
        print("accion no permitida", file=sys.stderr)
        return 64
    return request(action, profile)


if __name__ == "__main__":
    raise SystemExit(main())
