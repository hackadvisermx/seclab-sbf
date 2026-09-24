#!/usr/bin/env python3
import ipaddress
import json
import os
import signal
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

STATE_DIR = Path(os.environ.get("PROXY_STATE_DIR", "/var/lib/seclab/tester/proxy"))
PID_FILE = STATE_DIR / "pt-forward.pid"
META_FILE = STATE_DIR / "pt-forward.json"
LOG_FILE = STATE_DIR / "pt-forward.log"
LISTEN_HOST = "127.0.0.1"
MAX_CONNECTIONS = 32
VPN_INTERFACE = "tun0"
VPN_CONTROL = "/usr/local/bin/vpn-control"
BLOCKED_NETWORKS = tuple(
    ipaddress.ip_network(value)
    for value in (
        "100.64.0.0/10",
        "169.254.0.0/16",
        "172.17.0.0/16",
        "172.18.0.0/16",
        "172.19.0.0/16",
        "172.20.0.0/16",
        "172.21.0.0/16",
        "172.22.0.0/16",
        "172.23.0.0/16",
        "172.24.0.0/16",
        "172.25.0.0/16",
        "172.26.0.0/16",
        "172.27.0.0/16",
        "172.28.0.0/16",
        "172.29.0.0/16",
        "172.30.0.0/16",
        "172.31.0.0/16",
        "192.0.0.192/32",
        "168.63.129.16/32",
        "198.18.0.0/15",
    )
)
stop_event = threading.Event()
connection_lock = threading.Lock()
connection_count = 0


class ProxyError(Exception):
    pass


class RouteDenied(ProxyError):
    pass


def log(message):
    print(f"pt-forward: {message}", flush=True)


def ensure_state_dir():
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    os.chmod(STATE_DIR, 0o700)


def vpn_status():
    try:
        result = subprocess.run(
            [VPN_CONTROL, "client", "status"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    output = f"{result.stdout}\n{result.stderr}"
    active = ""
    for line in output.splitlines():
        if line.startswith("active="):
            active = line.split("=", 1)[1].strip()
            break
    tun_present = f"tun_interface={VPN_INTERFACE} present" in output
    return {"active": active, "tun": tun_present, "output": output.strip()}


def vpn_ready():
    status = vpn_status()
    if not status:
        return False
    return bool(status["active"] and status["active"] not in {"none", "stale"} and status["tun"])


def normalize_ip(value):
    address = ipaddress.ip_address(value)
    if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped:
        return address.ipv4_mapped
    return address


def blocked_ip(value):
    address = normalize_ip(value)
    if address.is_unspecified or address.is_loopback or address.is_link_local or address.is_multicast or address.is_reserved:
        return True
    if address.version == 6 and address in ipaddress.ip_network("fd7a:115c:a1e0::/48"):
        return True
    if address.version == 4:
        return any(address in network for network in BLOCKED_NETWORKS)
    return False


def route_uses_vpn(address):
    family = "-4" if address.version == 4 else "-6"
    try:
        result = subprocess.run(
            ["ip", family, "route", "get", str(address)],
            capture_output=True,
            text=True,
            timeout=3,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    if result.returncode != 0:
        return False
    fields = result.stdout.split()
    return "dev" in fields and VPN_INTERFACE in fields[fields.index("dev") + 1 : fields.index("dev") + 2]


def resolve_target(host, port):
    if not isinstance(host, str) or not host or len(host) > 253:
        raise RouteDenied("destino invalido")
    if not isinstance(port, int) or not 1 <= port <= 65535:
        raise RouteDenied("puerto invalido")
    literal = None
    try:
        literal = normalize_ip(host)
    except ValueError:
        pass
    if literal is not None:
        addresses = [literal]
    else:
        try:
            records = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
        except OSError as error:
            raise RouteDenied(f"no se pudo resolver {host}: {error}") from error
        addresses = []
        for record in records:
            try:
                address = normalize_ip(record[4][0])
            except ValueError:
                continue
            if address not in addresses:
                addresses.append(address)
        if not addresses:
            raise RouteDenied("el destino no tiene direcciones IP")
    if not vpn_ready():
        raise RouteDenied("no hay una VPN activa sobre tun0")
    for address in addresses:
        if blocked_ip(address):
            raise RouteDenied(f"destino bloqueado: {address}")
        if not route_uses_vpn(address):
            raise RouteDenied(f"la ruta de {address} no usa {VPN_INTERFACE}")
    return addresses[0]


def open_target(host, port):
    address = resolve_target(host, port)
    family = socket.AF_INET6 if address.version == 6 else socket.AF_INET
    upstream = socket.socket(family, socket.SOCK_STREAM)
    upstream.settimeout(10)
    try:
        destination = (str(address), port, 0, 0) if address.version == 6 else (str(address), port)
        upstream.connect(destination)
    except OSError as error:
        upstream.close()
        raise ProxyError(f"no se pudo conectar con {host}:{port}: {error}") from error
    return upstream, address


def pump(source, destination):
    try:
        while not stop_event.is_set():
            data = source.recv(65536)
            if not data:
                break
            destination.sendall(data)
    except OSError:
        pass
    finally:
        for item in (source, destination):
            try:
                item.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass


def relay(first, second):
    threads = [
        threading.Thread(target=pump, args=(first, second), daemon=True),
        threading.Thread(target=pump, args=(second, first), daemon=True),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()


def enter_connection():
    global connection_count
    with connection_lock:
        if connection_count >= MAX_CONNECTIONS:
            return False
        connection_count += 1
        return True


def leave_connection():
    global connection_count
    with connection_lock:
        connection_count = max(0, connection_count - 1)


def recv_exact(connection, size):
    chunks = []
    remaining = size
    while remaining:
        chunk = connection.recv(remaining)
        if not chunk:
            raise ProxyError("solicitud SOCKS incompleta")
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def socks_reply(connection, code, address="0.0.0.0", port=0):
    if ":" in address:
        bound = b"\x04" + socket.inet_pton(socket.AF_INET6, address)
    else:
        bound = b"\x01" + socket.inet_aton(address)
    connection.sendall(bytes((5, code, 0)) + bound + port.to_bytes(2, "big"))


def handle_tcp(client, host, port):
    upstream = None
    entered = False
    try:
        if not enter_connection():
            return
        entered = True
        upstream, _ = open_target(host, port)
        relay(client, upstream)
    except ProxyError as error:
        log(str(error))
    finally:
        if upstream is not None:
            upstream.close()
        client.close()
        if entered:
            leave_connection()


def handle_socks(client):
    upstream = None
    entered = False
    try:
        if not enter_connection():
            socks_reply(client, 1)
            return
        entered = True
        version, method_count = recv_exact(client, 2)
        if version != 5:
            raise ProxyError("version SOCKS no soportada")
        methods = recv_exact(client, method_count)
        if 0 not in methods:
            client.sendall(b"\x05\xff")
            return
        client.sendall(b"\x05\x00")
        version, command, _, address_type = recv_exact(client, 4)
        if version != 5 or command != 1:
            socks_reply(client, 7)
            return
        if address_type == 1:
            host = socket.inet_ntoa(recv_exact(client, 4))
        elif address_type == 3:
            length = recv_exact(client, 1)[0]
            host = recv_exact(client, length).decode("idna")
        elif address_type == 4:
            host = socket.inet_ntop(socket.AF_INET6, recv_exact(client, 16))
        else:
            socks_reply(client, 8)
            return
        port = int.from_bytes(recv_exact(client, 2), "big")
        upstream, address = open_target(host, port)
        socks_reply(client, 0, str(address), port)
        relay(client, upstream)
    except (ProxyError, UnicodeError, OSError) as error:
        log(str(error))
        try:
            socks_reply(client, 1)
        except OSError:
            pass
    finally:
        if upstream is not None:
            upstream.close()
        client.close()
        if entered:
            leave_connection()


def read_pid():
    try:
        value = PID_FILE.read_text().strip()
    except OSError:
        return None
    return int(value) if value.isdigit() else None


def process_alive(pid):
    if not pid:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def write_metadata(mode, target, target_port, listen_port):
    ensure_state_dir()
    META_FILE.write_text(json.dumps({"mode": mode, "target": target, "target_port": target_port, "listen_port": listen_port}) + "\n")
    os.chmod(META_FILE, 0o600)


def serve(mode, host, target_port, listen_port):
    global stop_event
    if os.geteuid() == 0:
        log("debe ejecutarse como tester, no como root")
        return 77
    if not vpn_ready():
        log("no hay una VPN activa; conecta una VPN antes de iniciar el proxy")
        return 78
    ensure_state_dir()
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        listener.bind((LISTEN_HOST, listen_port))
        listener.listen(MAX_CONNECTIONS)
        listener.settimeout(1)
    except OSError as error:
        listener.close()
        log(f"no se pudo escuchar en {LISTEN_HOST}:{listen_port}: {error}")
        return 69
    os.chmod(STATE_DIR, 0o700)
    PID_FILE.write_text(f"{os.getpid()}\n")
    os.chmod(PID_FILE, 0o600)
    write_metadata(mode, host or "", target_port, listen_port)
    stop_event.clear()

    def stop_handler(_signum, _frame):
        stop_event.set()
        try:
            listener.close()
        except OSError:
            pass

    signal.signal(signal.SIGTERM, stop_handler)
    signal.signal(signal.SIGINT, stop_handler)
    log(f"started mode={mode} listen={LISTEN_HOST}:{listen_port} target={host or '-'}:{target_port or '-'}")

    def monitor_vpn():
        while not stop_event.wait(2):
            if not vpn_ready():
                log("VPN no disponible; detener proxy")
                stop_handler(signal.SIGTERM, None)
                return

    threading.Thread(target=monitor_vpn, daemon=True).start()
    try:
        while not stop_event.is_set():
            try:
                client, _ = listener.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            if mode == "socks5":
                threading.Thread(target=handle_socks, args=(client,), daemon=True).start()
            else:
                threading.Thread(target=handle_tcp, args=(client, host, target_port), daemon=True).start()
    finally:
        stop_event.set()
        try:
            listener.close()
        except OSError:
            pass
        try:
            if PID_FILE.read_text().strip() == str(os.getpid()):
                PID_FILE.unlink()
        except OSError:
            pass
    return 0


def start(mode, host, target_port, listen_port):
    if os.geteuid() == 0:
        log("debe ejecutarse como tester, no como root")
        return 77
    if mode == "tcp" and (not host or not target_port):
        log("uso: pt-forward start tcp <host> <port> [listen_port]")
        return 64
    if mode == "socks5" and (host or target_port):
        log("uso: pt-forward start socks5 [listen_port]")
        return 64
    if mode == "tcp":
        try:
            resolve_target(host, target_port)
        except ProxyError as error:
            log(str(error))
            return 78
    if not vpn_ready():
        log("no hay una VPN activa; conecta una VPN antes de iniciar el proxy")
        return 78
    if not 1024 <= listen_port <= 65535:
        log("listen_port debe estar entre 1024 y 65535")
        return 64
    ensure_state_dir()
    old_pid = read_pid()
    if process_alive(old_pid):
        log(f"ya existe un proxy activo pid={old_pid}")
        return 75
    PID_FILE.unlink(missing_ok=True)
    META_FILE.unlink(missing_ok=True)
    LOG_FILE.touch(mode=0o600, exist_ok=True)
    os.chmod(LOG_FILE, 0o600)
    command = [sys.executable, str(Path(__file__).resolve()), "__serve__", mode, host or "", str(target_port or 0), str(listen_port)]
    with LOG_FILE.open("ab") as output:
        child = subprocess.Popen(command, stdout=output, stderr=subprocess.STDOUT, start_new_session=True, close_fds=True)
    time.sleep(0.4)
    if not process_alive(child.pid):
        log("el proxy no pudo iniciarse; revisa el log")
        return 69
    print(f"pt-forward=started mode={mode} pid={child.pid} listen={LISTEN_HOST}:{listen_port} target={host or '-'} target_port={target_port or '-'}")
    return 0


def status():
    pid = read_pid()
    if not process_alive(pid):
        print("pt-forward=inactive")
        return 1
    metadata = {}
    try:
        metadata = json.loads(META_FILE.read_text())
    except (OSError, json.JSONDecodeError):
        pass
    vpn = vpn_status() or {}
    print(f"pt-forward=active pid={pid} mode={metadata.get('mode', '-')} listen={LISTEN_HOST}:{metadata.get('listen_port', '-')} target={metadata.get('target') or '-'} target_port={metadata.get('target_port') or '-'}")
    print(f"vpn_active={vpn.get('active', '-')} tun={vpn.get('tun', False)}")
    return 0


def stop():
    pid = read_pid()
    if not process_alive(pid):
        PID_FILE.unlink(missing_ok=True)
        print("pt-forward=stopped")
        return 0
    os.kill(pid, signal.SIGTERM)
    for _ in range(20):
        if not process_alive(pid):
            break
        time.sleep(0.1)
    if process_alive(pid):
        os.kill(pid, signal.SIGKILL)
    PID_FILE.unlink(missing_ok=True)
    print("pt-forward=stopped")
    return 0


def clean():
    stop()
    META_FILE.unlink(missing_ok=True)
    LOG_FILE.unlink(missing_ok=True)
    print("pt-forward=clean")
    return 0


def doctor(host=None, port=None):
    print(f"user={os.geteuid()} state={STATE_DIR} listen={LISTEN_HOST}")
    status_value = vpn_status()
    if not status_value:
        print("vpn_status=unavailable")
        return 78
    print(f"vpn_active={status_value['active']} tun={status_value['tun']}")
    if not vpn_ready():
        print("route_guard=blocked vpn=inactive")
        return 78
    print("route_guard=ready interface=tun0")
    if host and port:
        try:
            address = resolve_target(host, port)
        except ProxyError as error:
            print(f"route_guard=blocked target={host}:{port} reason={error}")
            return 78
        print(f"route_guard=allowed target={host}:{port} address={address}")
    return 0


def usage():
    print("Uso: pt-forward start tcp <host> <port> [listen_port]", file=sys.stderr)
    print("     pt-forward start socks5 [listen_port]", file=sys.stderr)
    print("     pt-forward status|stop|clean|doctor [host port]", file=sys.stderr)
    return 64


def main():
    if len(sys.argv) < 2:
        return usage()
    command = sys.argv[1]
    if command == "__serve__":
        if len(sys.argv) != 6:
            return usage()
        return serve(sys.argv[2], sys.argv[3] or None, int(sys.argv[4]), int(sys.argv[5]))
    if command == "start":
        if len(sys.argv) < 3:
            return usage()
        mode = sys.argv[2]
        if mode == "socks5":
            listen_port = int(sys.argv[3]) if len(sys.argv) == 4 else 1080
            return start("socks5", None, None, listen_port)
        if mode == "tcp" and len(sys.argv) in {5, 6}:
            host = sys.argv[3]
            target_port = int(sys.argv[4])
            listen_port = int(sys.argv[5]) if len(sys.argv) == 6 else 18080
            return start("tcp", host, target_port, listen_port)
        return usage()
    if command in {"socks", "socks5"}:
        listen_port = int(sys.argv[2]) if len(sys.argv) == 3 else 1080
        return start("socks5", None, None, listen_port)
    if command == "status":
        return status()
    if command == "stop":
        return stop()
    if command == "clean":
        return clean()
    if command == "doctor":
        host = sys.argv[2] if len(sys.argv) > 2 else None
        port = int(sys.argv[3]) if len(sys.argv) > 3 else None
        return doctor(host, port)
    return usage()


if __name__ == "__main__":
    raise SystemExit(main())
