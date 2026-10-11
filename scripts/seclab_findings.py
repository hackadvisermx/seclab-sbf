import errno
import json
import os
import re
import stat
import uuid

from seclab_artifacts import normalize_artifact_refs

try:
    import yaml
except ImportError:  # Los lectores CLI también funcionan sin PyYAML.
    yaml = None


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


if yaml is not None:
    class _FindingLoader(yaml.SafeLoader):
        def construct_mapping(self, node, deep=False):
            if isinstance(node, yaml.MappingNode):
                seen = set()
                for key_node, _ in node.value:
                    if key_node.tag == 'tag:yaml.org,2002:merge':
                        raise ValueError('Metadata con merges YAML requiere revisión manual.')
                    key = self.construct_object(key_node, deep=deep)
                    if not isinstance(key, str) or key in seen:
                        raise ValueError('Metadata con claves inválidas o duplicadas.')
                    seen.add(key)
            return super().construct_mapping(node, deep=deep)


def parse_finding_frontmatter(content: str):
    """Interpreta fichas sin aceptar metadatos que el dashboard rechazaría."""
    match = re.match(r"\A---\r?\n(.*?)\r?\n---(?:\r?\n|$)(.*)\Z", content, re.DOTALL)
    if not match:
        if content.startswith('---'):
            raise ValueError('Frontmatter inválido; revisa la fuente original.')
        return {}, content
    source, body = match.groups()
    if yaml is None:
        # Sin PyYAML solo se admite el subconjunto de escalares simples.
        metadata = {}

        def unique_json_pairs(pairs):
            result = {}
            for key, value in pairs:
                if key in result:
                    raise ValueError('Referencias JSON con claves duplicadas.')
                result[key] = value
            return result

        for line in source.splitlines():
            if not line.strip() or line.lstrip().startswith('#'):
                continue
            plain = re.fullmatch(r'([A-Za-z_][A-Za-z0-9_-]*):\s*(.*)', line)
            if not plain or plain[1] in metadata or plain[2].startswith(('&', '*', '!', '|', '>', '{')):
                raise ValueError('Metadata YAML no interpretable sin PyYAML.')
            value = plain[2]
            if plain[1] == 'artifact_refs' and value.startswith('['):
                try:
                    refs = json.loads(value, object_pairs_hook=unique_json_pairs)
                    if not isinstance(refs, list):
                        raise ValueError('Referencias JSON inválidas.')
                except json.JSONDecodeError as error:
                    raise ValueError('Referencias JSON inválidas.') from error
            elif value.startswith('['):
                raise ValueError('Estructura YAML no interpretable sin PyYAML.')
            elif value.startswith('"'):
                try:
                    parsed, end = json.JSONDecoder().raw_decode(value)
                except json.JSONDecodeError as error:
                    raise ValueError('Escalar YAML inválido.') from error
                if not isinstance(parsed, str) or not re.fullmatch(r'\s*(?:#.*)?', value[end:]):
                    raise ValueError('Escalar YAML no textual.')
                value = parsed
            elif value.startswith("'"):
                scalar = re.fullmatch(r'(["\'])(.*?)\1(?:\s+#.*)?\s*', value)
                if not scalar:
                    raise ValueError('Escalar YAML inválido.')
                value = scalar[2]
            else:
                value = value.split(' #', 1)[0].strip()
            metadata[plain[1]] = value
    else:
        try:
            metadata = yaml.load(source, Loader=_FindingLoader) or {}
        except (yaml.YAMLError, RecursionError) as error:
            raise ValueError('Metadata YAML inválida; revisa la fuente original.') from error
        if not isinstance(metadata, dict):
            raise ValueError('Metadata debe ser un objeto YAML.')
    for key in ('id', 'title', 'severity', 'status', 'asset', 'cwe', 'finding_id'):
        if key in metadata and metadata[key] is not None and not isinstance(metadata[key], str):
            raise ValueError(f'Metadata {key} debe ser texto.')
    return metadata, body


def finding_status_from_markdown(content: str) -> str:
    try:
        metadata, _ = parse_finding_frontmatter(content)
    except ValueError:
        return 'CANDIDATE'
    return normalize_status(metadata.get('status'))


def normalize_finding_id(value):
    if (not isinstance(value, str) or not re.fullmatch(r'[a-f0-9]{32}', value)
            or uuid.UUID(hex=value).version != 4):
        raise ValueError('Identidad de hallazgo inválida: se requiere UUID v4 hexadecimal en minúsculas.')
    return value
