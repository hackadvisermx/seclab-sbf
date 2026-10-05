import hmac
import threading
import time
from collections import deque
from fastapi import APIRouter, Depends, HTTPException, Request, Response, WebSocketException
from pydantic import BaseModel, Field
from app.config import TESTER_PASSWORD, SESSION_SECONDS, CORS_ORIGINS
from starlette.requests import HTTPConnection
from app.core.security import create_session_token, verify_session_token, revoke_session_token

router = APIRouter(prefix="/auth", tags=["Autenticación"])
COOKIE_NAME = 'seclab_session'
_attempts = deque(maxlen=5)
_lock = threading.Lock()


def session_token(request: HTTPConnection) -> str:
    authorization = request.headers.get('authorization', '')
    if authorization.startswith('Bearer '):
        return authorization[7:].strip()
    return request.cookies.get(COOKIE_NAME, '')


def require_operator(request: HTTPConnection) -> str:
    if request.scope['type'] == 'websocket' and request.headers.get('origin') not in CORS_ORIGINS:
        raise WebSocketException(code=1008)
    user = verify_session_token(session_token(request))
    if not user:
        if request.scope['type'] == 'websocket':
            raise WebSocketException(code=1008)
        raise HTTPException(status_code=401, detail='Inicia sesión para acceder al dashboard.')
    return user


class LoginRequest(BaseModel):
    username: str = Field(default='tester', max_length=64)
    password: str = Field(max_length=1024)


@router.post('/login')
def login(payload: LoginRequest, request: Request, response: Response):
    if not TESTER_PASSWORD:
        raise HTTPException(status_code=503, detail='Configura la contraseña del laboratorio.')
    with _lock:
        now = time.monotonic()
        while _attempts and _attempts[0] <= now - 60:
            _attempts.popleft()
        if len(_attempts) >= 5:
            raise HTTPException(status_code=429, detail='Espera un minuto antes de volver a intentar.', headers={'Retry-After': '60'})
        _attempts.append(now)
    if payload.username != 'tester' or not hmac.compare_digest(payload.password.encode(), TESTER_PASSWORD.encode()):
        raise HTTPException(status_code=401, detail='Credenciales incorrectas')
    old_token = session_token(request)
    if old_token:
        revoke_session_token(old_token)
    token = create_session_token('tester')
    response.set_cookie(COOKIE_NAME, token, max_age=SESSION_SECONDS, httponly=True,
                        secure=request.url.scheme == 'https', samesite='strict', path='/api/v1')
    response.headers['Cache-Control'] = 'no-store'
    return {'username': 'tester', 'auth_enabled': True}


@router.get('/me')
def get_current_user(user: str = Depends(require_operator)):
    return {'authenticated': True, 'username': user, 'auth_enabled': True}


@router.post('/logout')
def logout(request: Request, response: Response, user: str = Depends(require_operator)):
    revoke_session_token(session_token(request))
    response.delete_cookie(COOKIE_NAME, path='/api/v1', httponly=True, samesite='strict')
    return {'authenticated': False}
