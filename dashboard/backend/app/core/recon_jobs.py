import datetime
import json
import os
import pathlib
import re
import sqlite3
import uuid
from contextlib import closing
from app.core.recon_results import validate_result_summary
from app.core.recon_decision import outcome_revision, TERMINAL_STATUSES


ACTIVE_STATUSES = ('running', 'cancelling')


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


class ReconJobStore:
    def __init__(self, path):
        self.path = pathlib.Path(path)
        self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        if self.path.parent.is_symlink():
            raise ValueError('El estado de reconocimiento no admite enlaces simbólicos.')
        fd = os.open(self.path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        try:
            os.fchmod(fd, 0o600)
        finally:
            os.close(fd)
        with closing(self.connect()) as conn, conn:
            conn.execute('''CREATE TABLE IF NOT EXISTS recon_jobs (
                engagement_type TEXT NOT NULL, engagement_id TEXT NOT NULL,
                run_id TEXT NOT NULL, status TEXT NOT NULL, stage TEXT NOT NULL,
                dry_run INTEGER NOT NULL, started_at TEXT NOT NULL,
                finished_at TEXT, error TEXT,
                PRIMARY KEY (engagement_type, engagement_id))''')
            conn.execute("""CREATE TABLE IF NOT EXISTS recon_job_history (
                engagement_type TEXT NOT NULL, engagement_id TEXT NOT NULL,
                run_id TEXT NOT NULL, status TEXT NOT NULL, stage TEXT NOT NULL,
                dry_run INTEGER NOT NULL, started_at TEXT NOT NULL,
                finished_at TEXT, error TEXT, scope_revision TEXT,
                origin TEXT NOT NULL, PRIMARY KEY (engagement_type, engagement_id, run_id))""")
            conn.execute("""CREATE INDEX IF NOT EXISTS recon_history_project
                ON recon_job_history (engagement_type, engagement_id, started_at DESC, run_id DESC)""")
            conn.execute("""CREATE TABLE IF NOT EXISTS recon_job_reviews (
                engagement_type TEXT NOT NULL, engagement_id TEXT NOT NULL,
                run_id TEXT NOT NULL, reviewed_plan TEXT NOT NULL,
                PRIMARY KEY (engagement_type, engagement_id, run_id))""")
            conn.execute("""CREATE TABLE IF NOT EXISTS recon_job_results (
                engagement_type TEXT NOT NULL, engagement_id TEXT NOT NULL,
                run_id TEXT NOT NULL, result_summary TEXT NOT NULL,
                PRIMARY KEY (engagement_type, engagement_id, run_id))""")
            conn.execute("""CREATE TABLE IF NOT EXISTS recon_job_outcome_reviews (
                engagement_type TEXT NOT NULL, engagement_id TEXT NOT NULL,
                run_id TEXT NOT NULL, job_revision TEXT NOT NULL, reviewed_at TEXT NOT NULL,
                PRIMARY KEY (engagement_type, engagement_id, run_id))""")
            # Only the last legacy row is known; never reconstruct older jobs.
            conn.execute("""INSERT OR IGNORE INTO recon_job_history
                SELECT engagement_type, engagement_id, run_id, status, stage, dry_run,
                       started_at, finished_at, error, NULL, 'legacy-current'
                FROM recon_jobs""")
            # A downgrade may update the current row without knowing the history table.
            conn.execute("""UPDATE recon_job_history SET (status, finished_at, error) =
                (SELECT status, finished_at, error FROM recon_jobs
                 WHERE recon_jobs.engagement_type=recon_job_history.engagement_type
                   AND recon_jobs.engagement_id=recon_job_history.engagement_id
                   AND recon_jobs.run_id=recon_job_history.run_id)
                WHERE EXISTS (SELECT 1 FROM recon_jobs
                 WHERE recon_jobs.engagement_type=recon_job_history.engagement_type
                   AND recon_jobs.engagement_id=recon_job_history.engagement_id
                   AND recon_jobs.run_id=recon_job_history.run_id)""")
            conn.execute("""DELETE FROM recon_job_reviews WHERE NOT EXISTS (
                SELECT 1 FROM recon_job_history WHERE
                    recon_job_history.engagement_type=recon_job_reviews.engagement_type
                    AND recon_job_history.engagement_id=recon_job_reviews.engagement_id
                    AND recon_job_history.run_id=recon_job_reviews.run_id)""")
            conn.execute("""DELETE FROM recon_job_results WHERE NOT EXISTS (
                SELECT 1 FROM recon_job_history WHERE
                    recon_job_history.engagement_type=recon_job_results.engagement_type
                    AND recon_job_history.engagement_id=recon_job_results.engagement_id
                    AND recon_job_history.run_id=recon_job_results.run_id)""")
            conn.execute("""DELETE FROM recon_job_outcome_reviews WHERE NOT EXISTS (
                SELECT 1 FROM recon_job_history WHERE
                    recon_job_history.engagement_type=recon_job_outcome_reviews.engagement_type
                    AND recon_job_history.engagement_id=recon_job_outcome_reviews.engagement_id
                    AND recon_job_history.run_id=recon_job_outcome_reviews.run_id)""")
        self.path.chmod(0o600)

    def connect(self):
        if self.path.parent.is_symlink() or any(path.is_symlink() for path in (
                self.path, pathlib.Path(str(self.path) + '-journal'),
                pathlib.Path(str(self.path) + '-wal'), pathlib.Path(str(self.path) + '-shm'))):
            raise ValueError('El estado de reconocimiento no admite enlaces simbólicos.')
        conn = sqlite3.connect(self.path, timeout=5)
        conn.row_factory = sqlite3.Row
        conn.execute('PRAGMA synchronous=FULL')
        return conn

    @staticmethod
    def job(row):
        if row is None:
            return None
        result = dict(row)
        result['dry_run'] = bool(result['dry_run'])
        revision = outcome_revision(result)
        reviewed_revision = result.pop('outcome_review_revision', None)
        reviewed_at = result.pop('outcome_reviewed_at', None)
        result['outcome_revision'] = revision
        result['outcome_review'] = None
        if (result['status'] in TERMINAL_STATUSES and result.get('finished_at')
                and reviewed_revision == revision and isinstance(reviewed_at, str)):
            try:
                timestamp = datetime.datetime.fromisoformat(reviewed_at)
                if timestamp.utcoffset() != datetime.timedelta(0):
                    raise ValueError('Revisión sin timestamp UTC.')
                result['outcome_review'] = {'job_revision': revision,
                    'reviewed_at': reviewed_at, 'decision': 'prepare_new_plan'}
            except ValueError:
                pass
        if 'reviewed_plan' in result and result['reviewed_plan'] is not None:
            try:
                plan = json.loads(result['reviewed_plan'])
                result['reviewed_plan'] = plan if isinstance(plan, dict) and plan.get('schema_version') == 1 else None
            except (ValueError, TypeError):
                result['reviewed_plan'] = None
        if 'result_summary' in result and result['result_summary'] is not None:
            try:
                if len(result['result_summary']) > 16384:
                    raise ValueError('Resumen de resultados demasiado grande.')
                result['result_summary'] = validate_result_summary(json.loads(result['result_summary']),
                    result['run_id'], result['stage'], result['status'], result['scope_revision'], result['dry_run'])
            except (ValueError, TypeError, KeyError, OverflowError):
                result['result_summary'] = None
        return result

    CURRENT_QUERY = '''SELECT c.*, h.scope_revision, h.origin, r.reviewed_plan, s.result_summary,
        o.job_revision AS outcome_review_revision, o.reviewed_at AS outcome_reviewed_at
        FROM recon_jobs c
        LEFT JOIN recon_job_history h ON c.engagement_type=h.engagement_type
            AND c.engagement_id=h.engagement_id AND c.run_id=h.run_id
        LEFT JOIN recon_job_reviews r ON c.engagement_type=r.engagement_type
            AND c.engagement_id=r.engagement_id AND c.run_id=r.run_id
        LEFT JOIN recon_job_results s ON c.engagement_type=s.engagement_type
            AND c.engagement_id=s.engagement_id AND c.run_id=s.run_id
        LEFT JOIN recon_job_outcome_reviews o ON c.engagement_type=o.engagement_type
            AND c.engagement_id=o.engagement_id AND c.run_id=o.run_id
        WHERE c.engagement_type=? AND c.engagement_id=?'''

    def get(self, key):
        with closing(self.connect()) as conn:
            return self.job(conn.execute(self.CURRENT_QUERY, key).fetchone())

    def review_outcome(self, key, run_id, expected_revision):
        with closing(self.connect()) as conn, conn:
            conn.execute('BEGIN IMMEDIATE')
            job = self.job(conn.execute(self.CURRENT_QUERY, key).fetchone())
            if (not job or job['run_id'] != run_id or job['status'] not in TERMINAL_STATUSES
                    or not job['finished_at'] or job.get('origin') not in ('dashboard', 'legacy-current')
                    or job['outcome_revision'] != expected_revision):
                raise RuntimeError('El job cambió o sigue activo. Actualiza el historial y revisa el resultado actual.')
            if job['outcome_review'] is None:
                conn.execute('INSERT OR REPLACE INTO recon_job_outcome_reviews VALUES (?, ?, ?, ?, ?)',
                             (*key, run_id, expected_revision, now()))
            return self.job(conn.execute(self.CURRENT_QUERY, key).fetchone())

    def history(self, key, limit=25, before=None):
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError('El límite de historial debe estar entre 1 y 100.')
        with closing(self.connect()) as conn:
            query = '''SELECT h.*, r.reviewed_plan, s.result_summary,
                o.job_revision AS outcome_review_revision, o.reviewed_at AS outcome_reviewed_at
                FROM recon_job_history h
                LEFT JOIN recon_job_reviews r ON h.engagement_type=r.engagement_type
                    AND h.engagement_id=r.engagement_id AND h.run_id=r.run_id
                LEFT JOIN recon_job_results s ON h.engagement_type=s.engagement_type
                    AND h.engagement_id=s.engagement_id AND h.run_id=s.run_id
                LEFT JOIN recon_job_outcome_reviews o ON h.engagement_type=o.engagement_type
                    AND h.engagement_id=o.engagement_id AND h.run_id=o.run_id
                WHERE h.engagement_type=? AND h.engagement_id=?'''
            args = list(key)
            if before:
                cursor = conn.execute('SELECT started_at, run_id FROM recon_job_history '
                    'WHERE engagement_type=? AND engagement_id=? AND run_id=?', (*key, before)).fetchone()
                if cursor is None:
                    raise ValueError('El cursor no pertenece al historial de este proyecto.')
                query += ' AND (h.started_at, h.run_id) < (?, ?)'
                args.extend((cursor['started_at'], cursor['run_id']))
            query += ' ORDER BY h.started_at DESC, h.run_id DESC LIMIT ?'
            rows = conn.execute(query, (*args, limit + 1)).fetchall()
        jobs = [self.job(row) for row in rows[:limit]]
        return {'jobs': jobs, 'next_cursor': jobs[-1]['run_id'] if len(rows) > limit else None}

    def begin(self, key, stage, dry_run, reviewed_plan=None):
        payload = json.dumps(reviewed_plan, ensure_ascii=False, separators=(',', ':')) if reviewed_plan is not None else None
        if payload is not None and len(payload.encode('utf-8')) > 192 * 1024:
            raise ValueError('La revisión excede el límite de metadatos del job.')
        with closing(self.connect()) as conn, conn:
            conn.execute('BEGIN IMMEDIATE')
            current = conn.execute('SELECT status FROM recon_jobs WHERE engagement_type=? AND engagement_id=?', key).fetchone()
            if current and current['status'] in ACTIVE_STATUSES:
                raise RuntimeError('Ya hay una tarea de reconocimiento activa en este proyecto.')
            conn.execute('''INSERT OR REPLACE INTO recon_jobs VALUES (?, ?, ?, ?, ?, ?, ?, NULL, NULL)''',
                         (*key, uuid.uuid4().hex, 'running', stage, int(dry_run), now()))
            conn.execute("""INSERT INTO recon_job_history
                SELECT engagement_type, engagement_id, run_id, status, stage, dry_run,
                       started_at, finished_at, error, NULL, 'dashboard'
                FROM recon_jobs WHERE engagement_type=? AND engagement_id=?""", key)
            if payload is not None:
                conn.execute("""INSERT INTO recon_job_reviews
                    SELECT engagement_type, engagement_id, run_id, ? FROM recon_jobs
                    WHERE engagement_type=? AND engagement_id=?""", (payload, *key))
        return self.get(key)

    def finish(self, key, run_id, status, error=None, scope_revision=None, result_summary=None):
        if status not in TERMINAL_STATUSES:
            raise ValueError('Estado final de reconocimiento no válido.')
        if scope_revision is not None and (not isinstance(scope_revision, str) or not re.fullmatch(r'[a-f0-9]{64}', scope_revision)):
            raise ValueError('Revisión de alcance no válida.')
        timestamp = now()
        with closing(self.connect()) as conn, conn:
            payload = None
            if result_summary is not None:
                current = conn.execute('SELECT stage, dry_run FROM recon_jobs WHERE engagement_type=? AND engagement_id=? AND run_id=?', (*key, run_id)).fetchone()
                if current is None:
                    return
                validate_result_summary(result_summary, run_id, current['stage'], status, scope_revision, bool(current['dry_run']))
                payload = json.dumps(result_summary, ensure_ascii=True, separators=(',', ':'))
                if len(payload) > 16384:
                    raise ValueError('Resumen de resultados demasiado grande.')
            changed = conn.execute("""UPDATE recon_jobs SET status=?, finished_at=?, error=?
                WHERE engagement_type=? AND engagement_id=? AND run_id=? AND status IN ('running', 'cancelling')""",
                         (status, timestamp, error, *key, run_id)).rowcount
            if changed:
                conn.execute("""UPDATE recon_job_history SET status=?, finished_at=?, error=?, scope_revision=?
                    WHERE run_id=? AND engagement_type=? AND engagement_id=?""",
                    (status, timestamp, error, scope_revision, run_id, *key))
                if payload is not None:
                    conn.execute('INSERT INTO recon_job_results VALUES (?, ?, ?, ?)', (*key, run_id, payload))

    def request_cancel(self, key):
        with closing(self.connect()) as conn, conn:
            conn.execute("UPDATE recon_jobs SET status='cancelling' WHERE engagement_type=? AND engagement_id=? AND status='running'", key)
            conn.execute("""UPDATE recon_job_history SET status='cancelling'
                WHERE engagement_type=? AND engagement_id=?
                AND run_id=(SELECT run_id FROM recon_jobs WHERE engagement_type=? AND engagement_id=?)
                AND status='running'""", (*key, *key))
        return self.get(key)

    def recover(self):
        timestamp = now()
        message = 'Ejecución interrumpida por reinicio del dashboard. No se reanudó automáticamente.'
        with closing(self.connect()) as conn, conn:
            conn.execute("""UPDATE recon_jobs SET status='interrupted', finished_at=?, error=?
                WHERE status IN ('running', 'cancelling')""", (timestamp, message))
            conn.execute("""UPDATE recon_job_history SET status='interrupted', finished_at=?, error=?
                WHERE status IN ('running', 'cancelling')
                AND EXISTS (SELECT 1 FROM recon_jobs WHERE status='interrupted'
                    AND recon_jobs.engagement_type=recon_job_history.engagement_type
                    AND recon_jobs.engagement_id=recon_job_history.engagement_id
                    AND recon_jobs.run_id=recon_job_history.run_id)""", (timestamp, message))

    def delete(self, key):
        with closing(self.connect()) as conn, conn:
            conn.execute('DELETE FROM recon_jobs WHERE engagement_type=? AND engagement_id=?', key)
            conn.execute('DELETE FROM recon_job_history WHERE engagement_type=? AND engagement_id=?', key)
            conn.execute('DELETE FROM recon_job_reviews WHERE engagement_type=? AND engagement_id=?', key)
            conn.execute('DELETE FROM recon_job_results WHERE engagement_type=? AND engagement_id=?', key)
            conn.execute('DELETE FROM recon_job_outcome_reviews WHERE engagement_type=? AND engagement_id=?', key)
