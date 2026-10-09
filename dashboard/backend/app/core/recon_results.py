import datetime
import re


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
            or set(value) != fields or type(value['schema_version']) is not int or value['schema_version'] != 1
            or value['run_id'] != run_id or value['scope_revision'] != scope_revision
            or not isinstance(scope_revision, str) or not re.fullmatch(r'[a-f0-9]{64}', scope_revision)):
        raise ValueError('Resumen no corresponde al job finalizado.')
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
    for step in steps:
        if not isinstance(step, dict) or set(step) != {'stage', 'status', 'counts', 'patterns', 'failure_kind'}:
            raise ValueError('Etapa de resultados inválida.')
        name = step['stage']
        if name not in STAGE_COUNTS or step['status'] not in ('completed', 'failed'):
            raise ValueError('Estado de etapa inválido.')
        names.append(name)
        _counts(step['counts'], STAGE_COUNTS[name])
        _counts(step['patterns'], PATTERNS if name == 'patterns' else ())
        if step['status'] == 'failed':
            if step['counts'] or step['patterns'] or step['failure_kind'] not in ('scope_guard', 'technical'):
                raise ValueError('Fallo de etapa inválido.')
        elif (step['failure_kind'] is not None or set(step['counts']) != set(STAGE_COUNTS[name])
              or (name == 'patterns' and set(step['patterns']) != set(PATTERNS))):
            raise ValueError('Estado o conteos de etapa incompletos.')
    expected_names = list(STAGE_COUNTS)[:len(names)] if stage == 'all' else [stage]
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
        if not isinstance(stages, dict) or raw['stages_executed'] != list(stages):
            return None
        timestamp = datetime.datetime.fromisoformat(raw['timestamp'])
        if timestamp.tzinfo is None:
            return None
        value = {
            'schema_version': 1, 'run_id': run_id, 'scope_revision': raw['scope_revision'],
            'recorded_at': timestamp.astimezone(datetime.timezone.utc).isoformat(),
            'metrics_source': raw['metrics_source'], 'metrics': {key: raw[key] for key in METRICS},
            'stages': [{
                'stage': name, 'status': step['status'],
                'counts': {key: step[key] for key in STAGE_COUNTS[name] if key in step} if step['status'] == 'completed' else {},
                'patterns': {key: count for key, count in step.get('patterns', {}).items() if key in PATTERNS}
                            if name == 'patterns' and step['status'] == 'completed' else {},
                'failure_kind': step.get('failure_kind') if step['status'] == 'failed' else None,
            } for name, step in stages.items()],
        }
        return validate_result_summary(value, run_id, stage, status, raw['scope_revision'], dry_run)
    except (KeyError, ValueError, TypeError, AttributeError, OverflowError):
        return None
