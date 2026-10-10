import json
import pathlib
import subprocess
import sys
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from app.config import SCRIPTS_DIR
from app.models.schemas import ChatMessage, ChatCompletionRequest, ChatCompletionResponse
from app.services.workspace_sync import workspace_service
from app.services.runner_service import runner_service, AgentContextUnavailable
from app.services.proxy_service import proxy_service

router = APIRouter(prefix="/copilot", tags=["Copiloto Táctico & Agentes IA"])


def _scope_validator_script() -> pathlib.Path:
    source = SCRIPTS_DIR / "pt-scope-validator.py"
    return source if source.is_file() else SCRIPTS_DIR / "pt-scope-validator"


def _validate_copilot_scope(content: str, target_dir: pathlib.Path) -> Dict[str, Any]:
    if not content.strip():
        return {'available': True, 'findings': []}
    if not (target_dir / "target.yaml").is_file() and not (target_dir / "scope.txt").is_file():
        return {'available': False, 'reason': 'Falta target.yaml o scope.txt en el proyecto.'}
    script = _scope_validator_script()
    if not script.is_file():
        return {'available': False, 'reason': 'El validador de alcance no está instalado.'}
    try:
        proc = subprocess.run(
            [sys.executable, str(script), "check-text", str(target_dir)],
            input=content,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except subprocess.TimeoutExpired:
        return {'available': False, 'reason': 'La comprobación de alcance agotó su tiempo de espera.'}
    except OSError:
        return {'available': False, 'reason': 'No se pudo iniciar el validador de alcance.'}
    if proc.returncode not in (0, 1, 3) or not proc.stdout.strip():
        return {'available': False, 'reason': 'El validador falló; revisa el alcance y la instalación.'}
    try:
        findings = json.loads(proc.stdout)
    except ValueError:
        return {'available': False, 'reason': 'El validador devolvió una respuesta inválida.'}
    if not isinstance(findings, list) or any(
            not isinstance(finding, dict) or finding.get('verdict') not in ('OUT_OF_SCOPE', 'UNKNOWN')
            or not all(isinstance(finding.get(key), str) and finding[key].strip() for key in ('target', 'reason'))
            for finding in findings):
        return {'available': False, 'reason': 'El validador devolvió una respuesta inválida.'}
    expected_code = 1 if any(finding['verdict'] == 'OUT_OF_SCOPE' for finding in findings) else (3 if findings else 0)
    if proc.returncode != expected_code:
        return {'available': False, 'reason': 'El resultado del validador es inconsistente.'}
    return {'available': True, 'findings': findings}


def _format_scope_warning(findings: List[Dict[str, str]]) -> str:
    out_of_scope = [f for f in findings if f.get("verdict") == "OUT_OF_SCOPE"]
    unknown = [f for f in findings if f.get("verdict") == "UNKNOWN"]
    lines = ["⚠️ **Validación de Alcance (Scope Guard)**"]
    if out_of_scope:
        lines.append("Objetivos **excluidos explícitamente** mencionados en esta respuesta — NO los pruebes:")
        for f in out_of_scope:
            lines.append(f"- `{f['target']}` — {f['reason']}")
    if unknown:
        lines.append("Objetivos **no confirmados** en el alcance declarado — verifica antes de actuar:")
        for f in unknown:
            lines.append(f"- `{f['target']}` — {f['reason']}")
    lines.append("")
    lines.append("---")
    return "\n".join(lines)


AGENT_PERSONAS = [
    {
        "id": "triage-agent",
        "name": "Triaje & Calidad (Evidence-First)",
        "skill": "triage-gatekeeper",
        "description": "Evalúa evidencias, verifica reproducibilidad, vectores CVSS y bloqueos antes de reportar.",
    },
    {
        "id": "recon-agent",
        "name": "Reconocimiento & Perfilado",
        "skill": "recon-profiling",
        "description": "Identifica tecnologías, superficie de ataque y correlaciona endpoints dentro del alcance.",
    },
    {
        "id": "auth-agent",
        "name": "Control de Acceso & Matriz Auth",
        "skill": "auth-matrix-audit",
        "description": "Guía pruebas de BFLA, BOLA/IDOR, control de roles e invariantes de autenticación.",
    },
    {
        "id": "logic-agent",
        "name": "Lógica de Negocio & Estados",
        "skill": "business-logic-audit",
        "description": "Auditoría de flujos de checkout, validación de cupones, secuencias multipartes y TOCTOU.",
    },
    {
        "id": "injection-agent",
        "name": "Inyecciones de Servidor & SSRF",
        "skill": "ssrf-injection-audit",
        "description": "Análisis de parámetros vulnerables a inyecciones ciegas y callbacks fuera de banda.",
    },
    {
        "id": "report-agent",
        "name": "Generación de Informes",
        "skill": "report-generation",
        "description": "Redacción ejecutiva, resumen técnico del impacto de negocio y mitigaciones sugeridas.",
    },
    {
        "id": "general",
        "name": "Copiloto Táctico General",
        "skill": "general",
        "description": "Asistente consultivo general sobre metodologías PTES, OWASP y herramientas del laboratorio.",
    },
]


class CopilotChatRequest(BaseModel):
    engagement_id: str
    type: str = "engagement"
    agent_id: str = "triage-agent"
    profile: Optional[str] = "quick"  # quick, deep, local
    provider: Optional[str] = None
    model: Optional[str] = None
    messages: List[ChatMessage]


@router.get("/agents")
def list_available_agents():
    """Lista los agentes y roles especializados configurados en SecLab."""
    return AGENT_PERSONAS


@router.get("/context/{eng_id}")
def get_engagement_copilot_context(
    eng_id: str,
    agent: Optional[str] = Query("triage-agent"),
    type: str = Query("engagement"),
):
    """Obtiene el contexto agregado en Markdown sintetizado por pt-agent-context.py."""
    target_dir = workspace_service._resolve_dir(eng_id, type)
    if not target_dir.exists():
        raise HTTPException(status_code=404, detail="Directorio del engagement no encontrado")

    skill_name = agent if agent != "general" else None
    try:
        context_md = runner_service.get_agent_context(str(target_dir), skill_name=skill_name)
    except AgentContextUnavailable as error:
        raise HTTPException(status_code=503, detail=str(error)) from None
    return {"engagement_id": eng_id, "agent": agent, "context": context_md}


@router.post("/chat", response_model=ChatCompletionResponse)
async def copilot_chat(payload: CopilotChatRequest):
    """Envia una consulta al Copiloto inyectando el contexto vivo del proyecto."""
    target_dir = workspace_service._resolve_dir(payload.engagement_id, payload.type)
    if not target_dir.exists():
        raise HTTPException(status_code=404, detail="Directorio del engagement no encontrado")

    skill_name = payload.agent_id if payload.agent_id != "general" else None
    try:
        context_md = runner_service.get_agent_context(str(target_dir), skill_name=skill_name)
    except AgentContextUnavailable as error:
        raise HTTPException(status_code=503, detail=str(error)) from None

    # Inyectar el contexto del engagement en el mensaje de sistema inicial
    system_prompt = (
        f"Eres el Asistente Copiloto de Auditoría de SecLab-SBF (Especialidad: {payload.agent_id}).\n"
        f"Tu misión es apoyar al operador auditor analizando el objetivo de forma técnica, defensiva y metódica.\n"
        f"PRINCIPIOS CRÍTICOS:\n"
        f"1. Alcance: Respeta estrictamente los activos in_scope y out_of_scope del proyecto.\n"
        f"2. Evidence-First: Cada afirmación debe basarse en evidencias verificables y pasos de reproducción claros.\n"
        f"3. No inventes vulnerabilidades no sustentadas por datos técnicos.\n\n"
        f"--- CONTEXTO EN VIVO DEL PROYECTO ---\n"
        f"{context_md}\n"
        f"--- FIN DEL CONTEXTO ---\n"
    )

    augmented_messages = [ChatMessage(role="system", content=system_prompt)]
    for m in payload.messages:
        augmented_messages.append(m)

    proxy_req = ChatCompletionRequest(
        messages=augmented_messages,
        provider=payload.provider,
        model=payload.model,
        temperature=0.2,
        max_tokens=2500,
    )

    try:
        profile_arg = None if (payload.provider or payload.model) else payload.profile
        response = await proxy_service.chat_completion(proxy_req, profile=profile_arg)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Error en comunicación con el modelo: {str(e)}")

    validation = _validate_copilot_scope(response.content, target_dir)
    if not validation['available']:
        response.content = (
            '⚠️ Validación de alcance no disponible. ' + validation['reason'] + '\n'
            'Esta respuesta sigue siendo una sugerencia sin comprobación de alcance. '
            'Revisa y corrige el alcance antes de realizar acciones; el Copiloto no autoriza ni ejecuta pruebas.\n\n'
            + response.content
        )
    elif validation['findings']:
        response.content = _format_scope_warning(validation['findings']) + "\n\n" + response.content
    return response
