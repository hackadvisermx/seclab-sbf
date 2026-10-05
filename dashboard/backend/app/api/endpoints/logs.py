import asyncio
import os
import pathlib
from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from app.services.workspace_sync import workspace_service
from app.api.endpoints.auth import session_token
from app.core.security import verify_session_token
from app.core.workspace_paths import UnsafeWorkspacePath

router = APIRouter(prefix="/logs", tags=["Logs de Auditoría"])


@router.get("/{eng_id}")
def get_log_snapshot(eng_id: str, lines: int = Query(500), type: str = Query("engagement")):
    """Devuelve las últimas N líneas del archivo terminal.log de un engagement."""
    content = workspace_service.get_terminal_log(eng_id, lines=lines, eng_type=type)
    return {"engagement_id": eng_id, "lines": lines, "content": content}


@router.websocket("/{eng_id}/ws")
async def websocket_terminal_log(websocket: WebSocket, eng_id: str, type: str = "engagement"):
    """Transmite en tiempo real las nuevas líneas escritas en terminal.log."""
    try:
        log_file = workspace_service._resolve_dir(eng_id, type) / "terminal.log"
    except UnsafeWorkspacePath:
        await websocket.close(code=1008)
        return
    await websocket.accept()
    token = session_token(websocket)

    async def session_valid():
        if verify_session_token(token):
            return True
        await websocket.close(code=1008)
        return False

    try:
        if not log_file.exists():
            await websocket.send_text("[SecLab Dashboard] Esperando inicio de auditoría y creación de terminal.log...\n")

        # Esperar a que el archivo exista si aún no fue creado
        while not log_file.exists():
            if not await session_valid():
                return
            await asyncio.sleep(1)

        # Enviar bloque inicial
        initial_content = workspace_service.get_terminal_log(eng_id, lines=100, eng_type=type)
        await websocket.send_text(initial_content)

        # Tailing en bucle asíncrono
        with open(log_file, "r", errors="ignore") as f:
            f.seek(0, os.SEEK_END)
            while True:
                if not await session_valid():
                    return
                line = f.readline()
                if line:
                    await websocket.send_text(line)
                else:
                    await asyncio.sleep(0.5)

    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await websocket.send_text(f"\n[Error en streaming de log: {str(e)}]\n")
        except Exception:
            pass
