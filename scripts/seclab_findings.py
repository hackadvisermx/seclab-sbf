from seclab_artifacts import normalize_artifact_refs


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
