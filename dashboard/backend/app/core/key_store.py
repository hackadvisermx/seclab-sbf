import os
import pathlib
import stat
import tempfile


def persistent_key(path: pathlib.Path) -> bytes:
    """Carga una clave de 256 bits o publica una nueva sin reemplazar claves existentes."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists() and not path.is_symlink():
        descriptor, temporary = tempfile.mkstemp(prefix='.key-', dir=path.parent)
        try:
            with os.fdopen(descriptor, 'wb') as stream:
                stream.write(os.urandom(32))
                stream.flush()
                os.fsync(stream.fileno())
            try:
                os.link(temporary, path)
            except FileExistsError:
                pass
        finally:
            os.unlink(temporary)
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(descriptor, 'rb') as stream:
        metadata = os.fstat(stream.fileno())
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_mode & 0o077:
            raise RuntimeError('La clave debe ser un archivo regular con permisos 600.')
        key = stream.read(33)
    if len(key) != 32:
        raise RuntimeError('Clave inválida: se conserva el archivo para recuperar los datos.')
    return key
