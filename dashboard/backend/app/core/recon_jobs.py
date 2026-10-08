import datetime
import os
import pathlib
import re
import sqlite3
import uuid
from contextlib import closing


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
        return result

    def get(self, key):
        with closing(self.connect()) as conn:
            return self.job(conn.execute('SELECT * FROM recon_jobs WHERE engagement_type=? AND engagement_id=?', key).fetchone())

    def history(self, key, limit=25, before=None):
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError('El límite de historial debe estar entre 1 y 100.')
        with closing(self.connect()) as conn:
            query = 'SELECT * FROM recon_job_history WHERE engagement_type=? AND engagement_id=?'
            args = list(key)
            if before:
                cursor = conn.execute('SELECT started_at, run_id FROM recon_job_history '
                    'WHERE engagement_type=? AND engagement_id=? AND run_id=?', (*key, before)).fetchone()
                if cursor is None:
                    raise ValueError('El cursor no pertenece al historial de este proyecto.')
                query += ' AND (started_at, run_id) < (?, ?)'
                args.extend((cursor['started_at'], cursor['run_id']))
            query += ' ORDER BY started_at DESC, run_id DESC LIMIT ?'
            rows = conn.execute(query, (*args, limit + 1)).fetchall()
        jobs = [self.job(row) for row in rows[:limit]]
        return {'jobs': jobs, 'next_cursor': jobs[-1]['run_id'] if len(rows) > limit else None}

    def begin(self, key, stage, dry_run):
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
        return self.get(key)

    def finish(self, key, run_id, status, error=None, scope_revision=None):
        if status not in ('completed', 'simulated', 'failed', 'blocked', 'cancelled', 'interrupted'):
            raise ValueError('Estado final de reconocimiento no válido.')
        if scope_revision is not None and (not isinstance(scope_revision, str) or not re.fullmatch(r'[a-f0-9]{64}', scope_revision)):
            raise ValueError('Revisión de alcance no válida.')
        timestamp = now()
        with closing(self.connect()) as conn, conn:
            changed = conn.execute("""UPDATE recon_jobs SET status=?, finished_at=?, error=?
                WHERE engagement_type=? AND engagement_id=? AND run_id=? AND status IN ('running', 'cancelling')""",
                         (status, timestamp, error, *key, run_id)).rowcount
            if changed:
                conn.execute("""UPDATE recon_job_history SET status=?, finished_at=?, error=?, scope_revision=?
                    WHERE run_id=? AND engagement_type=? AND engagement_id=?""",
                    (status, timestamp, error, scope_revision, run_id, *key))

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
