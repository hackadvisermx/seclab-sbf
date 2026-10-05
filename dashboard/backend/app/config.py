import os
import pathlib
from typing import List

# Rutas base
APP_DIR = pathlib.Path(__file__).resolve().parent
BACKEND_DIR = APP_DIR.parent
DASHBOARD_DIR = pathlib.Path(os.environ.get("DASHBOARD_DIR", str(BACKEND_DIR.parent)))
REPO_ROOT = pathlib.Path(os.environ.get("REPO_ROOT", str(DASHBOARD_DIR.parent)))

# Detección de Workspace
DEFAULT_WS = pathlib.Path("/workspace") if pathlib.Path("/workspace").exists() else REPO_ROOT / "workspace"
WORKSPACE_DIR = pathlib.Path(os.environ.get("WORKSPACE_DIR", os.environ.get("SECLAB_WORKSPACE_DIR", str(DEFAULT_WS)))).resolve()

# Directorio de datos locales
DEFAULT_DATA_DIR = pathlib.Path("/var/lib/seclab/dashboard") if pathlib.Path("/var/lib/seclab").exists() else BACKEND_DIR / "data"
DATA_DIR = pathlib.Path(os.environ.get("SECLAB_DATA_DIR", str(DEFAULT_DATA_DIR)))
DATA_DIR.mkdir(parents=True, exist_ok=True)
VAULT_DB_PATH = DATA_DIR / "vault.db"
VAULT_KEY_PATH = DATA_DIR / ".vault.key"
RECON_DB_PATH = DATA_DIR / "recon-jobs.db"

# Red y Puerto
HOST = os.environ.get("DASHBOARD_HOST", "0.0.0.0")
PORT = int(os.environ.get("DASHBOARD_PORT", "8080"))

# Rutas de herramientas del laboratorio
SCRIPTS_DIR = pathlib.Path("/usr/local/bin") if pathlib.Path("/usr/local/bin/pt-scope-validator").exists() else REPO_ROOT / "scripts"
SHELL_DIR = REPO_ROOT / "shell"
CHEATSHEET_FILE = pathlib.Path("/home/tester/.oh-my-zsh/custom/plugins/pentest-lab/cheatsheet.tsv") if pathlib.Path("/home/tester/.oh-my-zsh/custom/plugins/pentest-lab/cheatsheet.tsv").exists() else SHELL_DIR / "pentest-lab" / "cheatsheet.tsv"
SKILLS_DIR = pathlib.Path("/workspace/skills") if pathlib.Path("/workspace/skills").exists() else REPO_ROOT / "skills"
TEMPLATES_DIR = pathlib.Path("/workspace/templates") if pathlib.Path("/workspace/templates").exists() else REPO_ROOT / "workspace-seed" / "templates"

# Seguridad y Autenticación
AUTH_ENABLED = True
SESSION_SECONDS = 8 * 60 * 60
LAB_ENV_FILE = pathlib.Path(os.environ.get("ENV_FILE_PATH", "/run/secrets/lab.env"))
if not LAB_ENV_FILE.exists():
    LAB_ENV_FILE = REPO_ROOT / ".env"

def load_lab_settings(path: pathlib.Path) -> dict:
    settings = {}
    if path.exists():
        for line in path.read_text().splitlines():
            key, separator, value = line.partition("=")
            if separator and key not in settings and key in {"TTYD_PASSWORD", "DASHBOARD_PASSWORD", "DASHBOARD_CORS_ORIGINS", "DASHBOARD_ALLOWED_HOSTS"}:
                settings[key] = value
    return settings


lab_settings = load_lab_settings(LAB_ENV_FILE)
TESTER_PASSWORD = os.environ.get("DASHBOARD_PASSWORD") or lab_settings.get("DASHBOARD_PASSWORD") or lab_settings.get("TTYD_PASSWORD", "")
CORS_ORIGINS: List[str] = [value.strip() for value in os.environ.get(
    "DASHBOARD_CORS_ORIGINS", lab_settings.get("DASHBOARD_CORS_ORIGINS", "http://localhost:8080,http://127.0.0.1:8080"),
).split(",") if value.strip()]
ALLOWED_HOSTS = [value.strip() for value in os.environ.get(
    "DASHBOARD_ALLOWED_HOSTS", lab_settings.get("DASHBOARD_ALLOWED_HOSTS", "localhost,127.0.0.1"),
).split(",") if value.strip()]
if not CORS_ORIGINS or not ALLOWED_HOSTS or any("*" in value for value in CORS_ORIGINS + ALLOWED_HOSTS):
    raise RuntimeError("El dashboard requiere orígenes y hosts explícitos.")
