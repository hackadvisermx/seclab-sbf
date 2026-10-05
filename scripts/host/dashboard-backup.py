#!/usr/bin/env python3
"""Respaldo offline del workspace y dashboard; helper aislado en Docker."""
import argparse
from contextlib import closing
import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import sqlite3
import stat
import subprocess
import sys
import tarfile
import tempfile
import uuid

STATE_FILES = {'.vault.key', 'vault.db', 'recon-jobs.db'}


def regular_tree(root):
    if root.is_symlink() or not root.is_dir():
        raise ValueError('Se requiere un directorio real.')
    for path in root.rglob('*'):
        mode = path.lstat().st_mode
        if not (stat.S_ISDIR(mode) or stat.S_ISREG(mode)):
            raise ValueError('El respaldo no admite enlaces ni archivos especiales.')


def check_state(root, databases=True):
    regular_tree(root)
    key = root / '.vault.key'
    if not STATE_FILES.issubset({p.name for p in root.iterdir()}):
        raise ValueError('Faltan bases o clave de bóveda; no se genera una copia parcial.')
    if len(key.read_bytes()) != 32 or key.stat().st_mode & 0o777 != 0o600:
        raise ValueError('Clave de bóveda inválida o permisos distintos de 600.')
    allowed = STATE_FILES | {'recon-jobs.db.lock'} | {name + suffix for name in ('vault.db', 'recon-jobs.db') for suffix in ('-wal', '-shm', '-journal')}
    if any(p.name not in allowed or not p.is_file() for p in root.iterdir()):
        raise ValueError('Archivo de estado desconocido; revisar alcance antes de respaldar.')
    if not databases:
        return
    for name in ('vault.db', 'recon-jobs.db'):
        with closing(sqlite3.connect((root / name).as_uri() + '?mode=ro', uri=True)) as conn:
            if conn.execute('PRAGMA integrity_check').fetchall() != [('ok',)]:
                raise ValueError('Base SQLite corrupta.')


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def backup(workspace, state, destination):
    regular_tree(workspace)
    check_state(state, databases=False)
    destination.mkdir(mode=0o700, parents=True, exist_ok=True)
    if destination.is_symlink() or destination.stat().st_mode & 0o077:
        raise ValueError('El destino del respaldo debe ser privado (700).')
    if destination.resolve().is_relative_to(workspace.resolve()) or destination.resolve().is_relative_to(state.resolve()):
        raise ValueError('El respaldo debe quedar fuera de sus fuentes.')
    with tempfile.TemporaryDirectory(dir=destination) as temporary:
        stage = Path(temporary)
        shutil.copytree(workspace, stage / 'workspace')
        (stage / 'dashboard').mkdir(mode=0o700)
        shutil.copyfile(state / '.vault.key', stage / 'dashboard/.vault.key')
        (stage / 'dashboard/.vault.key').chmod(0o600)
        for name in ('vault.db', 'recon-jobs.db'):
            source_copy = stage / ('source-' + name)
            shutil.copyfile(state / name, source_copy)
            for suffix in ('-wal', '-shm', '-journal'):
                if (state / (name + suffix)).exists():
                    shutil.copyfile(state / (name + suffix), Path(str(source_copy) + suffix))
            with closing(sqlite3.connect(source_copy)) as source:
                if source.execute('PRAGMA integrity_check').fetchall() != [('ok',)]:
                    raise ValueError('Base SQLite corrupta.')
                with closing(sqlite3.connect(stage / 'dashboard' / name)) as target:
                    source.backup(target)
                    target.execute("PRAGMA journal_mode=DELETE")
            (stage / 'dashboard' / name).chmod(0o600)
        check_state(stage / 'dashboard')
        manifest = {'format': 1, 'created_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    'files': {p.relative_to(stage).as_posix(): digest(p)
                              for root in ('workspace', 'dashboard') for p in (stage / root).rglob('*') if p.is_file()}}
        (stage / 'manifest.json').write_text(json.dumps(manifest, sort_keys=True))
        name = 'dashboard-' + datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ-') + uuid.uuid4().hex[:8] + '.tar.gz'
        archive = stage / name
        with tarfile.open(archive, 'w:gz') as tar:
            for item in ('workspace', 'dashboard', 'manifest.json'):
                tar.add(stage / item, arcname=item)
        archive.chmod(0o600)
        checksum = stage / (name + '.sha256')
        checksum.write_text(digest(archive) + '  ' + name + '\n')
        checksum.chmod(0o600)
        os.rename(checksum, destination / checksum.name)
        os.rename(archive, destination / name)
        return destination / name


def restore(workspace, state, archive):
    for target in (workspace, state):
        if target.is_symlink() or (target.exists() and (not target.is_dir() or any(target.iterdir()))):
            raise ValueError('Restauración requiere workspace y dashboard vacíos; no hay FORCE.')
    if archive.is_symlink() or not archive.is_file() or archive.stat().st_mode & 0o077:
        raise ValueError('El archivo de respaldo debe ser regular y privado (600).')
    checksum = Path(str(archive) + '.sha256')
    if checksum.is_symlink() or not checksum.is_file():
        raise ValueError('Se requiere checksum SHA-256.')
    if checksum.read_text().strip() != digest(archive) + '  ' + archive.name:
        raise ValueError('Checksum SHA-256 incorrecto.')
    with tempfile.TemporaryDirectory(dir=archive.parent) as temporary:
        stage = Path(temporary)
        with tarfile.open(archive, 'r:gz') as tar:
            seen = set()
            for member in tar:
                path = PurePosixPath(member.name)
                if (path.is_absolute() or '..' in path.parts or str(path) != member.name
                        or member.name in seen or not (member.isfile() or member.isdir())
                        or not path.parts or path.parts[0] not in {'workspace', 'dashboard', 'manifest.json'}
                        or (path.parts[0] == 'manifest.json' and (len(path.parts) != 1 or not member.isfile()))):
                    raise ValueError('Entrada de archivo insegura o duplicada.')
                seen.add(member.name)
                target = stage / member.name
                if member.isdir():
                    target.mkdir(mode=0o700, parents=True, exist_ok=True)
                else:
                    target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
                    with tar.extractfile(member) as source, target.open('xb') as output:
                        shutil.copyfileobj(source, output)
                    target.chmod(0o700 if path.parts[0] == 'workspace' and member.mode & 0o111 else 0o600)
        manifest = json.loads((stage / 'manifest.json').read_text())
        actual = {p.relative_to(stage).as_posix(): digest(p)
                  for root in ('workspace', 'dashboard') for p in (stage / root).rglob('*') if p.is_file()}
        if manifest.get('format') != 1 or manifest.get('files') != actual:
            raise ValueError('El manifiesto de integridad no coincide.')
        if {p.name for p in (stage / 'dashboard').iterdir()} != STATE_FILES:
            raise ValueError('Estado dashboard inesperado.')
        regular_tree(stage / 'workspace')
        check_state(stage / 'dashboard')
        with closing(sqlite3.connect(stage / 'dashboard/vault.db')) as conn, conn:
            conn.execute('DELETE FROM dashboard_sessions')
        moved = []
        try:
            for name, target in (('workspace', workspace), ('dashboard', state)):
                target.mkdir(mode=0o700, parents=True, exist_ok=True)
                target.chmod(0o700)
                for child in (stage / name).iterdir():
                    result = target / child.name
                    moved.append(result)
                    shutil.move(str(child), result)
            if os.geteuid() == 0:
                for target in (workspace, state):
                    for item in [target, *target.rglob('*')]:
                        os.chown(item, 1000, 1000)
        except BaseException:
            for path in reversed(moved):
                if not path.exists():
                    continue
                if path.is_dir():
                    shutil.rmtree(path)
                else:
                    path.unlink()
            raise


def docker_json(*args):
    return json.loads(subprocess.check_output(['docker', *args], text=True))


def offline_mounts(container):
    info = docker_json('inspect', container)[0]
    if info['State']['Running'] or info['State'].get('Paused') or info['State'].get('Restarting'):
        raise ValueError('Detenga el laboratorio con docker compose stop lab antes de continuar.')
    mounts = {m['Destination']: m for m in info['Mounts']}
    ws, state = mounts['/workspace'], mounts['/var/lib/seclab']
    if ws['Type'] != 'bind' or state['Type'] != 'volume':
        raise ValueError('Se requiere workspace bind y lab-state volume.')
    active = subprocess.check_output(['docker', 'ps', '-q'], text=True).split()
    if active:
        for other in docker_json('inspect', *active):
            for m in other['Mounts']:
                if ((m['Type'] == 'volume' and m.get('Name') == state['Name'])
                        or (m['Type'] == 'bind' and (Path(m['Source']).is_relative_to(ws['Source'])
                            or Path(ws['Source']).is_relative_to(m['Source'])))):
                    raise ValueError('Otro contenedor activo usa el workspace o lab-state.')
    return info['Image'], ws['Source'], state['Name']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('backup', 'restore'))
    parser.add_argument('--container')
    parser.add_argument('--destination', type=Path, default=Path('./backups/dashboard'))
    parser.add_argument('--archive', type=Path)
    parser.add_argument('--output-owner', default=None, help=argparse.SUPPRESS)
    parser.add_argument('--helper', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args()
    os.umask(0o077)
    if args.helper:
        state = Path('/state/dashboard')
        if state.is_symlink():
            raise ValueError('Estado simbólico rechazado.')
        if args.action == 'backup':
            fd = os.open(state / 'recon-jobs.db.lock', os.O_RDONLY | os.O_NOFOLLOW)
            with os.fdopen(fd, 'rb') as lock:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                archive = backup(Path('/workspace'), state, args.destination)
                if args.output_owner:
                    uid, gid = map(int, args.output_owner.split(':'))
                    for path in (archive, Path(str(archive) + '.sha256')):
                        os.chown(path, uid, gid)
                print('dashboard_backup=ok archivo=' + archive.name)
        else:
            restore(Path('/workspace'), state, args.archive)
            print('dashboard_restore=ok sesiones revocadas; iniciar laboratorio manualmente')
        return
    if not args.container or (args.action == 'restore' and args.archive is None):
        parser.error('Se requiere --container y, para restore, --archive.')
    image, workspace, volume = offline_mounts(args.container)
    directory = args.destination if args.action == 'backup' else args.archive.absolute().parent
    if directory.is_symlink():
        raise ValueError('Destino simbólico rechazado.')
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    directory = directory.resolve()
    if directory.stat().st_mode & 0o077 or directory.is_relative_to(Path(workspace)):
        raise ValueError('Directorio privado 700 requerido fuera del workspace.')
    with (directory / '.dashboard-backup.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        helper_name = 'seclab-state-copy-' + hashlib.sha256(volume.encode()).hexdigest()[:16]
        command = ['docker', 'run', '--rm', '--name', helper_name, '--pull=never', '--network=none', '--read-only',
                   '--cap-drop=ALL', '--cap-add=DAC_OVERRIDE', '--cap-add=CHOWN', '--cap-add=FOWNER',
                   '--security-opt=no-new-privileges', '--user=0:0', '--tmpfs=/tmp:rw,noexec,nosuid,size=16m',
                   '--mount', f'type=bind,src={workspace},dst=/workspace' + (',readonly' if args.action == 'backup' else ''),
                   '--mount', f'type=volume,src={volume},dst=/state' + (',readonly' if args.action == 'backup' else ''),
                   '--mount', f'type=bind,src={directory},dst=/backup',
                   '--mount', f'type=bind,src={Path(__file__).resolve()},dst=/tool.py,readonly',
                   '--entrypoint=python3', image, '/tool.py', args.action, '--helper', '--destination=/backup', '--output-owner', f'{os.getuid()}:{os.getgid()}']
        if args.action == 'restore':
            command += ['--archive', '/backup/' + args.archive.name]
        subprocess.run(command, check=True)


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, KeyError, sqlite3.Error, tarfile.TarError, subprocess.CalledProcessError) as error:
        print('dashboard_backup: ' + str(error), file=sys.stderr)
        sys.exit(1)
