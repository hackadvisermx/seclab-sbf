from typing import Any, Dict, List
from fastapi import APIRouter, HTTPException, Query
from app.models.schemas import FindingDetail, FindingCreate
from app.services.workspace_sync import workspace_service, FindingUpdateError

router = APIRouter(prefix="/findings", tags=["Hallazgos & Evidencias"])

@router.post("/cvss/calculate")
@router.post("/cvss-calc")
def calculate_cvss_score(payload: Dict[str, str]):
    """Calcula el score base CVSS 3.1 a partir de las métricas seleccionadas."""
    av_weights = {"N": 0.85, "A": 0.62, "L": 0.55, "P": 0.2}
    ac_weights = {"L": 0.77, "H": 0.44}
    pr_weights_u = {"N": 0.85, "L": 0.62, "H": 0.27}
    pr_weights_c = {"N": 0.85, "L": 0.68, "H": 0.5}
    ui_weights = {"N": 0.85, "R": 0.62}
    cia_weights = {"N": 0.0, "L": 0.22, "H": 0.56}

    av = payload.get("AV", "N")
    ac = payload.get("AC", "L")
    pr = payload.get("PR", "N")
    ui = payload.get("UI", "N")
    s = payload.get("S", "U")
    c = payload.get("C", "N")
    i = payload.get("I", "L")
    a = payload.get("A", "N")

    scope_changed = (s == "C")
    pr_weight = pr_weights_c.get(pr, 0.85) if scope_changed else pr_weights_u.get(pr, 0.85)

    iss = 1 - ((1 - cia_weights.get(c, 0.0)) * (1 - cia_weights.get(i, 0.0)) * (1 - cia_weights.get(a, 0.0)))

    impact = (7.52 * (iss - 0.029) - 3.25 * ((iss - 0.02) ** 15)) if scope_changed else 6.42 * iss
    if impact <= 0:
        base_score = 0.0
    else:
        if not scope_changed:
            base_score = min(impact + 8.22 * av_weights.get(av, 0.85) * ac_weights.get(ac, 0.77) * pr_weight * ui_weights.get(ui, 0.85), 10.0)
        else:
            base_score = min(1.08 * (impact + 8.22 * av_weights.get(av, 0.85) * ac_weights.get(ac, 0.77) * pr_weight * ui_weights.get(ui, 0.85)), 10.0)

    import math
    scaled_score = round(base_score * 100000)
    rounded_score = scaled_score / 100000 if scaled_score % 10000 == 0 else (math.floor(scaled_score / 10000) + 1) / 10

    if rounded_score >= 9.0:
        sev = "CRITICAL"
    elif rounded_score >= 7.0:
        sev = "HIGH"
    elif rounded_score >= 4.0:
        sev = "MEDIUM"
    elif rounded_score > 0.0:
        sev = "LOW"
    else:
        sev = "INFO"

    vector = f"CVSS:3.1/AV:{av}/AC:{ac}/PR:{pr}/UI:{ui}/S:{s}/C:{c}/I:{i}/A:{a}"
    return {"score": rounded_score, "severity": sev, "vector": vector}


@router.get("/{eng_id}", response_model=List[FindingDetail])
def get_findings_list(eng_id: str, type: str = Query("engagement")):
    """Lista todas las fichas de hallazgos registradas en evidence/*.md."""
    return workspace_service.list_findings(eng_id, type)


@router.get("/{eng_id}/{slug}", response_model=FindingDetail)
def get_single_finding(eng_id: str, slug: str, type: str = Query("engagement")):
    """Obtiene el detalle completo de un hallazgo con frontmatter y cuerpo Markdown."""
    finding = workspace_service.get_finding(eng_id, slug, type)
    if not finding:
        raise HTTPException(status_code=404, detail="Hallazgo no encontrado")
    return finding


@router.post("/{eng_id}", response_model=FindingDetail)
def create_or_update_finding(eng_id: str, payload: FindingCreate, type: str = Query("engagement")):
    """Crea o actualiza una ficha en evidence/<slug>.md bajo el estándar Evidence-First."""
    try:
        return workspace_service.save_finding(eng_id, payload, type)
    except FindingUpdateError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@router.delete("/{eng_id}/{slug}")
def delete_finding(eng_id: str, slug: str, type: str = Query("engagement"), expected_source_sha256: str | None = Query(None)):
    """Elimina una ficha de hallazgo."""
    try:
        success = workspace_service.delete_finding(eng_id, slug, type, expected_source_sha256)
    except FindingUpdateError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    if not success:
        raise HTTPException(status_code=404, detail="Hallazgo no encontrado")
    return {"status": "ok", "message": f"Hallazgo {slug} eliminado correctamente"}
