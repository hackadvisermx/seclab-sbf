from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from app.config import CORS_ORIGINS, DASHBOARD_DIR, TESTER_PASSWORD, ALLOWED_HOSTS
from app.core.database import init_db
from app.api.router import api_router


# Asegurar inicialización inmediata de tablas
init_db()

@asynccontextmanager
async def lifespan(app: FastAPI):
    if not TESTER_PASSWORD:
        raise RuntimeError("Configura TTYD_PASSWORD en lab.env o DASHBOARD_PASSWORD.")
    init_db()
    yield


app = FastAPI(
    title="SecLab Tactical Dashboard API",
    description="Backend unificado de gestión de auditorías, alcance, hallazgos y Hermes API Key Vault para SecLab-SBF.",
    version="1.0.0",
    lifespan=lifespan,
    docs_url=None, redoc_url=None, openapi_url=None,
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)

from starlette.middleware.trustedhost import TrustedHostMiddleware
app.add_middleware(TrustedHostMiddleware, allowed_hosts=ALLOWED_HOSTS)

@app.middleware("http")
async def protect_origin(request: Request, call_next):
    origin = request.headers.get("origin")
    if request.method not in ("GET", "HEAD", "OPTIONS") and origin and origin not in CORS_ORIGINS:
        return JSONResponse({"detail": "Origen no permitido."}, status_code=403)
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "same-origin"
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    return response

from app.core.workspace_paths import UnsafeWorkspacePath

@app.exception_handler(UnsafeWorkspacePath)
async def invalid_workspace_path(request: Request, error: UnsafeWorkspacePath):
    return JSONResponse({"detail": str(error)}, status_code=400)

# Enrutar API v1
app.include_router(api_router)

# Montar frontend compilado si existe
dist_dir = DASHBOARD_DIR / "frontend" / "dist"
assets_dir = dist_dir / "assets"

if dist_dir.exists() and (dist_dir / "index.html").exists():
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

    @app.api_route("/{full_path:path}", methods=["GET", "HEAD"], response_class=HTMLResponse)
    def serve_spa(full_path: str):
        potential_file = (dist_dir / full_path).resolve()
        if not potential_file.is_relative_to(dist_dir.resolve()):
            return JSONResponse({"detail": "Ruta no permitida."}, status_code=400)
        if full_path and potential_file.is_file():
            from fastapi.responses import FileResponse
            return FileResponse(str(potential_file))
        return (dist_dir / "index.html").read_text(encoding="utf-8")
else:
    @app.get("/", response_class=HTMLResponse)
    def index():
        return """
        <!DOCTYPE html>
        <html lang="es">
        <head>
            <meta charset="UTF-8">
            <title>SecLab Tactical Dashboard</title>
            <style>
                body { background: #0b0f19; color: #00ffcc; font-family: monospace; display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; }
                .card { border: 1px solid #00ffcc; padding: 2rem; border-radius: 8px; box-shadow: 0 0 20px rgba(0,255,204,0.2); max-width: 600px; text-align: center; }
                h1 { margin-top: 0; color: #fff; }
                a { color: #38bdf8; text-decoration: none; font-weight: bold; }
                a:hover { text-decoration: underline; }
                .badge { background: #1e293b; padding: 4px 8px; border-radius: 4px; border: 1px solid #334155; display: inline-block; margin: 4px; }
            </style>
        </head>
        <body>
            <div class="card">
                <h1>⚡ SecLab Tactical Dashboard</h1>
                <p>Backend API de Control de Auditorías & Hermes Vault Activo.</p>
                <div style="margin: 1.5rem 0;">
                    <span class="badge">FastAPI 3.14</span>
                    <span class="badge">SQLite AES-256 Vault</span>
                    <span class="badge">Evidence-First</span>
                </div>
                <p>La API requiere una sesión del operador.</p>
            </div>
        </body>
        </html>
        """
