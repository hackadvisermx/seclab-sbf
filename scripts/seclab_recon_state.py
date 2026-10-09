import datetime
import hashlib
import json
import os
import pathlib
import re
import sqlite3
from contextlib import closing

TERMINAL_STATUSES = ('completed', 'simulated', 'failed', 'blocked', 'cancelled', 'interrupted')


def outcome_revision(job):
    """Bind a review to the stored outcome, not to the mutable workspace."""
    fields = ('engagement_type', 'engagement_id', 'run_id', 'status', 'stage', 'dry_run',
              'started_at', 'finished_at', 'error', 'scope_revision', 'reviewed_plan', 'result_summary')
    payload = {field: job.get(field) for field in fields}
    payload['dry_run'] = bool(payload['dry_run'])
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=True,
                                    separators=(',', ':')).encode()).hexdigest()


DECISIONS = {
    'running': ('Esperar el reconocimiento en ejecución',
        'El job sigue en ejecución. Revisa su progreso o solicita cancelación antes de iniciar otra actividad.', 'recon', 'Ver progreso'),
    'cancelling': ('Esperar la confirmación de cancelación',
        'Se solicitó cancelar, pero el job todavía no ha terminado. Revisa su progreso antes de iniciar otra actividad.', 'recon', 'Ver cancelación'),
    'blocked': ('Revisar alcance y autorización tras el bloqueo',
        'Scope Guard bloqueó el último job. Revisa el motivo en Reconocimiento y corrige el alcance o los permisos; después revisa un nuevo plan sin tráfico.', 'scope', 'Revisar alcance y autorización'),
    'failed': ('Revisar el fallo del reconocimiento',
        'El último job falló. Revisa su motivo y log en Reconocimiento antes de decidir si reintentas. Los archivos previos no acreditan que este job terminara correctamente.', 'recon', 'Revisar fallo y log'),
    'cancelled': ('Revisar el reconocimiento cancelado',
        'El último job fue cancelado. Revisa el historial y los resultados conservados antes de decidir cómo continuar; la cancelación no completa la etapa.', 'recon', 'Revisar job cancelado'),
    'interrupted': ('Revisar el reconocimiento interrumpido',
        'El último job quedó interrumpido tras detener o reiniciar el servicio. Revisa el historial antes de preparar un nuevo plan; no se considera completado.', 'recon', 'Revisar interrupción'),
}


def recon_decision(job):
    if not job:
        return None
    reviewed = job.get('outcome_review') and job.get('status') in TERMINAL_STATUSES
    if not reviewed and job.get('status') not in DECISIONS:
        return None
    if reviewed:
        decision_id = 'recon_prepare_plan'
        title = 'Preparar otro plan tras revisar el resultado'
        reason = ('La revisión del operador quedó registrada. El estado original del job se conserva; '
                  'revisar no confirma resultados ni concede permisos. Revisa el alcance actual y prepara '
                  'un nuevo plan sin tráfico antes de decidir si lo ejecutas.')
        view, label = 'recon', 'Preparar un nuevo plan'
    else:
        title, reason, view, label = DECISIONS[job['status']]
        decision_id = 'recon_' + job['status']
    return {
        'timestamp': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'decision_job': {key: job[key] for key in ('run_id', 'status', 'stage', 'dry_run')},
        'outcome_review': job.get('outcome_review'),
        'next_step': {
            'id': decision_id, 'phase': 'Reconocimiento',
            'title': title, 'reason': reason, 'command': None,
            'ready_for_closure': False,
            'action': {'view': view, 'label': label},
        },
        'prompt_available': False,
        'prompt': '',
    }


def unavailable_decision():
    return {'next_step': {'id': 'recon_state_unavailable', 'phase': 'Reconocimiento',
        'title': 'Revisar el estado persistido del reconocimiento',
        'reason': 'No se pudo leer un estado válido del reconocimiento. Revisa el servicio y su historial antes de decidir otra actividad.',
        'command': None, 'ready_for_closure': False,
        'action': {'view': 'recon', 'label': 'Revisar historial'}},
        'prompt_available': False, 'prompt': ''}


def read_current_job(project, workspace, database):
    project, workspace, database = map(pathlib.Path, (project, workspace, database))
    project, workspace = project.resolve(), workspace.resolve()
    if project.parent.parent != workspace or project.parent.name not in ('engagements', 'retos'):
        return None
    if not re.fullmatch(r'[A-Za-z0-9_.-]{1,128}', project.name):
        raise ValueError('Proyecto inválido.')
    key = ('reto' if project.parent.name == 'retos' else 'engagement', project.name)
    if database.parent.is_symlink():
        raise ValueError('Estado no válido.')
    database = database.parent.resolve() / database.name
    if any(path.is_symlink() for path in (database,
            pathlib.Path(str(database)+'-wal'), pathlib.Path(str(database)+'-shm'),
            pathlib.Path(str(database)+'-journal'))):
        raise ValueError('Estado no válido.')
    if not database.exists():
        return None
    identity = database.stat()
    with closing(sqlite3.connect(database.resolve().as_uri()+'?mode=ro', uri=True, timeout=1)) as conn:
        conn.row_factory = sqlite3.Row
        conn.execute('PRAGMA query_only=ON')
        conn.execute('BEGIN')
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name IN ('recon_jobs', 'recon_job_history', 'recon_job_reviews', 'recon_job_results', 'recon_job_outcome_reviews')")}
        if 'recon_jobs' not in tables:
            raise ValueError('Estado sin tabla de jobs.')
        rows = conn.execute('SELECT * FROM recon_jobs WHERE engagement_type=? AND engagement_id=? LIMIT 2', key).fetchall()
        if not rows:
            return None
        if len(rows) != 1:
            raise ValueError('Estado ambiguo.')
        job = dict(rows[0])
        required = ('run_id', 'status', 'stage', 'dry_run', 'started_at', 'finished_at', 'error')
        if (any(field not in job for field in required)
                or not isinstance(job['run_id'], str) or not re.fullmatch(r'[a-f0-9]{32}', job['run_id'])
                or job['status'] not in (*TERMINAL_STATUSES, 'running', 'cancelling')
                or job['stage'] not in ('all', 'subdomains', 'probe', 'urls', 'patterns')
                or type(job['dry_run']) is not int or job['dry_run'] not in (0, 1)):
            raise ValueError('Job inválido.')
        for field in ('started_at', 'finished_at'):
            value = job[field]
            if field == 'finished_at' and value is None and job['status'] not in TERMINAL_STATUSES:
                continue
            if not isinstance(value, str) or len(value) > 128:
                raise ValueError('Timestamp inválido.')
            timestamp = datetime.datetime.fromisoformat(value[:-1] + '+00:00' if value.endswith('Z') else value)
            if timestamp.utcoffset() is None:
                raise ValueError('Timestamp sin zona.')
        if job['error'] is not None and (not isinstance(job['error'], str) or len(job['error']) > 65536):
            raise ValueError('Metadata inválida.')
        job['dry_run'] = bool(job['dry_run'])
        job.update(scope_revision=None, reviewed_plan=None, result_summary=None, outcome_review=None)
        if 'recon_job_history' in tables:
            history = conn.execute('SELECT scope_revision FROM recon_job_history WHERE engagement_type=? AND engagement_id=? AND run_id=?', (*key, job['run_id'])).fetchone()
            if history:
                job['scope_revision'] = history['scope_revision']
        for table, column, limit in (('recon_job_reviews', 'reviewed_plan', 192*1024),
                                     ('recon_job_results', 'result_summary', 16384)):
            if table in tables:
                extra = conn.execute(f'SELECT substr({column},1,?), length({column}) FROM {table} WHERE engagement_type=? AND engagement_id=? AND run_id=?', (limit+1, *key, job['run_id'])).fetchone()
                if extra:
                    if extra[1] > limit:
                        raise ValueError('Metadata demasiado grande.')
                    job[column] = extra[0]
        if (job['status'] in TERMINAL_STATUSES and job['finished_at']
                and 'recon_job_outcome_reviews' in tables):
            review = conn.execute('SELECT job_revision, reviewed_at FROM recon_job_outcome_reviews WHERE engagement_type=? AND engagement_id=? AND run_id=?', (*key, job['run_id'])).fetchone()
            if review and isinstance(review['reviewed_at'], str) and review['job_revision'] == outcome_revision(job):
                try:
                    value = review['reviewed_at']
                    timestamp = datetime.datetime.fromisoformat(value[:-1] + '+00:00' if value.endswith('Z') else value)
                    if timestamp.utcoffset() == datetime.timedelta(0):
                        job['outcome_review'] = {'job_revision': review['job_revision'],
                            'reviewed_at': review['reviewed_at'], 'decision': 'prepare_new_plan'}
                except (ValueError, TypeError):
                    pass
    current = database.stat()
    if (current.st_dev, current.st_ino) != (identity.st_dev, identity.st_ino) or database.is_symlink():
        raise ValueError('Estado reemplazado durante lectura.')
    return job


def project_recon_decision(project):
    root = pathlib.Path(os.environ.get('REPO_ROOT', pathlib.Path(__file__).resolve().parent.parent))
    workspace = os.environ.get('WORKSPACE_DIR', os.environ.get('SECLAB_WORKSPACE_DIR',
        '/workspace' if pathlib.Path('/workspace').exists() else str(root/'workspace')))
    data = pathlib.Path(os.environ.get('SECLAB_DATA_DIR', '/var/lib/seclab/dashboard'
        if pathlib.Path('/var/lib/seclab').exists() else str(root/'dashboard/backend/data')))
    try:
        return recon_decision(read_current_job(project, workspace, data/'recon-jobs.db'))
    except (OSError, ValueError, TypeError, sqlite3.Error):
        return unavailable_decision()
