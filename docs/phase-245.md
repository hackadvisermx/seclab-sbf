# Fase 245 — Remediación Integral de Auditoría: Cierre Definitivo de Autorización Incompleta (B2) y Resolución Exhaustiva de Destinos (B3)

## Resumen Ejecutivo

- **ID de Mejora:** Auditoría de Seguridad & Robustecimiento de Salvaguardas — Ronda 2 (Blockers B2 y B3).
- **Objetivo:** Subsanar de forma definitiva los dos vectores de bypass restantes reportados en la segunda auditoría de seguridad sobre Playbooks, garantizando que ninguna autorización incompleta pueda habilitar tráfico real (B2) y que todos los destinos (placeholders arbitrarios en `command_template`, parámetros provistos y selectores basados en archivos como `recon/subdomains.txt`) queden estrictamente vinculados y verificados con Scope Guard (`check_scope`) en fail-closed (B3).
- **Hallazgos Resueltos:**
  - **B2 (Blocker - Autorización incompleta permite ejecución real):**
    - Se eliminó la compuerta condicional que omitía `require_authorization` cuando faltaban `reference`, `valid_from` o `valid_until`.
    - Ahora, toda declaración de `allow_passive: true` o `allow_active: true` ejecuta de manera estricta y universal `require_authorization`. Cualquier autorización que carezca de referencia o ventana temporal de vigencia es rechazada deterministamente en fail-closed (`allow_active = False`, `allow_passive = False`, estado `BLOCKED`).
    - Se añadió validación en profundidad en `execute_playbook_step` para rechazar cualquier intento de ejecución real sin contrato canónico completo.
  - **B3 (Blocker - `target_selector` no controla todos los destinos ni archivos):**
    - Implementación de `extract_step_targets`: resolución exhaustiva de todos los placeholders `{param}` en `command_template` consumidos por el paso (ej. `{endpoint}`, `{domain}`, etc., excluyendo banderas no de destino).
    - Inspección de todos los parámetros de destino provistos en `parameters`.
    - Soporte completo y seguro para selectores basados en archivos (ej. `recon/subdomains.txt` en `web_recon.yaml:32`): resolución contra `engagement_dir`, inspección de cada línea/destino contra `check_scope`, y bloqueo inmediato (código 126 / `BLOCKED`) si el archivo contiene destinos fuera de alcance o si el archivo no existe en una ejecución real (`not dry_run`).
  - **Robustez y Manejo de Errores (Sugerencias no bloqueantes):**
    - Manejo seguro de `ScopeError` en `check_scope` y `validate_playbook_against_scope`, devolviendo veredictos deterministas `BLOCKED` (HTTP 400 en API) sin generar excepciones 500 no controladas.
    - Sincronización de fixtures de pruebas unitarias (`test_seclab_playbook.py`, `test_playbook_infra_seeds.py`, `test_playbook_api_seeds.py`) con el estándar canónico `AUTHORIZATION_YAML`.
- **Archivos modificados:**
  - `scripts/seclab_playbook.py`: `extract_step_targets`, validación universal de contrato en B2, inspección exhaustiva de placeholders y archivos en B3, resolución de `engagement_dir` en `run_playbook`.
  - `dashboard/backend/app/api/endpoints/playbooks.py`: Inyección de `engagement_dir`, captura robusta de errores de alcance en `validate`, `run` y `step/run` devolviendo HTTP 400.
  - `scripts/verify/test_seclab_playbook.py`: Fixtures actualizados y 5 nuevas pruebas unitarias para autorización incompleta, placeholders arbitrarios (`{endpoint}`), selectores de archivos y manejo grácil de `target.yaml` sin `scope`.
  - `scripts/verify/test_playbook_infra_seeds.py`: Fixture actualizado con `AUTHORIZATION_YAML`.
  - `scripts/verify/test_playbook_api_seeds.py`: Fixture actualizado con `AUTHORIZATION_YAML`.
  - `dashboard/backend/tests/test_playbooks_api.py`: Pruebas de integración API para autorización incompleta y selectores basados en archivos con destinos no autorizados.
- **Verificación:**
  - `check-python-units.py`: 320 pruebas unitarias aprobadas (+5 pruebas nuevas).
  - Pruebas backend focalizadas: `test_playbooks_api.py` aprobada.
  - Pruebas frontend: 193 pruebas en Vitest aprobadas sin advertencias.
  - Contenedor efímero: `make smoke-test` con 14 suites aprobadas en imagen `seclab-sbf:full`.
