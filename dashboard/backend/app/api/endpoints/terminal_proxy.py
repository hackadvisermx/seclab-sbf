"""Proxy HTTP + WebSocket hacia ttyd para sesión única (fase 114 / backlog A10).

Antes, la terminal embebida apuntaba directo a http://<host>:7681 (puerto
y origen distintos del dashboard), así que el navegador exigía la
autenticación HTTP Basic propia de ttyd además de la sesión del
dashboard: dos inicios de sesión para la misma persona.

Este módulo expone /api/v1/terminal/* en el MISMO origen que el resto
del dashboard. El router ya exige una sesión válida (ver
app/api/router.py, dependencies=[Depends(auth.require_operator)]) antes
de llegar aquí; una vez dentro, este proxy reenvía la petición a ttyd en
127.0.0.1 inyectando la autenticación HTTP Basic de ttyd del lado del
servidor. El navegador nunca ve ni introduce esa contraseña por separado:
basta la cookie de sesión del dashboard, que ya se envía sola por ser
mismo origen.
"""

import asyncio
import base64

import httpx
import websockets
from fastapi import APIRouter, HTTPException, Response, WebSocket
from starlette.websockets import WebSocketState

from app.api.endpoints.auth import session_token
from app.config import TTYD_PASSWORD, TTYD_PORT, TTYD_USER
from app.core.security import verify_session_token

router = APIRouter(prefix="/terminal", tags=["Terminal Integrada"])

_SESSION_RECHECK_SECONDS = 30


def _ttyd_auth_header() -> dict:
    if not TTYD_PASSWORD:
        raise HTTPException(status_code=503, detail="Terminal no disponible: falta TTYD_PASSWORD.")
    creds = base64.b64encode(f"{TTYD_USER}:{TTYD_PASSWORD}".encode()).decode()
    return {"Authorization": f"Basic {creds}"}


def _upstream_http_base() -> str:
    # Calculado en cada llamada (no precomputado al importar el módulo) para
    # que las pruebas puedan apuntar TTYD_PORT a un ttyd real de prueba con
    # unittest.mock.patch.object sobre este módulo.
    return f"http://127.0.0.1:{TTYD_PORT}"


def _upstream_ws_url() -> str:
    return f"ws://127.0.0.1:{TTYD_PORT}/ws"


def _ttyd_ws_headers() -> dict:
    # scripts/entrypoint/ttyd-as-tester.sh lanza ttyd con -O (check-origin):
    # rechaza cualquier upgrade de WebSocket cuyo header Origin no coincida
    # con el Host que ttyd ve en la petición. Antes de este fix, esta
    # conexión servidor-a-servidor (este proceso hacia 127.0.0.1:TTYD_PORT)
    # no enviaba ningún Origin, así que ttyd la rechazaba SIEMPRE con "refuse
    # to serve WS client from different origin" -- la terminal integrada
    # nunca llegó a conectar desde que existe este proxy (fase 114/A10), solo
    # pasaba en las pruebas porque su ttyd de fixture no usaba -O. El Origin
    # correcto es el propio origen que ttyd ve (127.0.0.1:TTYD_PORT), no el
    # origen del navegador (ese ya lo valida require_operator por separado).
    headers = _ttyd_auth_header()
    headers["Origin"] = _upstream_http_base()
    return headers


@router.api_route("/{sub_path:path}", methods=["GET"])
async def proxy_http(sub_path: str = "") -> Response:
    """Reenvía GET / y GET /token (los únicos recursos HTTP que sirve ttyd)."""
    headers = _ttyd_auth_header()
    url = f"{_upstream_http_base()}/{sub_path}"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            upstream = await client.get(url, headers=headers)
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"No se pudo conectar con la terminal: {exc}") from None
    return Response(
        content=upstream.content,
        status_code=upstream.status_code,
        media_type=upstream.headers.get("content-type", "application/octet-stream"),
    )


@router.websocket("/ws")
async def proxy_websocket(websocket: WebSocket) -> None:
    """Relevo transparente de bytes entre el navegador y el WebSocket real de
    ttyd, sin interpretar el protocolo de ttyd: solo copia frames tal cual,
    preservando si son binarios o de texto."""
    token = session_token(websocket)
    if not TTYD_PASSWORD:
        await websocket.close(code=1011)
        return

    try:
        async with websockets.connect(
            _upstream_ws_url(),
            additional_headers=_ttyd_ws_headers(),
            subprotocols=["tty"],
        ) as upstream:
            await websocket.accept(subprotocol="tty")
            await _relay(websocket, upstream, token)
    except (websockets.exceptions.WebSocketException, OSError, HTTPException):
        if websocket.client_state != WebSocketState.DISCONNECTED:
            await websocket.close(code=1011)


async def _relay(client_ws: WebSocket, upstream_ws, token: str) -> None:
    async def client_to_upstream() -> None:
        while True:
            msg = await client_ws.receive()
            if msg["type"] == "websocket.disconnect":
                return
            if msg.get("bytes") is not None:
                await upstream_ws.send(msg["bytes"])
            elif msg.get("text") is not None:
                await upstream_ws.send(msg["text"])

    async def upstream_to_client() -> None:
        async for message in upstream_ws:
            if isinstance(message, (bytes, bytearray)):
                await client_ws.send_bytes(bytes(message))
            else:
                await client_ws.send_text(message)

    async def session_watchdog() -> None:
        # La conexión puede vivir largo rato sin que ninguna de las dos
        # direcciones produzca bytes (operador mirando salida en silencio);
        # se revisa aparte en vez de solo antes de cada receive().
        while True:
            await asyncio.sleep(_SESSION_RECHECK_SECONDS)
            if not verify_session_token(token):
                return

    tasks = [asyncio.create_task(coro()) for coro in (client_to_upstream, upstream_to_client, session_watchdog)]
    try:
        await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        if upstream_ws.state.name != "CLOSED":
            await upstream_ws.close()
        if client_ws.client_state != WebSocketState.DISCONNECTED:
            await client_ws.close()
