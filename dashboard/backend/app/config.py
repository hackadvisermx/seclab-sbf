import os
import pathlib
from typing import List

# Rutas base
APP_DIR = pathlib.Path(__file__).resolve().parent
BACKEND_DIR = APP_DIR.parent
DASHBOARD_DIR = BACKEND_DIR.parent
REPO_ROOT = DASHBOARD_DIR.parent

# Detección de Workspace
DEFAULT_WS = REPO_ROOT / "workspace" if (REPO_ROOT / "workspace").exists() else pathlib.Path("/workspace")
WORKSPACE_DIR = pathlib.Path(os.environ.get("WORKSPACE_DIR", os.environ.get("SECLAB_WORKSPACE_DIR", str(DEFAULT_WS)))).resolve()

# Directorio de datos locales
DATA_DIR = BACKEND_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
VAULT_DB_PATH = DATA_DIR / "vault.db"
VAULT_KEY_PATH = DATA_DIR / ".vault.key"

# Red y Puerto
HOST = os.environ.get("DASHBOARD_HOST", "0.0.0.0")
PORT = int(os.environ.get("DASHBOARD_PORT", "8080"))

# Rutas de herramientas del laboratorio
SCRIPTS_DIR = REPO_ROOT / "scripts"
SHELL_DIR = REPO_ROOT / "shell"
CHEATSHEET_FILE = SHELL_DIR / "pentest-lab" / "cheatsheet.tsv"
SKILLS_DIR = REPO_ROOT / "skills"
TEMPLATES_DIR = REPO_ROOT / "workspace-seed" / "templates"

# Seguridad y Autenticación
SECRET_KEY = os.environ.get("SECLAB_SECRET_KEY", "seclab-tactical-dashboard-secret-key-default-2026")
AUTH_ENABLED = os.environ.get("DASHBOARD_AUTH_ENABLED", "false").lower() in ("true", "1", "yes")

# Intentar leer contraseña configurada en .env o secretos
LAB_ENV_FILE = pathlib.Path("/run/secrets/lab.env")
if not LAB_ENV_FILE.exists():
    LAB_ENV_FILE = REPO_ROOT / ".env"

TESTER_PASSWORD = os.environ.get("TESTER_PASSWORD", "tester")
if LAB_ENV_FILE.exists():
    try:
        for line in LAB_ENV_FILE.read_text().splitlines():
            line = line.strip()
            if line.startswith("TESTER_PASSWORD="):
                TESTER_PASSWORD = line.split("=", 1)[1].strip().strip("'\"")
    except Exception:
        pass

CORS_ORIGINS: List[str] = [
    "http://localhost:5173", # Vite dev server
    "http://127.0.0.1:5173",
    "http://localhost:8080",
    "http://127.0.0.1:8080",
    "*" # Permite Tailscale IP
]
