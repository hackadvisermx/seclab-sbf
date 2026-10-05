from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from app.models.schemas import ChatMessage, ChatCompletionRequest, ChatCompletionResponse
from app.services.workspace_sync import workspace_service
from app.services.runner_service import runner_service
from app.services.proxy_service import proxy_service

router = APIRouter(prefix="/copilot", tags=["Copiloto Táctico & Agentes IA"])


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
    context_md = runner_service.get_agent_context(str(target_dir), skill_name=skill_name)
    return {"engagement_id": eng_id, "agent": agent, "context": context_md}


@router.post("/chat", response_model=ChatCompletionResponse)
async def copilot_chat(payload: CopilotChatRequest):
    """Envia una consulta al Copiloto inyectando el contexto vivo del proyecto."""
    target_dir = workspace_service._resolve_dir(payload.engagement_id, payload.type)
    if not target_dir.exists():
        raise HTTPException(status_code=404, detail="Directorio del engagement no encontrado")

    skill_name = payload.agent_id if payload.agent_id != "general" else None
    context_md = runner_service.get_agent_context(str(target_dir), skill_name=skill_name)

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
        temperature=0.2,
        max_tokens=2500,
    )

    try:
        return await proxy_service.chat_completion(proxy_req, profile=payload.profile)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Error en comunicación con el modelo: {str(e)}")
