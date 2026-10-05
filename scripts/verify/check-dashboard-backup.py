#!/usr/bin/env python3
"""Restauración real con imagen local y fixtures desechables sin red."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile
import uuid

ROOT = Path(__file__).resolve().parents[2]


def command(*args, **kwargs):
    return subprocess.check_output(list(args), text=True, **kwargs).strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image', default='seclab-sbf:full')
    args = parser.parse_args()
    image = json.loads(command('docker', 'image', 'inspect', args.image))[0]['Id']
    tag = 'phase90-fixture-' + uuid.uuid4().hex[:12]
    volumes, containers = [], []
    (ROOT / 'tmp').mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=tag, dir=ROOT / 'tmp') as temporary:
        directory = Path(temporary)
        workspaces = [directory / 'source', directory / 'restored']
        for ws in workspaces:
            ws.mkdir()
        try:
            for index, ws in enumerate(workspaces):
                volume = tag + '-' + str(index)
                command('docker', 'volume', 'create', volume)
                volumes.append(volume)
                cid = command('docker', 'create', '--network=none', '--read-only', '--cap-drop=ALL',
                              '--mount', f'type=bind,src={ws},dst=/workspace',
                              '--mount', f'type=volume,src={volume},dst=/var/lib/seclab',
                              '--entrypoint=/bin/true', image)
                containers.append(cid)
            env = ['-e', 'PYTHONPATH=/usr/local/share/seclab/dashboard/backend',
                   '-e', 'DASHBOARD_PASSWORD=phase90-local-fixture-only']
            seed = '''
from pathlib import Path
from app.core.database import init_db, get_db_connection
from app.core.security import encrypt_secret, create_session_token
from app.core.recon_jobs import ReconJobStore
from app.config import RECON_DB_PATH
init_db()
conn = get_db_connection()
with conn:
    conn.execute("INSERT INTO api_keys (provider,label,service_type,encrypted_key) VALUES (?,?,?,?)", ('fixture','fixture','llm',encrypt_secret('fixture-secret-local')))
    conn.execute("INSERT INTO dashboard_settings (key,value) VALUES ('fixture','preserved')")
conn.close()
create_session_token('tester')
store = ReconJobStore(RECON_DB_PATH)
store.begin(('reto', 'demo'), 'all', False)
Path(str(RECON_DB_PATH) + '.lock').touch(mode=0o600)
Path('/workspace/retos/demo').mkdir(parents=True)
Path('/workspace/retos/demo/evidence.md').write_text('fixture evidence')
'''
            command('docker', 'run', '--rm', '--network=none', '--volumes-from', containers[0],
                    *env, '--entrypoint=/opt/nxc/bin/python3', image, '-c', seed)
            tool = str(ROOT / 'scripts/host/dashboard-backup.py')
            destination = directory / 'backups'
            command('python3', tool, 'backup', '--container', containers[0], '--destination', str(destination))
            archive = next(destination.glob('*.tar.gz'))
            if archive.stat().st_uid != os.getuid() or archive.stat().st_mode & 0o777 != 0o600:
                raise AssertionError('Propietario o permisos del archivo incorrectos.')
            command('python3', tool, 'restore', '--container', containers[1], '--archive', str(archive))
            verify = '''
from pathlib import Path
from app.core.database import get_db_connection
from app.core.security import decrypt_secret
from app.core.recon_jobs import ReconJobStore
from app.config import RECON_DB_PATH, VAULT_KEY_PATH
conn = get_db_connection()
assert decrypt_secret(conn.execute("SELECT encrypted_key FROM api_keys WHERE provider='fixture'").fetchone()[0]) == 'fixture-secret-local'
assert conn.execute('SELECT count(*) FROM dashboard_sessions').fetchone()[0] == 0
assert conn.execute("SELECT value FROM dashboard_settings WHERE key='fixture'").fetchone()[0] == 'preserved'
conn.close()
store = ReconJobStore(RECON_DB_PATH)
store.recover()
assert store.get(('reto','demo'))['status'] == 'interrupted'
assert Path('/workspace/retos/demo/evidence.md').read_text() == 'fixture evidence'
assert VAULT_KEY_PATH.stat().st_mode & 0o777 == 0o600
assert VAULT_KEY_PATH.stat().st_uid == 1000
print('dashboard_backup_integration=ok vault/settings/workspace/jobs/sessions/permisos')
'''
            print(command('docker', 'run', '--rm', '--network=none', '--read-only', '--cap-drop=ALL',
                          '--user=1000:1000', '--volumes-from', containers[1], *env,
                          '--entrypoint=/opt/nxc/bin/python3', image, '-c', verify))
            result = subprocess.run(['python3', tool, 'restore', '--container', containers[1], '--archive', str(archive)], capture_output=True)
            if result.returncode == 0:
                raise AssertionError('Se aceptó restaurar sobre datos existentes.')
        finally:
            for cid in containers:
                subprocess.run(['docker', 'rm', '-f', cid], check=True, stdout=subprocess.DEVNULL)
            for volume in volumes:
                subprocess.run(['docker', 'volume', 'rm', volume], check=True, stdout=subprocess.DEVNULL)


if __name__ == '__main__':
    main()
