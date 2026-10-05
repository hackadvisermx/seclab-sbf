import datetime
import os
import pathlib
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

    def begin(self, key, stage, dry_run):
        with closing(self.connect()) as conn, conn:
            conn.execute('BEGIN IMMEDIATE')
            current = conn.execute('SELECT status FROM recon_jobs WHERE engagement_type=? AND engagement_id=?', key).fetchone()
            if current and current['status'] in ACTIVE_STATUSES:
                raise RuntimeError('Ya hay una tarea de reconocimiento activa en este proyecto.')
            conn.execute('''INSERT OR REPLACE INTO recon_jobs VALUES (?, ?, ?, ?, ?, ?, ?, NULL, NULL)''',
                         (*key, uuid.uuid4().hex, 'running', stage, int(dry_run), now()))
        return self.get(key)

    def finish(self, key, run_id, status, error=None):
        with closing(self.connect()) as conn, conn:
            conn.execute('''UPDATE recon_jobs SET status=?, finished_at=?, error=?
                WHERE engagement_type=? AND engagement_id=? AND run_id=? AND status IN ('running', 'cancelling')''',
                         (status, now(), error, *key, run_id))

    def request_cancel(self, key):
        with closing(self.connect()) as conn, conn:
            conn.execute("UPDATE recon_jobs SET status='cancelling' WHERE engagement_type=? AND engagement_id=? AND status='running'", key)
        return self.get(key)

    def recover(self):
        with closing(self.connect()) as conn, conn:
            conn.execute('''UPDATE recon_jobs SET status='interrupted', finished_at=?, error=?
                WHERE status IN ('running', 'cancelling')''',
                         (now(), 'Ejecución interrumpida por reinicio del dashboard. No se reanudó automáticamente.'))

    def delete(self, key):
        with closing(self.connect()) as conn, conn:
            conn.execute('DELETE FROM recon_jobs WHERE engagement_type=? AND engagement_id=?', key)
