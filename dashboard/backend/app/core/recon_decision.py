import datetime
from app.core.recon_jobs import TERMINAL_STATUSES


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
