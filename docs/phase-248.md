# Fase 248 — Remediación Integral de Auditoría (Ronda 5): Cierre de Destinos No Reconocidos (B3), Validación Estática Fail-Closed (M4) y Diferenciación de Artefactos (M5)

## Resumen Ejecutivo

- **ID de Mejora:** Auditoría de Seguridad & Robustecimiento de Salvaguardas — Ronda 5 (Blocker B3, Major M4 y M5).
- **Objetivo:** Resolver de forma exhaustiva los hallazgos de la quinta auditoría de seguridad sobre el commit `67f4b8c`:
  1. Extracción universal de formatos de destinos literales en playbooks: esquemas URI distintos de HTTP/HTTPS (ej. `ftp://`, `ws://`, etc.), direcciones IPv6 sin corchetes (ej. `2001:db8::bad`), hosts con rutas o puertos (`evil.com/path`, `evil.com:8080/path`), y comandos con destinos combinados (válidos + inválidos) para evaluación estricta en Scope Guard.
  2. Detección y bloqueo determinista de archivos de objetivos vacíos (ej. `recon/empty.txt`) tanto en simulación (`dry_run=True`) como en ejecución real (`dry_run=False`), eliminando falsos positivos en `validate_playbook_against_scope`.
  3. Diferenciación rigurosa entre archivos de objetivos (target-bearing) y artefactos/dependencias de datos (ej. `recon/graphql_introspection.json`, `target.yaml`), garantizando que la ausencia o vacío de un artefacto previo no bloquee pasos activos con placeholders canónicos en alcance ({domain}).
  4. Bloqueo preventivo fail-closed de destinos dinámicos no verificables mediante sustituciones de shell (`$VAR`, `${VAR}`, `$(...)`, ``` `...` ```) en pasos activos.
- **Hallazgos Resueltos:**
  - **B3 (Blocker - Destinos literales no reconocidos y destinos combinados):**
    - Se creó la función unificada `_extract_literal_targets` en `scripts/seclab_playbook.py` que detecta cualquier URI con esquema, direcciones IPv6 con o sin corchetes, direcciones IPv4 con puertos o rutas, y nombres de host/dominio/FQDN con o sin rutas o puertos.
    - Se garantiza que en comandos como `curl https://target.local evil.com/path`, todos los destinos son extraídos y evaluados por Scope Guard; si alguno resulta fuera de alcance o con esquema no autorizado, el paso queda `BLOCKED` con `can_execute=False` y en ejecución real se detiene con código 126.
    - Se añadió `step_has_unverified_dynamic_targets` para bloquear preventivamente cualquier sustitución de shell dinámica en pasos activos.
  - **M4 (Major - Validación estática permisiva ante fuentes sin candidatos):**
    - En `extract_step_targets`, se eliminó el condicionamiento `and not dry_run` al leer archivos de objetivos: si un archivo de objetivos existe en disco y tiene 0 líneas válidas, produce `missing_file_error` determinista tanto en dry-run como en ejecución real.
    - En `validate_playbook_against_scope`, todo paso activo sin placeholders de destino y sin candidatos resolubles es marcado como `BLOCKED` con `can_execute=False`.
  - **M5 (Major - Ambigüedad entre archivos de objetivos y artefactos de datos):**
    - Se refinó la selección de archivos candidatos (`file_candidates`) en `extract_step_targets`: los archivos en `inputs` solo se tratan como fuentes de objetivos si el paso no posee placeholders de destino ni selector canónico, o si el archivo está explícitamente referenciado en el comando como lista de objetivos.
    - Los artefactos de salida (como archivos `.json` de introspección GraphQL o esquemas intermedios) no son tratados como listas de objetivos y no bloquean pasos que ya cuentan con destinos canónicos `{domain}` autorizados.
- **Archivos modificados:**
  - `scripts/seclab_playbook.py`: Extractor canónico `_extract_literal_targets`, extractor de objetivos de paso `extract_step_targets`, función `step_has_declared_target_source`, detector de variables dinámicas `step_has_unverified_dynamic_targets`, validación estática estricta en `validate_playbook_against_scope` y compuertas en `execute_playbook_step`.
  - `scripts/verify/test_seclab_playbook.py`: +4 pruebas unitarias de regresión cubriendo destinos combinados, IPv6 sin corchetes, esquemas FTP, destinos literales en alcance con rutas/puertos, variables dinámicas de shell, archivos vacíos y diferenciación de artefactos GraphQL.
- **Verificación:**
  - `check-python-units.py`: 344 pruebas unitarias aprobadas (+4 pruebas vs Fase 247).
  - Suite de playbooks: `test_seclab_playbook.py` con 37/37 pruebas aprobadas (+4 pruebas).
  - Pruebas semilla: `test_playbook_api_seeds.py` (6/6), `test_playbook_infra_seeds.py` (6/6) y `test_playbook_step_run.py` (2/2) aprobadas.
  - Pruebas backend API: `dashboard.backend.tests.test_playbooks_api` con 2/2 pruebas aprobadas en contenedor efímero.
  - `git diff --check`: Salida limpia, cero advertencias de formato o trailing whitespace.
