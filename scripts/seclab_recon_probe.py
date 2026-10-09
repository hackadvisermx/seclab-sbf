"""Sondeo HTTP con destinos fijados, sin redirecciones y con límites globales."""
import concurrent.futures
import http.client
import ipaddress
import json
import math
import socket
import ssl
import subprocess
import threading
import time
from seclab_scope import ScopeError, check_scope, normalize_target, require_authorization


def operational_limits(data):
    supplied = data.get('operational_limits', {})
    values = {}
    for key, default, lower, upper in (
        ('max_requests_per_second', 1, 0.1, 100),
        ('max_parallel_threads', 1, 1, 32),
        ('max_probe_targets', 1000, 1, 10000),
        ('probe_timeout_seconds', 8, 1, 30),
    ):
        raw = supplied.get(key, default)
        try:
            number = float(raw) if not isinstance(raw, bool) else float('nan')
        except (TypeError, ValueError):
            number = float('nan')
        if not math.isfinite(number) or not lower <= number <= upper:
            raise ScopeError(f'Límite inválido: {key}; rango permitido {lower}–{upper}.')
        if key in ('max_parallel_threads', 'max_probe_targets'):
            if not number.is_integer():
                raise ScopeError(f'{key} debe ser un entero.')
            number = int(number)
        values[key] = number
    return values


class RateLimiter:
    def __init__(self, rate, clock=time.monotonic, sleep=time.sleep):
        self.interval = 1 / rate
        self.clock, self.sleep = clock, sleep
        self.next_start = 0
        self.lock = threading.Lock()

    def wait(self):
        with self.lock:
            now = self.clock()
            if self.next_start > now:
                self.sleep(self.next_start - now)
            self.next_start = self.clock() + self.interval


def local_network_addresses():
    addresses = set()
    try:
        interfaces = subprocess.run(['ip', '-j', 'address', 'show'], capture_output=True, text=True, timeout=3, check=True)
        routes = subprocess.run(['ip', '-j', 'route', 'show', 'default'], capture_output=True, text=True, timeout=3, check=True)
        for interface in json.loads(interfaces.stdout):
            for address in interface.get('addr_info', []):
                addresses.add(normalize_target(address['local']))
        for route in json.loads(routes.stdout):
            if route.get('gateway'):
                addresses.add(normalize_target(route['gateway']))
    except (OSError, subprocess.SubprocessError, ValueError, KeyError):
        raise ScopeError('No se pudieron verificar interfaces y gateway. Ejecuta el sondeo dentro del laboratorio Linux.') from None
    return addresses


def destination_permitted(raw_address, scope_data, forbidden):
    address = ipaddress.ip_address(normalize_target(raw_address))
    if str(address) in forbidden or address.is_loopback or address.is_link_local or address.is_multicast or address.is_unspecified or address.is_reserved:
        return False
    if address in ipaddress.ip_network('100.64.0.0/10') or address in ipaddress.ip_network('fd7a:115c:a1e0::/48'):
        return False
    if str(address) in {'168.63.129.16', 'fd00:ec2::254', 'fd20:ce::254'}:
        return False
    verdict, _ = check_scope(str(address), scope_data)
    if verdict == 'OUT_OF_SCOPE':
        return False
    return address.is_global or verdict == 'IN_SCOPE'


class PinnedConnection(http.client.HTTPConnection):
    def __init__(self, host, address, port, timeout, tls=False):
        super().__init__(host, port=port, timeout=timeout)
        self.address = address
        self.tls = tls
        self.expired = threading.Event()

    def connect(self):
        family = socket.AF_INET6 if ipaddress.ip_address(self.address).version == 6 else socket.AF_INET
        self.sock = socket.socket(family, socket.SOCK_STREAM)
        self.sock.settimeout(self.timeout)
        if self.expired.is_set():
            raise TimeoutError('Plazo de sondeo agotado.')
        self.sock.connect((self.address, self.port))
        if self.tls:
            context = ssl.create_default_context()
            self.sock = context.wrap_socket(self.sock, server_hostname=self.host, do_handshake_on_connect=False)
            if self.expired.is_set():
                raise TimeoutError('Plazo de sondeo agotado.')
            self.sock.do_handshake()

    def expire(self):
        self.expired.set()
        if self.sock:
            try:
                self.sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass


class ProbeClient:
    def __init__(self, scope_data, limits, before_request=None):
        self.before_request = before_request
        self.scope_data = scope_data
        self.limits = limits
        self.forbidden = local_network_addresses()
        self.limiter = RateLimiter(limits['max_requests_per_second'])

    def probe_host(self, host):
        if self.before_request:
            self.before_request(host)
        observations = []
        verdict, reason = check_scope(host, self.scope_data)
        if verdict != 'IN_SCOPE':
            return [{'host': host, 'status': 'blocked', 'reason': reason}]
        require_authorization(self.scope_data, 'active')
        try:
            resolved = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
            addresses = sorted({normalize_target(item[4][0]) for item in resolved})
            if not addresses or any(not destination_permitted(address, self.scope_data, self.forbidden) for address in addresses):
                return [{'host': host, 'status': 'blocked', 'reason': 'DNS contiene una dirección excluida, interna sin autorización o protegida.'}]
        except (OSError, ValueError):
            return [{'host': host, 'status': 'dns_error', 'reason': 'No se pudo resolver el destino.'}]
        address = addresses[0]
        for scheme, port in (('https', 443), ('http', 80)):
            url_host = '[' + host + ']' if ':' in host else host
            url = f'{scheme}://{url_host}'
            if check_scope(url + '/', self.scope_data)[0] != 'IN_SCOPE':
                observations.append({'host': host, 'url': url, 'status': 'blocked', 'reason': 'Endpoint excluido del alcance.'})
                continue
            self.limiter.wait()
            require_authorization(self.scope_data, 'active')
            if self.before_request:
                self.before_request(url + "/")
            connection = PinnedConnection(host, address, port, self.limits['probe_timeout_seconds'], tls=scheme == 'https')
            timer = threading.Timer(self.limits['probe_timeout_seconds'], connection.expire)
            timer.daemon = True
            timer.start()
            try:
                connection.request('GET', '/', headers={'Host': url_host, 'User-Agent': 'SecLab-AuthorizedRecon/1.0', 'Connection': 'close'})
                response = connection.getresponse()
                if connection.expired.is_set():
                    raise TimeoutError('Plazo de sondeo agotado.')
                observations.append({'host': host, 'url': url, 'address': address, 'status': 'response', 'http_status': response.status,
                                     'location': response.getheader('Location'), 'redirect_followed': False})
            except ssl.SSLCertVerificationError:
                observations.append({'host': host, 'url': url, 'address': address, 'status': 'tls_untrusted'})
            except (OSError, http.client.HTTPException):
                observations.append({'host': host, 'url': url, 'address': address, 'status': 'connection_error'})
            finally:
                timer.cancel()
                connection.close()
        return observations

    def probe(self, hosts, on_result=None):
        if len(hosts) > self.limits['max_probe_targets']:
            raise ScopeError('Demasiados objetivos para max_probe_targets; no se inició el sondeo.')
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.limits['max_parallel_threads']) as executor:
            if on_result is None:
                groups = list(executor.map(self.probe_host, hosts))
            else:
                futures = {executor.submit(self.probe_host, host): index for index, host in enumerate(hosts)}
                groups = [None] * len(hosts)
                for future in concurrent.futures.as_completed(futures):
                    rows = future.result()
                    groups[futures[future]] = rows
                    on_result(rows)
        return [observation for group in groups for observation in group]
