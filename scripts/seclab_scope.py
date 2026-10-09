"""Reglas compartidas de alcance para el validador y el reconocimiento."""
import ast
import datetime
import ipaddress
import pathlib
import re
import urllib.parse


class ScopeError(ValueError):
    pass


def default_authorization():
    return {'reference': '', 'valid_from': '', 'valid_until': '',
            'allow_passive': False, 'allow_active': False}


def _authorization_time(value):
    if not isinstance(value, str):
        raise ScopeError('La vigencia requiere fechas ISO 8601 con zona horaria.')
    try:
        result = datetime.datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError:
        raise ScopeError('La vigencia requiere fechas ISO 8601 con zona horaria.') from None
    if result.tzinfo is None or result.utcoffset() is None:
        raise ScopeError('La vigencia requiere zona horaria explícita.')
    try:
        return result.astimezone(datetime.timezone.utc)
    except (ValueError, OverflowError):
        raise ScopeError('La vigencia está fuera del rango de fechas admitido.') from None


def authorization_contract(data):
    if 'authorization' not in data:
        return default_authorization()
    supplied = data['authorization']
    if not isinstance(supplied, dict) or set(supplied) - set(default_authorization()):
        raise ScopeError('authorization requiere un objeto con referencia, vigencia y permisos conocidos.')
    contract = {**default_authorization(), **supplied}
    for key in ('allow_passive', 'allow_active'):
        if type(contract[key]) is not bool:
            raise ScopeError(f'{key} requiere true o false, sin comillas.')
    for key in ('reference', 'valid_from', 'valid_until'):
        if not isinstance(contract[key], str):
            raise ScopeError(f'{key} requiere texto.')
        contract[key] = contract[key].strip()
    if contract['allow_passive'] or contract['allow_active']:
        if not all(contract[key] for key in ('reference', 'valid_from', 'valid_until')):
            raise ScopeError('Para permitir actividad se requieren referencia, inicio y fin de autorización.')
    start = _authorization_time(contract['valid_from']) if contract['valid_from'] else None
    end = _authorization_time(contract['valid_until']) if contract['valid_until'] else None
    if start and end and start >= end:
        raise ScopeError('El fin de autorización debe ser posterior al inicio.')
    return contract


def require_authorization(data, interaction, now=None):
    if interaction in ('local', 'simulation'):
        return
    if interaction not in ('passive', 'active'):
        raise ScopeError('Tipo de interacción desconocido.')
    contract = authorization_contract(data)
    if not contract['allow_' + interaction]:
        label = 'pasiva' if interaction == 'passive' else 'activa'
        raise ScopeError(f'Falta permiso explícito para actividad {label}. Configura autorización y vigencia en Alcance; la simulación sigue disponible.')
    current = now or datetime.datetime.now(datetime.timezone.utc)
    if current.tzinfo is None or current.utcoffset() is None:
        raise ScopeError('El reloj de autorización requiere zona horaria.')
    if not _authorization_time(contract['valid_from']) <= current < _authorization_time(contract['valid_until']):
        raise ScopeError('La autorización está fuera de su ventana de vigencia. Revisa inicio/fin con el responsable; no se enviará tráfico.')


def initial_scope(target=None):
    value = (target or '').strip()
    rules = {section: {key: [] for key in ('domains', 'ips', 'cidrs', 'endpoints')}
             for section in ('in_scope', 'out_of_scope')}
    rules['out_of_scope']['notes'] = []
    if value:
        rules['in_scope']['ips' if is_ip(value) else 'domains'] = [value]
    validate_scope({'scope': rules})
    return rules


def is_ip(target):
    try:
        ipaddress.ip_address(target)
        return True
    except ValueError:
        return False


def normalize_target(raw_target):
    if not isinstance(raw_target, str):
        return ''
    value = raw_target.strip()
    if not value or any(character.isspace() or ord(character) < 32 for character in value):
        return ''
    try:
        address = ipaddress.ip_address(value)
        return str(address.ipv4_mapped or address) if address.version == 6 else str(address)
    except ValueError:
        pass
    if '://' not in value and '/' in value:
        try:
            ipaddress.ip_network(value, strict=False)
            return ''
        except ValueError:
            pass
    try:
        parsed = urllib.parse.urlsplit(value if '://' in value else '//' + value)
        if parsed.scheme and parsed.scheme.lower() not in ('http', 'https'):
            return ''
        if parsed.username is not None or parsed.password is not None:
            return ''
        host = parsed.hostname
        if not host or '%' in host or '\\' in host:
            return ''
        parsed.port
        if is_ip(host):
            return normalize_target(host)
        host = host.rstrip('.').encode('idna').decode('ascii').lower()
        if len(host) > 253 or not all(re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?', label) for label in host.split('.')):
            return ''
        return host
    except (ValueError, UnicodeError):
        return ''


def domain_matches(target, pattern):
    suffix = pattern[2:] if pattern.startswith('*.') else pattern
    suffix = normalize_target(suffix)
    target = normalize_target(target)
    if not suffix or not target:
        return False
    return target.endswith('.' + suffix) if pattern.startswith('*.') else target == suffix


def validate_scope(data):
    if not isinstance(data, dict) or not isinstance(data.get('scope'), dict):
        raise ScopeError('La configuración requiere un objeto scope.')
    if set(data['scope']) - {'in_scope', 'out_of_scope'}:
        raise ScopeError('Sección de alcance desconocida.')
    for section in ('in_scope', 'out_of_scope'):
        rules = data['scope'].get(section, {})
        if not isinstance(rules, dict):
            raise ScopeError('Las inclusiones y exclusiones deben ser objetos.')
        if set(rules) - {'domains', 'ips', 'cidrs', 'endpoints', 'notes'}:
            raise ScopeError('Regla de alcance desconocida.')
        for key in ('domains', 'ips', 'cidrs', 'endpoints'):
            values = rules.get(key, [])
            if not isinstance(values, list) or any(not isinstance(value, str) or not value.strip() for value in values):
                raise ScopeError('Las reglas de alcance deben ser listas de textos no vacíos.')
            for value in values:
                value = value.strip()
                try:
                    if key == 'ips':
                        ipaddress.ip_address(value)
                    elif key == 'cidrs':
                        ipaddress.ip_network(value, strict=False)
                    elif key == 'domains':
                        host = value[2:] if value.startswith('*.') else value
                        if not normalize_target(host) or any(character in host for character in '*/:?#@') or is_ip(host):
                            raise ValueError()
                    elif not value.lower().startswith(('http://', 'https://')) or not normalize_target(value):
                        raise ValueError()
                except ValueError:
                    raise ScopeError('Hay una regla de alcance inválida.') from None
    authorization_contract(data)
    limits = data.get('operational_limits', {})
    if not isinstance(limits, dict):
        raise ScopeError('operational_limits debe ser un objeto.')
    return data


def _scalar(value):
    value = value.strip()
    if value.startswith(('"', "'")):
        try:
            return ast.literal_eval(value)
        except (ValueError, SyntaxError):
            raise ScopeError('YAML no soportado sin PyYAML.') from None
    value = value.split(' #', 1)[0].strip()
    if any(character in value for character in '{}[]&!') or value.startswith('*') and not value.startswith('*.'):
        raise ScopeError('YAML no soportado sin PyYAML.')
    return value


def parse_simple_yaml_lists(content):
    data = {'scope': {'in_scope': {}, 'out_of_scope': {}}, 'operational_limits': {}, 'engagement': {}}
    section = subsection = field = None
    seen = set()
    for line in content.splitlines():
        if not line.strip() or line.lstrip().startswith('#') or line.strip() == '---':
            continue
        if '\t' in line:
            raise ScopeError('YAML no soportado sin PyYAML.')
        indent = len(line) - len(line.lstrip())
        text = line.strip()
        if indent == 0:
            match = re.fullmatch(r'([a-z_]+):\s*(.*)', text)
            if not match:
                raise ScopeError('YAML no soportado sin PyYAML.')
            section, subsection, field = match.group(1), None, None
            if ('root', section) in seen:
                raise ScopeError('Sección YAML duplicada.')
            seen.add(('root', section))
            if section == 'authorization':
                data['authorization'] = {}
            if section in ('scope', 'operational_limits', 'authorization') and match.group(2) and not match.group(2).startswith('#'):
                raise ScopeError('La configuración requiere objetos de alcance y límites.')
            continue
        if section == 'scope':
            if indent == 2 and text in ('in_scope:', 'out_of_scope:'):
                subsection, field = text[:-1], None
                key = ('scope', subsection)
                if key in seen:
                    raise ScopeError('Regla YAML duplicada.')
                seen.add(key)
                continue
            if subsection and indent in (4, 6) and text.startswith('- ') and field:
                data['scope'][subsection][field].append(_scalar(text[2:]))
                continue
            match = re.fullmatch(r'(domains|ips|cidrs|endpoints|notes):\s*(.*)', text)
            if not subsection or indent != 4 or not match:
                raise ScopeError('YAML de alcance no soportado sin PyYAML.')
            field, value = match.groups()
            key = (subsection, field)
            if key in seen:
                raise ScopeError('Regla YAML duplicada.')
            seen.add(key)
            if value.startswith('[') and value.endswith(']'):
                values = [_scalar(item) for item in value[1:-1].split(',') if item.strip()]
            elif not value or value.startswith('#'):
                values = []
            else:
                raise ScopeError('Las reglas deben ser listas.')
            data['scope'][subsection][field] = values
        elif section in ('engagement', 'operational_limits', 'authorization') and indent == 2:
            key, separator, value = text.partition(':')
            if separator:
                if (section, key) in seen:
                    raise ScopeError('Regla YAML duplicada.')
                seen.add((section, key))
                parsed = _scalar(value)
                if section == 'authorization' and key in ('allow_passive', 'allow_active') and value.split(' #', 1)[0].strip() in ('true', 'false'):
                    parsed = value.split(' #', 1)[0].strip() == 'true'
                data[section][key] = parsed
        elif section in ('operational_limits', 'authorization'):
            raise ScopeError('Límite YAML no soportado sin PyYAML.')
    if ('root', 'scope') not in seen:
        raise ScopeError('Falta scope en target.yaml.')
    return validate_scope(data)


def load_target_yaml(path):
    content = pathlib.Path(path).read_text(encoding='utf-8')
    try:
        import yaml
    except ImportError:
        return parse_simple_yaml_lists(content)
    class UniqueLoader(yaml.SafeLoader):
        pass
    def unique_mapping(loader, node, deep=False):
        mapping = {}
        for key_node, value_node in node.value:
            key = loader.construct_object(key_node, deep=deep)
            if not isinstance(key, str) or key in mapping:
                raise ScopeError('Regla YAML inválida o duplicada.')
            mapping[key] = loader.construct_object(value_node, deep=deep)
        return mapping
    UniqueLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, unique_mapping)
    try:
        return validate_scope(yaml.load(content, Loader=UniqueLoader))
    except yaml.YAMLError:
        raise ScopeError('target.yaml inválido: corrige el YAML antes de continuar.') from None


def load_scope_txt(path):
    data = {'scope': {'in_scope': {'domains': [], 'ips': [], 'cidrs': []}, 'out_of_scope': {'domains': [], 'ips': [], 'cidrs': []}}}
    content = pathlib.Path(path).read_text(encoding='utf-8')
    markdown = any(line.startswith('## ') for line in content.splitlines())
    section = None if markdown else 'in_scope'
    for line in content.splitlines():
        text = line.strip()
        if text.startswith('## Activos y Objetivos en Alcance'):
            section = 'in_scope'
            continue
        if text.startswith('## Fuera de Alcance'):
            section = 'out_of_scope'
            continue
        if text.startswith('## '):
            section = None
            continue
        if not section or not text or text.startswith('#'):
            continue
        if markdown and not text.startswith('- '):
            continue
        value = text[2:].split()[0].strip('[]()') if markdown else text
        key = 'ips' if is_ip(value) else 'cidrs' if '/' in value and not value.startswith(('http://', 'https://')) else 'domains'
        data['scope'][section][key].append(normalize_target(value) if key == 'domains' and not value.startswith('*.') else value)
    return validate_scope(data)


def load_scope_rules(directory):
    root = pathlib.Path(directory)
    if (root / 'target.yaml').is_file():
        return load_target_yaml(root / 'target.yaml')
    if (root / 'scope.txt').is_file():
        return load_scope_txt(root / 'scope.txt')
    raise ScopeError('Falta target.yaml o scope.txt; no se autoriza tráfico.')


def endpoint_matches(target, endpoint):
    if not target.lower().startswith(('http://', 'https://')):
        return False
    candidate, rule = urllib.parse.urlsplit(target), urllib.parse.urlsplit(endpoint)
    if (candidate.scheme.lower(), normalize_target(target), candidate.port or (443 if candidate.scheme.lower() == 'https' else 80)) != (
            rule.scheme.lower(), normalize_target(endpoint), rule.port or (443 if rule.scheme.lower() == 'https' else 80)):
        return False
    path = rule.path.rstrip('/')
    return (candidate.path or '/') == (path or '/') or (candidate.path or '/').startswith(path + '/')


def check_scope(target, scope_data):
    validate_scope(scope_data)
    raw_target = target
    target = normalize_target(target)
    if not target:
        return 'UNKNOWN', 'Objetivo inválido o no autorizado'
    address = ipaddress.ip_address(target) if is_ip(target) else None
    for section, verdict in (('out_of_scope', 'OUT_OF_SCOPE'), ('in_scope', 'IN_SCOPE')):
        rules = scope_data['scope'].get(section, {})
        for value in rules.get('endpoints', []):
            if endpoint_matches(raw_target, value):
                return verdict, f'Endpoint: {value}'
        if address:
            for value in rules.get('ips', []):
                if target == normalize_target(value):
                    return verdict, f'IP: {value}'
            for value in rules.get('cidrs', []):
                network = ipaddress.ip_network(value.strip(), strict=False)
                candidate = ipaddress.IPv6Address('::ffff:' + str(address)) if address.version == 4 and network.version == 6 and network.network_address.ipv4_mapped else address
                if candidate in network:
                    return verdict, f'CIDR: {value}'
        else:
            for value in rules.get('domains', []):
                if domain_matches(target, value.strip().lower()):
                    return verdict, f'Dominio: {value}'
    return 'UNKNOWN', 'Objetivo no listado en el alcance explícito'
