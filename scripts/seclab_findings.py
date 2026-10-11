import errno
import os
import re
import stat
import uuid

from seclab_artifacts import normalize_artifact_refs


FINDING_READ_LIMIT = 32 * 1024 * 1024


def read_finding_source(path):
    """Lee una ficha regular sin seguir enlaces en evidence/ ni en su entrada."""
    flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK
    directory_fd = os.open(path.parent, flags | os.O_DIRECTORY)
    try:
        source_fd = os.open(path.name, flags, dir_fd=directory_fd)
        try:
            source_stat = os.fstat(source_fd)
            if not stat.S_ISREG(source_stat.st_mode):
                raise OSError(errno.EINVAL, "Fuente de ficha no regular.")
            if source_stat.st_size > FINDING_READ_LIMIT:
                raise OSError(errno.EFBIG, "Fuente de ficha demasiado grande.")
            with os.fdopen(source_fd, 'rb', closefd=False) as source:
                content = source.read(FINDING_READ_LIMIT + 1)
            if len(content) > FINDING_READ_LIMIT:
                raise OSError(errno.EFBIG, "Fuente de ficha demasiado grande.")
            return content.decode('utf-8')
        finally:
            os.close(source_fd)
    finally:
        os.close(directory_fd)


def normalize_status(raw_status: str) -> str:
    """Normaliza estados heterogeneos de hallazgos al ciclo Evidence-First."""
    raw = str(raw_status or "").strip().upper()
    status_map = {
        "PROVEN": "PROVEN",
        "CONFIRMADO": "PROVEN",
        "VERIFIED": "PROVEN",
        "CANDIDATE": "CANDIDATE",
        "NULL": "CANDIDATE",
        "~": "CANDIDATE",
        "HIPOTESIS": "CANDIDATE",
        "DISPROVED": "DISPROVED",
        "FALSO_POSITIVO": "DISPROVED",
        "FALSO POSITIVO": "DISPROVED",
        "FALSE_POSITIVE": "DISPROVED",
        "MITIGATED": "MITIGATED",
        "MITIGADO": "MITIGATED",
        "REMEDIATED": "MITIGATED",
        "DRAFT": "DRAFT",
        "BORRADOR": "DRAFT",
        "UNVERIFIED": "DRAFT",
        "BLOCKED": "BLOCKED",
    }
    return status_map.get(raw, raw if raw else "CANDIDATE")


def normalize_verification_rationale(value):
    if value is None:
        return ""
    if not isinstance(value, str) or len(value) > 4000 or "\0" in value:
        raise ValueError("Motivo de verificación inválido: usa texto de hasta 4000 caracteres sin NUL.")
    return value.strip()


def validate_confirmation(metadata):
    if normalize_status(metadata.get("status")) != "PROVEN":
        return
    asset = metadata.get("asset")
    if not isinstance(asset, str) or not asset.strip() or asset.strip().upper() == "N/A":
        raise ValueError("Para confirmar necesitas un activo autorizado.")
    if not normalize_artifact_refs(metadata.get("artifact_refs", [])):
        raise ValueError("Para confirmar necesitas al menos un artefacto vinculado y revisado.")
    if not normalize_verification_rationale(metadata.get("verification_rationale")):
        raise ValueError("Para confirmar explica el motivo de verificación humana.")


def requires_finding_review(raw_status):
    return normalize_status(raw_status) not in {"PROVEN", "DISPROVED", "MITIGATED"}


def finding_status_from_markdown(content: str) -> str:
    match = re.match(r"\A---\r?\n(.*?)\r?\n---(?:\r?\n|$)", content, re.DOTALL)
    if match:
        keys = set()
        for line in match[1].splitlines():
            line = line.strip()
            if not line or line.startswith("#") or ":" not in line:
                continue
            key = line.split(":", 1)[0].strip()
            if key in keys:
                return "CANDIDATE"
            keys.add(key)
        values = [line.split(":", 1)[1].strip() for line in match[1].splitlines()
                  if line.startswith("status:")]
        if len(values) == 1:
            value = values[0]
            if value.startswith(("'", '"')):
                scalar = re.fullmatch(r"([\"'])(.*?)\1(?:\s+#.*)?\s*", value)
                return normalize_status(scalar[2]) if scalar else "CANDIDATE"
            return normalize_status(value.split(" #", 1)[0].strip())
    return "CANDIDATE"


def normalize_finding_id(value):
    if (not isinstance(value, str) or not re.fullmatch(r'[a-f0-9]{32}', value)
            or uuid.UUID(hex=value).version != 4):
        raise ValueError('Identidad de hallazgo inválida: se requiere UUID v4 hexadecimal en minúsculas.')
    return value
