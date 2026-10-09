#!/usr/bin/env python3
import argparse
import hashlib
import io
import json
import os
import pathlib
import platform
import re
import tarfile
import tempfile
import time
import urllib.request
from urllib.parse import urlparse

LIMIT = 128 * 1024 * 1024
LOCK = pathlib.Path(__file__).resolve().parents[1] / 'supply-chain/ci-linters.lock.json'


def verified(data, digest):
    return len(data) <= LIMIT and hashlib.sha256(data).hexdigest() == digest


def download(url):
    for attempt in range(3):
        try:
            request = urllib.request.Request(url, headers={'User-Agent':'seclab-ci-linters'})
            with urllib.request.urlopen(request, timeout=30) as response:
                if urlparse(response.url).scheme != 'https':
                    raise ValueError('Descarga sin HTTPS.')
                data = response.read(LIMIT+1)
                if len(data) > LIMIT:
                    raise ValueError('Descarga demasiado grande.')
                return data
        except OSError:
            if attempt == 2:
                raise
            time.sleep(attempt+1)


def atomic_write(path, data, mode):
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as temporary:
        staging = pathlib.Path(temporary.name)
        try:
            temporary.write(data)
            temporary.flush()
            os.fchmod(temporary.fileno(), mode)
            os.replace(staging, path)
        finally:
            staging.unlink(missing_ok=True)


def install(lock, arch, cache, destination, offline=False):
    if lock.get('schema_version') != 1 or set(lock['tools']) != {'actionlint','hadolint','shellcheck'}:
        raise ValueError('Lock de linters inválido.')
    for directory in (cache, destination):
        if directory.is_symlink():
            raise ValueError('Directorio enlazado.')
        directory.mkdir(parents=True, exist_ok=True)
    for name, tool in lock['tools'].items():
        asset = tool['assets'][arch]
        digest = asset['sha256']
        url = urlparse(asset['url'])
        if not re.fullmatch(r'[a-f0-9]{64}', digest) or url.scheme != 'https' or url.netloc != 'github.com':
            raise ValueError('Pin de linter inválido.')
        archive = cache / digest
        if archive.is_symlink():
            raise ValueError('Cache enlazada.')
        data = archive.read_bytes() if archive.exists() and archive.stat().st_size <= LIMIT else b''
        if not verified(data, digest):
            if offline:
                raise ValueError('Cache ausente o checksum inválido.')
            data = download(asset['url'])
            if not verified(data, digest):
                raise ValueError('Checksum de descarga inválido.')
            atomic_write(archive, data, 0o600)
        if asset.get('member'):
            with tarfile.open(fileobj=io.BytesIO(data), mode='r:*') as package:
                member = package.getmember(asset['member'])
                if not member.isfile() or member.size > LIMIT:
                    raise ValueError('Binario de archivo inválido.')
                binary = package.extractfile(member).read(LIMIT+1)
        else:
            binary = data
        if not binary or len(binary) > LIMIT:
            raise ValueError('Binario inválido.')
        atomic_write(destination/name, binary, 0o555)
        print(f'ci_linter={name} version={tool["version"]} arch={arch} sha256={digest}')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--cache', required=True, type=pathlib.Path)
    parser.add_argument('--destination', required=True, type=pathlib.Path)
    parser.add_argument('--arch', choices=('amd64','arm64'), default=None)
    parser.add_argument('--offline', action='store_true')
    args = parser.parse_args()
    arch = args.arch or {'x86_64':'amd64','aarch64':'arm64','arm64':'arm64'}.get(platform.machine())
    if arch is None or (args.arch is None and platform.system() != 'Linux'):
        parser.error('Solo se admiten Linux amd64/arm64; --arch permite preparar un cache para esos runners.')
    install(json.loads(LOCK.read_text()), arch, args.cache, args.destination, args.offline)


if __name__ == '__main__':
    main()
