import datetime
import hashlib
import os
import pathlib
import stat

PREVIEW_LIMIT = 2 * 1024 * 1024
HASH_LIMIT = 32 * 1024 * 1024


class ArtifactChangedError(ValueError):
    pass


def read_artifact_snapshot(root: pathlib.Path, rel_path: str):
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
                if before.st_size <= PREVIEW_LIMIT:
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
        return {
            'name': parts[-1], 'rel_path': rel_path, 'size': before.st_size, 'content': content,
            'modified': datetime.datetime.fromtimestamp(before.st_mtime, datetime.timezone.utc).isoformat(),
            'sha256': digest, 'fingerprint_status': fingerprint_status, 'preview_status': preview_status,
        }
    except FileNotFoundError:
        raise FileNotFoundError('Archivo de artefacto no encontrado o acceso denegado') from None
    except OSError:
        raise FileNotFoundError('Archivo de artefacto no encontrado o acceso denegado') from None
    finally:
        for fd in reversed(descriptors):
            os.close(fd)
