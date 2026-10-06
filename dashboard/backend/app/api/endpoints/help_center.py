import pathlib
import re
from typing import Any, Dict, List
from fastapi import APIRouter, HTTPException
from app.config import CHEATSHEET_FILE, SKILLS_DIR

router = APIRouter(prefix="/help", tags=["Centro de Ayuda & Tácticas"])


@router.get("/cheatsheet")
def get_cheatsheet():
    """Lee y parsea el archivo de cheatsheet interactivo cheatsheet.tsv."""
    if not CHEATSHEET_FILE.exists():
        return []

    entries = []
    for line in CHEATSHEET_FILE.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) >= 4:
            entries.append({
                "category": parts[0].strip(),
                "title": parts[1].strip(),
                "command": parts[2].strip(),
                "description": parts[3].strip(),
            })
    return entries


@router.get("/skills")
def list_skills():
    """Lista las metodologías y playbooks de habilidades disponibles en skills/."""
    if not SKILLS_DIR.exists() or SKILLS_DIR.is_symlink():
        return []

    skills = []
    for skill_path in sorted(SKILLS_DIR.iterdir()):
        if not skill_path.is_symlink() and skill_path.is_dir() and (skill_path / "SKILL.md").is_file() and not (skill_path / "SKILL.md").is_symlink():
            skill_md = skill_path / "SKILL.md"
            title = skill_path.name
            description = ""
            try:
                for line in skill_md.read_text(encoding="utf-8").splitlines():
                    if line.startswith("# ") and title == skill_path.name:
                        title = line.replace("# ", "").strip()
                    elif (line.startswith("description:") or line.startswith("> ")) and not description:
                        description = line.replace("description:", "").replace("> ", "").strip()
            except Exception:
                pass

            skills.append({
                "id": skill_path.name,
                "title": title,
                "description": description,
            })
    return skills


@router.get("/skills/{skill_id}")
def get_skill_detail(skill_id: str):
    """Devuelve el contenido completo en Markdown del playbook solicitado."""
    skill_dir = SKILLS_DIR / skill_id
    skill_file = skill_dir / "SKILL.md"
    if (not re.fullmatch(r"[a-zA-Z0-9-][a-zA-Z0-9._-]{0,127}", skill_id)
            or SKILLS_DIR.is_symlink() or skill_dir.is_symlink() or skill_file.is_symlink()
            or not skill_file.resolve().is_relative_to(SKILLS_DIR.resolve()) or not skill_file.is_file()):
        raise HTTPException(status_code=404, detail="Skill no encontrada")
    return {
        "id": skill_id,
        "content": skill_file.read_text(encoding="utf-8", errors="ignore"),
    }
