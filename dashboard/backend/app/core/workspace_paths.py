import os
import pathlib
import re


class UnsafeWorkspacePath(ValueError):
    pass


def project_directory(workspace_path: pathlib.Path, eng_id: str, eng_type: str = "engagement") -> pathlib.Path:
    if eng_type not in {"engagement", "reto"}:
        raise UnsafeWorkspacePath("Tipo de proyecto no válido.")
    if not re.fullmatch(r"[a-zA-Z0-9-][a-zA-Z0-9._-]{0,127}", eng_id):
        raise UnsafeWorkspacePath("Identificador de proyecto no válido.")
    category = workspace_path / ("retos" if eng_type == "reto" else "engagements")
    target = category / eng_id
    if category.is_symlink() or target.is_symlink():
        raise UnsafeWorkspacePath("El proyecto no puede ser un enlace simbólico.")
    if category.resolve().parent != workspace_path.resolve() or target.resolve().parent != category.resolve():
        raise UnsafeWorkspacePath("El proyecto debe estar dentro del workspace.")
    for directory, folders, files in os.walk(target, followlinks=False):
        if any((pathlib.Path(directory) / name).is_symlink() for name in folders + files):
            raise UnsafeWorkspacePath("El dashboard no admite enlaces simbólicos dentro del proyecto.")
    return target

