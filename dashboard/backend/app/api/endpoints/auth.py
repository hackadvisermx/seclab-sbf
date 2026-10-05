from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
from app.config import TESTER_PASSWORD, AUTH_ENABLED
from app.core.security import create_session_token, verify_session_token

router = APIRouter(prefix="/auth", tags=["Autenticación"])


class LoginRequest(BaseModel):
    username: str = "tester"
    password: str


class LoginResponse(BaseModel):
    token: str
    username: str
    auth_enabled: bool


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest):
    """Autentica al operador contra las credenciales del laboratorio."""
    if payload.username != "tester" or payload.password != TESTER_PASSWORD:
        raise HTTPException(status_code=401, detail="Credenciales incorrectas")

    token = create_session_token(payload.username)
    return LoginResponse(
        token=token,
        username=payload.username,
        auth_enabled=AUTH_ENABLED,
    )


@router.get("/me")
def get_current_user(authorization: str = Header(None)):
    """Verifica si la sesión actual es válida."""
    if not AUTH_ENABLED:
        return {"authenticated": True, "username": "tester", "auth_enabled": False}

    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Token no suministrado")

    token = authorization.split("Bearer ", 1)[1].strip()
    user = verify_session_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="Token expirado o inválido")

    return {"authenticated": True, "username": user, "auth_enabled": True}
