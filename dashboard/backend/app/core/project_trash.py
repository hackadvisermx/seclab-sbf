import ctypes
import datetime
import errno
import os
import pathlib
import re
import stat
import threading
import uuid
from app.core.workspace_paths import project_directory, validate_project_identity, UnsafeWorkspacePath


def move_without_replacing(source, target):
    libc = ctypes.CDLL(None, use_errno=True)
    rename = getattr(libc, 'renameat2', None)
    if rename is None:
        raise OSError(errno.ENOTSUP, 'La papelera requiere renameat2 en el runtime Linux del laboratorio.')
    rename.argtypes = (ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint)
    rename.restype = ctypes.c_int
    if rename(-100, os.fsencode(source), -100, os.fsencode(target), 1) != 0:
        code = ctypes.get_errno()
        if code == errno.EEXIST:
            raise RuntimeError('Ya existe el destino. No se sobrescribió ningún proyecto; la copia sigue en su origen.')
        raise OSError(code, os.strerror(code))


class ProjectTrash:
    def __init__(self, workspace):
        self.workspace = pathlib.Path(workspace)
        self.lock = threading.RLock()

    def _root(self):
        root = self.workspace / '.seclab-trash'
        self._safe_directory(root)
        if root.resolve().parent != self.workspace.resolve():
            raise UnsafeWorkspacePath('La papelera debe estar dentro del workspace.')
        return root

    @staticmethod
    def _safe_directory(path):
        if path.is_symlink() or (path.exists() and not path.is_dir()):
            raise UnsafeWorkspacePath('La papelera no admite enlaces ni rutas que no sean directorios.')

    @staticmethod
    def _safe_tree(path):
        ProjectTrash._safe_directory(path)
        def fail(error):
            raise error
        for directory, folders, files in os.walk(path, followlinks=False, onerror=fail):
            for name in folders + files:
                mode = (pathlib.Path(directory) / name).lstat().st_mode
                if not (stat.S_ISREG(mode) or stat.S_ISDIR(mode)):
                    raise UnsafeWorkspacePath('El proyecto no admite enlaces ni archivos especiales.')

    @staticmethod
    def _deleted_at(entry_id):
        if not re.fullmatch(r'[0-9]{8}T[0-9]{12}Z-[a-f0-9]{32}', entry_id):
            raise UnsafeWorkspacePath('Identificador de papelera no válido.')
        try:
            return datetime.datetime.strptime(entry_id.split('-')[0], '%Y%m%dT%H%M%S%fZ').replace(
                tzinfo=datetime.timezone.utc).isoformat()
        except ValueError as error:
            raise UnsafeWorkspacePath('Fecha de papelera no válida.') from error

    def _parent(self, project_id, project_type):
        validate_project_identity(project_id, project_type)
        root = self._root()
        category = root / ('retos' if project_type == 'reto' else 'engagements')
        parent = category / project_id
        for path in (category, parent):
            self._safe_directory(path)
        return parent

    def _entry(self, entry_id, project_id, project_type):
        deleted_at = self._deleted_at(entry_id)
        return {'entry_id': entry_id, 'project_id': project_id, 'type': project_type,
                'deleted_at': deleted_at}

    def move(self, project_id, project_type='engagement'):
        with self.lock:
            target = project_directory(self.workspace, project_id, project_type)
            if not target.is_dir():
                raise FileNotFoundError('Proyecto no encontrado.')
            self._safe_tree(target)
            parent = self._parent(project_id, project_type)
            entry_id = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ-') + uuid.uuid4().hex
            destination = parent / entry_id
            for path in (self._root(), parent.parent, parent):
                path.mkdir(mode=0o700, exist_ok=True)
                path.chmod(0o700)
            if destination.exists() or destination.is_symlink():
                raise RuntimeError('Ya existe esta entrada en la papelera.')
            move_without_replacing(target, destination)
            return self._entry(entry_id, project_id, project_type)

    def list_entries(self):
        with self.lock:
            root = self._root()
            entries = []
            for project_type, category_name in (('engagement', 'engagements'), ('reto', 'retos')):
                category = root / category_name
                self._safe_directory(category)
                if not category.exists():
                    continue
                for parent in category.iterdir():
                    try:
                        self._parent(parent.name, project_type)
                        if not parent.is_dir():
                            continue
                        for path in parent.iterdir():
                            try:
                                entry = self._entry(path.name, parent.name, project_type)
                                self._safe_tree(path)
                                if path.is_dir():
                                    entries.append(entry)
                            except (UnsafeWorkspacePath, OSError):
                                continue
                    except (UnsafeWorkspacePath, OSError):
                        continue
            return sorted(entries, key=lambda entry: (entry['deleted_at'], entry['entry_id']), reverse=True)

    def restore(self, entry_id, project_id, project_type='engagement'):
        with self.lock:
            entry = self._entry(entry_id, project_id, project_type)
            source = self._parent(project_id, project_type) / entry_id
            self._safe_tree(source)
            if not source.is_dir():
                raise FileNotFoundError('Entrada de papelera no encontrada.')
            target = project_directory(self.workspace, project_id, project_type)
            if target.exists() or target.is_symlink():
                raise RuntimeError('Ya existe un proyecto con ese nombre y tipo. No se sobrescribió; la copia sigue en la papelera.')
            target.parent.mkdir(exist_ok=True)
            move_without_replacing(source, target)
            return entry
