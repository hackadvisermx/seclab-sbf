import datetime
import re
from app.core.artifact_snapshot import HASH_LIMIT, RECON_STAGE_ARTIFACTS


METRICS = ('subdomains_count', 'subdomains_discarded_out_of_scope', 'subdomains_new_count',
           'live_hosts_count', 'live_hosts_new_count', 'urls_count', 'js_files_count')
STAGE_COUNTS = {
    'subdomains': ('total_raw', 'in_scope_count', 'discarded_count', 'new_count'),
    'probe': ('live_hosts_count', 'discarded_count', 'blocked_dns_count', 'new_count', 'next_commands_count'),
    'urls': ('urls_count', 'js_files_count'),
    'patterns': (),
}
PATTERNS = ('xss', 'sqli', 'ssrf', 'redirect', 'idor', 'rce', 'lfi')


def _counts(value, allowed):
    if not isinstance(value, dict) or set(value) - set(allowed):
        raise ValueError('Conteos de resultados inválidos.')
    if any(type(count) is not int or not 0 <= count <= 9007199254740991 for count in value.values()):
        raise ValueError('Conteos de resultados inválidos.')


def validate_result_summary(value, run_id, stage, status, scope_revision, dry_run):
    fields = {'schema_version', 'run_id', 'scope_revision', 'recorded_at', 'metrics_source', 'metrics', 'stages'}
    if (dry_run or status not in ('completed', 'failed', 'blocked') or not isinstance(value, dict)
            or set(value) != fields or type(value['schema_version']) is not int or value['schema_version'] not in (1, 2, 3)
            or value['run_id'] != run_id or value['scope_revision'] != scope_revision
            or not isinstance(scope_revision, str) or not re.fullmatch(r'[a-f0-9]{64}', scope_revision)):
        raise ValueError('Resumen no corresponde al job finalizado.')
    if value['schema_version'] >= 2 and (not isinstance(run_id, str) or not re.fullmatch(r'[a-f0-9]{32}', run_id)):
        raise ValueError('Identificador del job inválido.')
    timestamp = datetime.datetime.fromisoformat(value['recorded_at'])
    if timestamp.tzinfo is None or timestamp.utcoffset() != datetime.timedelta(0):
        raise ValueError('Fecha de resultados inválida.')
    expected_source = 'artifacts' if status == 'completed' else 'previous_artifacts'
    if value['metrics_source'] != expected_source:
        raise ValueError('Fuente de métricas inconsistente.')
    _counts(value['metrics'], METRICS)
    if set(value['metrics']) != set(METRICS):
        raise ValueError('Conteos de resultados incompletos.')
    steps = value['stages']
    if not isinstance(steps, list) or not 1 <= len(steps) <= 4:
        raise ValueError('Etapas de resultados inválidas.')
    names = []
    current_seen = False
    artifact_bytes = 0
    for step in steps:
        step_fields = {'stage', 'status', 'counts', 'patterns', 'failure_kind'}
        if value['schema_version'] >= 2:
            step_fields |= {'execution', 'origin_run_id'}
        if value['schema_version'] == 3:
            step_fields.add('artifact_capture')
        if not isinstance(step, dict) or set(step) != step_fields:
            raise ValueError('Etapa de resultados inválida.')
        name = step['stage']
        if name not in STAGE_COUNTS or step['status'] not in ('completed', 'failed'):
            raise ValueError('Estado de etapa inválido.')
        names.append(name)
        if value['schema_version'] >= 2:
            origin = step['origin_run_id']
            if origin is not None and (not isinstance(origin, str) or not re.fullmatch(r'[a-f0-9]{32}', origin)):
                raise ValueError('Origen de etapa inválido.')
            if step['execution'] == 'current':
                if origin != run_id:
                    raise ValueError('Etapa actual no corresponde al job.')
                current_seen = True
            elif step['execution'] == 'recovered':
                if stage != 'all' or current_seen or step['status'] != 'completed' or origin == run_id:
                    raise ValueError('Etapa recuperada inconsistente.')
            else:
                raise ValueError('Ejecución de etapa inválida.')
        if value['schema_version'] == 3:
            capture = step['artifact_capture']
            if step['status'] == 'failed':
                if capture is not None:
                    raise ValueError('Etapa fallida no puede declarar artefactos completados.')
            else:
                if not isinstance(capture, dict) or set(capture) != {'status', 'refs'} or not isinstance(capture['refs'], list):
                    raise ValueError('Captura de artefactos inválida.')
                if capture['status'] == 'unavailable':
                    if capture['refs'] or stage == 'all' or step['execution'] != 'current':
                        raise ValueError('Captura no disponible inconsistente.')
                elif capture['status'] == 'recorded':
                    paths = ['recon/' + path for path in RECON_STAGE_ARTIFACTS[name]]
                    if len(capture['refs']) != len(paths):
                        raise ValueError('Inventario de artefactos incompleto.')
                    for ref, path in zip(capture['refs'], paths):
                        if (not isinstance(ref, dict) or set(ref) != {'path', 'sha256', 'size'} or ref['path'] != path
                                or not isinstance(ref['sha256'], str) or not re.fullmatch(r'[a-f0-9]{64}', ref['sha256'])
                                or type(ref['size']) is not int or not 0 <= ref['size'] <= HASH_LIMIT):
                            raise ValueError('Versión de artefacto inválida.')
                        artifact_bytes += ref['size']
                else:
                    raise ValueError('Estado de captura inválido.')
        _counts(step['counts'], STAGE_COUNTS[name])
        _counts(step['patterns'], PATTERNS if name == 'patterns' else ())
        if step['status'] == 'failed':
            if step['counts'] or step['patterns'] or step['failure_kind'] not in ('scope_guard', 'technical'):
                raise ValueError('Fallo de etapa inválido.')
        elif (step['failure_kind'] is not None or set(step['counts']) != set(STAGE_COUNTS[name])
              or (name == 'patterns' and set(step['patterns']) != set(PATTERNS))):
            raise ValueError('Estado o conteos de etapa incompletos.')
    expected_names = list(STAGE_COUNTS)[:len(names)] if stage == 'all' else [stage]
    if artifact_bytes > HASH_LIMIT:
        raise ValueError('Límite de huellas excedido.')
    if value['schema_version'] >= 2 and not current_seen:
        raise ValueError('Resumen sin intento del job actual.')
    if names != expected_names:
        raise ValueError('Etapas no corresponden a la ejecución.')
    expected_statuses = ['completed'] * len(steps)
    if status != 'completed':
        expected_statuses[-1] = 'failed'
        if status == 'blocked' and steps[-1]['failure_kind'] != 'scope_guard':
            raise ValueError('Bloqueo de etapa inconsistente.')
    elif stage == 'all' and len(steps) != 4:
        raise ValueError('Ejecución completa sin todas las etapas.')
    if [step['status'] for step in steps] != expected_statuses:
        raise ValueError('Etapas incompletas o inconsistentes.')
    return value


def result_summary(raw, run_id, stage, status, dry_run):
    try:
        if (not isinstance(raw, dict) or raw.get('run_id') != run_id or raw.get('dry_run') is not False
                or raw.get('status') != ('completed' if status == 'completed' else 'failed')):
            return None
        stages = raw['stage_results']
        if not isinstance(stages, dict):
            return None
        version = 3 if 'stage_artifacts' in raw else 2 if 'stages_recovered' in raw else 1
        if version == 1:
            if (raw['stages_executed'] != list(stages)
                    or any('execution' in step or 'origin_run_id' in step for step in stages.values())):
                return None
        else:
            if (raw['stages_executed'] != [name for name, step in stages.items() if step['execution'] == 'current']
                    or raw['stages_recovered'] != [name for name, step in stages.items() if step['execution'] == 'recovered']):
                return None
        if version == 3:
            captures = raw['stage_artifacts']
            if (not isinstance(captures, dict) or set(captures) != {name for name, step in stages.items() if step['status'] == 'completed'}):
                return None
        timestamp = datetime.datetime.fromisoformat(raw['timestamp'])
        if timestamp.tzinfo is None:
            return None
        value = {
            'schema_version': version, 'run_id': run_id, 'scope_revision': raw['scope_revision'],
            'recorded_at': timestamp.astimezone(datetime.timezone.utc).isoformat(),
            'metrics_source': raw['metrics_source'], 'metrics': {key: raw[key] for key in METRICS},
            'stages': [{
                'stage': name, 'status': step['status'],
                'counts': {key: step[key] for key in STAGE_COUNTS[name] if key in step} if step['status'] == 'completed' else {},
                'patterns': {key: count for key, count in step.get('patterns', {}).items() if key in PATTERNS}
                            if name == 'patterns' and step['status'] == 'completed' else {},
                'failure_kind': step.get('failure_kind') if step['status'] == 'failed' else None,
                **({'execution': step['execution'], 'origin_run_id': step['origin_run_id']} if version >= 2 else {}),
                **({'artifact_capture': captures.get(name)} if version == 3 else {}),
            } for name, step in stages.items()],
        }
        return validate_result_summary(value, run_id, stage, status, raw['scope_revision'], dry_run)
    except (KeyError, ValueError, TypeError, AttributeError, OverflowError):
        return None
