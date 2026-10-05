#!/usr/bin/env python3
"""Hash portátil de los insumos locales de las imágenes."""
import argparse
import hashlib
import os
import pathlib
import stat
import sys

BASE_FILES = ('images/base/Dockerfile', 'scripts/entrypoint/base-entrypoint.sh',
              'scripts/health/base-healthcheck.sh')
FULL_DIRS = ('images', 'scripts', 'shell', 'security', 'supply-chain',
             'workspace-seed', 'dashboard/backend', 'dashboard/frontend')
FULL_FILES = ('Makefile', '.dockerignore', '.tmux.conf')
EXCLUDED_DIRS = {'__pycache__', 'node_modules', '.venv', '.git'}
EXCLUDED_ROOTS = ('dashboard/frontend/dist', 'dashboard/backend/data')


def selected_files(root, profile):
    paths = set()
    if profile == 'base':
        paths.update(root / name for name in BASE_FILES)
    else:
        paths.update(root / name for name in FULL_FILES)
        for name in FULL_DIRS:
            directory = root / name
            if not directory.is_dir() or directory.is_symlink():
                raise ValueError(f'Directorio de insumos inválido: {name}')
            def scan_error(error):
                raise error
            for current, directories, files in os.walk(directory, onerror=scan_error, followlinks=False):
                current = pathlib.Path(current)
                directories[:] = [entry for entry in directories if entry not in EXCLUDED_DIRS
                                  and not any((current / entry).is_relative_to(root / excluded) for excluded in EXCLUDED_ROOTS)]
                for entry in directories:
                    if (current / entry).is_symlink():
                        raise ValueError(f'No se admiten directorios simbólicos: {(current / entry).relative_to(root)}')
                for entry in files:
                    path = current / entry
                    if path.name == '.env' or path.name.startswith('.env.') or path.suffix in {'.pyc', '.log', '.pid'}:
                        continue
                    paths.add(path)
    return sorted(paths, key=lambda path: path.relative_to(root).as_posix())


def build_hash(root, profile):
    digest = hashlib.sha256()
    for path in selected_files(root, profile):
        if not path.is_file() or any(parent.is_symlink() for parent in (path, *path.parents) if parent.is_relative_to(root)):
            raise ValueError(f'Falta un insumo regular: {path.relative_to(root)}')
        digest.update(path.relative_to(root).as_posix().encode() + b'\0')
        digest.update(b'x' if path.stat().st_mode & (stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH) else b'-')
        digest.update(hashlib.sha256(path.read_bytes()).digest())
    return digest.hexdigest()[:16]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('profile', choices=('base', 'full'))
    parser.add_argument('--root', type=pathlib.Path, default=pathlib.Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    try:
        print(build_hash(args.root.resolve(), args.profile))
    except (OSError, ValueError) as error:
        print(f'build-inputs: {error}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
