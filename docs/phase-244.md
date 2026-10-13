# Fase 244 — Remediación Integral de Auditoría: Salvaguardas Fail-Closed en Playbooks, Vigencia Temporal, Scope Guard y Aislamiento de Proyectos

## Resumen Ejecutivo

- **ID de Mejora:** Auditoría de Seguridad & Robustecimiento de Salvaguardas (Blockers B1, B2, B3; Majors M1, M2).
- **Objetivo:** Subsanar los 5 hallazgos de seguridad y trazabilidad reportados en la auditoría post-v3.0.0, implementando salvaguardas fail-closed en ejecuciones reales de playbooks, validación canónica de vigencia temporal de autorizaciones (`require_authorization`), verificación de destinos contra Scope Guard (`check_scope`), resolución segura de proyectos (`project_directory`) y preservación de identificadores de checkpoints en exportaciones de supervisión.
- **Hallazgos Resueltos:**
  - **B1 (Blocker - Fail-closed sin target.yaml):** Rechazo inmediato de ejecuciones reales (`dry_run=false`) sin `engagement_id` o sin `target.yaml` válido en `scripts/seclab_playbook.py` y `dashboard/backend/app/api/endpoints/playbooks.py`. Eliminación de condiciones laxas por omisión.
  - **B2 (Blocker - Vigencia temporal de autorización):** Integración del contrato canónico `require_authorization` en `validate_playbook_against_scope` para verificar las fechas `valid_from` y `valid_until` de `target.yaml`. Bloqueo inmediato de pasos activos y pasivos si la ventana expiró.
  - **B3 (Blocker - Destinos vinculados a Scope Guard):** Vinculación de `target_selector` y parámetros de destino (`domain`, `target`, etc.) con `check_scope`. Bloqueo automático (código 126 / `BLOCKED`) ante objetivos con veredicto `OUT_OF_SCOPE` o `UNKNOWN`.
  - **M1 (Major - Identificadores canónicos en supervisión):** Preservación de la columna de ID canónico (`cp_scope`, `cp_recon`, `cp_evidence`, `cp_report`) en la tabla de exportación Markdown en `supervision_service.py` y `seclab_supervision.py`, resolviendo el fallo funcional de la prueba backend.
  - **M2 (Major - Aislamiento e identidad de proyectos):** Centralización de la resolución de rutas mediante `project_directory` en todos los endpoints de Playbooks, neutralizando path traversal (`../../`) y manipulación de enlaces simbólicos.
  - **Sugerencias:** Inclusión de `include_in_schema=False` en la ruta SPA de `main.py` eliminando la advertencia de `Duplicate Operation ID`, y actualización del mock de `getCrossEngagementMetricsSummary` en pruebas de frontend.
- **Archivos modificados:**
  - `scripts/seclab_playbook.py`: Salvaguardas fail-closed, validación de vigencia temporal y Scope Guard sobre parámetros.
  - `dashboard/backend/app/api/endpoints/playbooks.py`: Uso de `project_directory`, validación obligatoria de proyecto/scope en ejecuciones reales y paso de `scope_data`.
  - `dashboard/backend/app/services/supervision_service.py`: ID de checkpoint en exportación Markdown.
  - `scripts/seclab_supervision.py`: ID de checkpoint en exportación Markdown CLI.
  - `dashboard/backend/app/main.py`: Ocultación de ruta catch-all de SPA en OpenAPI schema.
  - `dashboard/frontend/tests/create-engagement-redirect.test.js`: Mock de `getCrossEngagementMetricsSummary`.
  - `scripts/verify/test_seclab_playbook.py`: 6 nuevas pruebas de regresión cubriendo B1, B2 y B3.
  - `dashboard/backend/tests/test_playbooks_api.py`: Nuevas pruebas de seguridad para B1, B2, B3 y M2 en endpoints.
- **Verificación:**
  - `check-python-units.py`: 315 pruebas unitarias aprobadas (+6 pruebas nuevas).
  - Backend tests: `test_supervision_service.py` (4/4 aprobadas), `test_playbooks_api.py` (2/2 aprobadas).
  - Frontend: 193 pruebas en Vitest aprobadas sin advertencias.
  - Contenedor: `make smoke-test` con 14 suites aprobadas en imagen efímera.
  - Comandos make, compose refs y makefile lint aprobados.
