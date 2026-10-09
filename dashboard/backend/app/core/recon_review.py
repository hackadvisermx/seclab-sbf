import urllib.parse


def target_host(value):
    try:
        parsed = urllib.parse.urlsplit(value if '://' in value else '//' + value)
        return (parsed.hostname or '[target omitido]')[:253]
    except ValueError:
        return '[target omitido]'


def reviewed_plan(preview):
    authorization = preview['authorization']
    for key in ('reference_present', 'allow_passive', 'allow_active'):
        if type(authorization[key]) is not bool:
            raise ValueError('Permisos de revisión inválidos.')
    return {
        'schema_version': 1,
        'checked_at': preview['generated_at'],
        'plan_revision': preview['plan_revision'],
        'scope_revision': preview['scope_revision'],
        'stage': preview['stage'],
        'dry_run': preview['dry_run'],
        'can_start': preview['can_start'],
        'authorization': {key: authorization[key] for key in (
            'reference_present', 'allow_passive', 'allow_active', 'valid_from', 'valid_until')},
        'operational_limits': dict(preview['operational_limits']),
        'target_representation': 'host-only',
        'stages': [{
            'stage': step['stage'], 'interaction': step['interaction'],
            'targets_pending': step['targets_pending'],
            'targets_count': step['targets_count'],
            'discarded_count': step['discarded_count'],
            'targets': [{'host': target_host(target), 'verdict': 'PASSIVE_SOURCE' if step['interaction'] == 'passive' else 'IN_SCOPE'}
                        for target in step['targets'][:50]],
            'discarded': [{'host': target_host(target['target']), 'verdict': target['verdict']}
                          for target in step['discarded'][:50]],
        } for step in preview['stages']],
    }
