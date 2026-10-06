# Fase 96 — Resolución del Catálogo pt-cheat (48 Comandos) y Playbooks de Habilidades (skills/)

Corrección integral de la resolución de rutas del catálogo táctico `pt-cheat` (`cheatsheet.tsv`) y de los playbooks de metodologías (`skills/`) tanto en el backend/frontend del Dashboard como en la terminal CLI del contenedor.

## Diagnóstico del problema raíz

1. **Resolución errónea de `CHEATSHEET_FILE`**:
   - En [`dashboard/backend/app/config.py`](file:///Users/castr/tmp/t01/dashboard/backend/app/config.py), `CHEATSHEET_FILE` dependía de `SHELL_DIR / "pentest-lab" / "cheatsheet.tsv"`.
   - En el entorno de ejecución del contenedor, `REPO_ROOT` es `/usr/local/share/seclab`, lo que construía la ruta inexistente `/usr/local/share/seclab/shell/pentest-lab/cheatsheet.tsv`.
   - El archivo real se instala en `/usr/local/share/seclab/pentest-lab/cheatsheet.tsv` y en `/opt/seclab/oh-my-zsh/custom/plugins/pentest-lab/cheatsheet.tsv`, causando que `get_cheatsheet()` retornara una lista vacía `[]`.

2. **Ausencia de `skills/` a nivel de sistema en la imagen**:
   - [`images/full/Dockerfile`](file:///Users/castr/tmp/t01/images/full/Dockerfile) únicamente copiaba las habilidades dentro de `/workspace/skills` al sembrar `workspace-seed/`.
   - Cuando Docker Compose montaba la carpeta del host `./workspace` como bind mount (`- ./workspace:/workspace`), ocultaba el contenido original de la imagen si el host fue creado previamente sin la carpeta `skills/`.
   - Además, `pt-skills-dir` y `SKILLS_DIR` buscaban `/usr/local/share/seclab/skills`, directorio que no era copiado durante el build de la imagen Docker.

3. **Sobrescritura de metadatos en el parseo de `SKILL.md`**:
   - En [`dashboard/backend/app/api/endpoints/help_center.py`](file:///Users/castr/tmp/t01/dashboard/backend/app/api/endpoints/help_center.py), el ciclo de lectura de `SKILL.md` iteraba hasta el final del archivo reemplazando `title` por cualquier línea que empezara con `# `, causando que subtítulos dentro del cuerpo del playbook reemplazaran el título principal.

## Solución implementada

1. **Resolución robusta con múltiples candidatos en `config.py`**:
   - `_resolve_cheatsheet_file()`: Consulta secuencialmente `/usr/local/share/seclab/pentest-lab/cheatsheet.tsv`, `/opt/seclab/oh-my-zsh/...`, `/home/tester/.oh-my-zsh/...`, `SHELL_DIR / "pentest-lab" / "cheatsheet.tsv"` y rutas de desarrollo del repositorio.
   - `_resolve_skills_dir()`: Consulta secuencialmente `WORKSPACE_DIR / "skills"`, `/workspace/skills`, `/usr/local/share/seclab/skills`, `REPO_ROOT / "skills"` y `REPO_ROOT / "workspace-seed" / "skills"`.
   - `_resolve_templates_dir()`: Consulta secuencialmente `WORKSPACE_DIR / "templates"`, `/workspace/templates`, `/usr/local/share/seclab/templates` y `REPO_ROOT / "workspace-seed" / "templates"`.

2. **Instalación de `skills/` y `templates/` en el sistema (`images/full/Dockerfile`)**:
   - Se agregaron las directivas `COPY skills/ /usr/local/share/seclab/skills/` y `COPY workspace-seed/templates/ /usr/local/share/seclab/templates/` con permisos de sólo lectura `0555`.
   - Garantiza que `pt-skills`, `pt-agent-context` y la API del Dashboard dispongan de las habilidades en cualquier escenario de montura.

3. **Sincronización defensiva en `Makefile`**:
   - La regla `workspace-dir` ahora verifica si existen `skills` y `templates` en la carpeta del host (`$(WORKSPACE_DIR)`), copiándolos desde `workspace-seed/` si están ausentes para no ocultarlos en el bind mount.

4. **Corrección de extracción de metadatos en `help_center.py`**:
   - `list_skills()` solo captura el primer encabezado `# ` y la primera descripción, garantizando nombres limpios como `Skill: Modern API & Webhook Security Audit (api-security-audit)`.

5. **Inclusión en cálculo de insumos (`scripts/build-inputs.py`)**:
   - Se añadió `'skills'` a `FULL_DIRS` para calcular adecuadamente el hash de insumos de imagen completa.

## Validación

- `npm --prefix dashboard/frontend test`: 12 pruebas pasando exitosamente.
- `gitleaks dir . --no-banner --config .gitleaks.toml`: 0 fugas.
- `make verify`: 117 pruebas Python aprobadas.
- `make dashboard-tests`: 61 pruebas aprobadas (+2 nuevas pruebas en `test_evidence_first_hunting.py` verificando la carga completa de 48 comandos de `cheatsheet` y 10 playbooks de `skills`).
- Verificación en terminal: `pt-skills-dir` resuelve `/workspace/skills` y `pt-skills view api-security-audit` renderiza el contenido correctamente.
