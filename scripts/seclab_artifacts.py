import datetime
import hashlib
import json
import os
import pathlib
import stat
import re

PREVIEW_LIMIT = 2 * 1024 * 1024
HASH_LIMIT = 32 * 1024 * 1024
RECON_STAGE_ARTIFACTS = {
    'subdomains': ('subdomains.txt', 'subdomains_new.txt', 'out_of_scope_discarded.txt'),
    'probe': ('live_hosts.txt', 'live_hosts_new.txt', 'probe_observations.jsonl',
              'probe_discarded.txt', 'next_commands.txt'),
    'urls': ('urls_all.txt', 'js_files.txt'),
    'patterns': tuple('patterns/' + name + '.txt' for name in ('xss', 'sqli', 'ssrf', 'redirect', 'idor', 'rce', 'lfi')),
}


class ArtifactChangedError(ValueError):
    pass


def read_artifact_snapshot(root: pathlib.Path, rel_path: str, include_bytes=False):
    parts = rel_path.split('/')
    if not rel_path or any(part in ('', '.', '..') for part in parts):
        raise FileNotFoundError('Archivo de artefacto no encontrado o acceso denegado')
    descriptors = []
    try:
        descriptors.append(os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW))
        for part in parts[:-1]:
            descriptors.append(os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=descriptors[-1]))
        parent = descriptors[-1]
        descriptors.append(os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent))
        fd = descriptors[-1]
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode):
            raise FileNotFoundError('El artefacto debe ser un archivo regular')
        content = '[Archivo demasiado grande para previsualizar]'
        preview_status = 'too_large'
        digest = None
        fingerprint_status = 'too_large'
        if before.st_size <= HASH_LIMIT:
            hasher = hashlib.sha256()
            chunks = []
            total = 0
            while True:
                chunk = os.read(fd, 1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > HASH_LIMIT:
                    raise ArtifactChangedError('El artefacto cambió durante la lectura; vuelve a seleccionarlo.')
                hasher.update(chunk)
                if include_bytes or before.st_size <= PREVIEW_LIMIT:
                    chunks.append(chunk)
            digest = hasher.hexdigest()
            fingerprint_status = 'available'
            if before.st_size <= PREVIEW_LIMIT:
                raw = b''.join(chunks)
                if b'\0' in raw:
                    content = '[Archivo binario: previsualización textual no disponible]'
                    preview_status = 'binary'
                else:
                    try:
                        content = raw.decode('utf-8')
                        preview_status = 'complete'
                    except UnicodeDecodeError:
                        content = raw.decode('utf-8', errors='replace')
                        preview_status = 'decoded_with_replacement'
        after = os.fstat(fd)
        current = os.stat(parts[-1], dir_fd=parent, follow_symlinks=False)
        signature = lambda info: (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)
        if signature(before) != signature(after) or signature(after) != signature(current):
            raise ArtifactChangedError('El artefacto cambió durante la lectura; vuelve a seleccionarlo.')
        result = {
            'name': parts[-1], 'rel_path': rel_path, 'size': before.st_size, 'content': content,
            'modified': datetime.datetime.fromtimestamp(before.st_mtime, datetime.timezone.utc).isoformat(),
            'sha256': digest, 'fingerprint_status': fingerprint_status, 'preview_status': preview_status,
        }
        if include_bytes and digest is not None:
            result['_bytes'] = b''.join(chunks)
        return result
    except FileNotFoundError:
        raise FileNotFoundError('Archivo de artefacto no encontrado o acceso denegado') from None
    except OSError:
        raise FileNotFoundError('Archivo de artefacto no encontrado o acceso denegado') from None
    finally:
        for fd in reversed(descriptors):
            os.close(fd)


def normalize_artifact_refs(value):
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except ValueError:
            raise ValueError('Referencias de artefactos inválidas: se requiere una lista JSON.') from None
    if not isinstance(value, list) or len(value) > 10:
        raise ValueError('Referencias de artefactos inválidas: máximo 10 vínculos.')
    result = []
    seen = set()
    for item in value:
        if not isinstance(item, dict) or set(item) != {'path', 'sha256'}:
            raise ValueError('Cada referencia necesita solo path y sha256.')
        path, digest = item['path'], item['sha256']
        if not isinstance(path, str) or not re.fullmatch(r'(recon|fuzzing|screenshots)/[a-zA-Z0-9._/-]{1,230}', path):
            raise ValueError('Referencia no permitida: usa una ruta de recon/, fuzzing/ o screenshots/ con nombre ASCII sin espacios.')
        if any(part in ('', '.', '..') for part in path.split('/')) or path in seen:
            raise ValueError('Referencia duplicada o ruta no canónica.')
        if not isinstance(digest, str) or not re.fullmatch(r'[a-f0-9]{64}', digest):
            raise ValueError('La referencia necesita un SHA-256 válido en minúsculas.')
        seen.add(path)
        result.append({'path': path, 'sha256': digest})
    return result


def validate_artifact_refs(root, value):
    references = normalize_artifact_refs(value)
    total = 0
    for reference in references:
        snapshot = read_artifact_snapshot(root, reference['path'])
        total += snapshot['size']
        if total > HASH_LIMIT:
            raise ValueError('Los artefactos vinculados superan 32 MiB en total.')
        if snapshot['sha256'] != reference['sha256']:
            raise ValueError('La versión de ' + reference['path'] + ' cambió o no tiene huella; revisa y vuelve a vincularla.')
    return references
