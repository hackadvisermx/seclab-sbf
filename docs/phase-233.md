# Fase 233 — Historial y Comparador de Revisiones de Alcance target.yaml (V3-01h)

## Contexto y Motivación
La iniciativa V3-01 establece que el contrato de alcance (`target.yaml`) debe ser trazable, inmutable en su auditoría y explicable para el operador. En auditorías prolongadas o entornos compartidos, los objetivos dentro y fuera de alcance, las reglas de comodines y las autorizaciones evolucionan a lo largo de las sesiones. Sin un registro histórico de revisiones de alcance, el auditor o supervisor no puede auditar qué cambios ocurrieron, quién los autorizó o qué diferencias exactas se introdujeron entre iteraciones.

Esta fase implementa el registro atómico e inmutable de revisiones de `target.yaml` en `evidence/.revisions/target_yaml.jsonl`, con cálculo de diferencias unificadas (`diff`), hashes SHA-256 previos y nuevos, endpoint backend, método de API y modal interactivo «📜 Revisiones de Alcance» en la pestaña Alcance (`EngagementDetailView.vue`).

## Cambios Implementados

1. **Módulo de Alcance (`scripts/seclab_scope.py`)**:
   - `record_scope_revision(engagement_dir, new_yaml_content, author)`: Registra en `evidence/.revisions/target_yaml.jsonl` la acción (`created` o `updated`), timestamp UTC, autor, hash SHA-256 previo y nuevo, y diff unificado exacto entre el `target.yaml` anterior y el nuevo.
   - `get_scope_revisions(engagement_dir)`: Lee las revisiones históricas del engagement y las devuelve en orden cronológico inverso (la más reciente primero).

2. **Servicio y Endpoint Backend (`dashboard/backend`)**:
   - En `workspace_sync.py`: `save_target_yaml` invoca `record_scope_revision` inmediatamente antes de escribir en disco; método `get_scope_revisions`.
   - Endpoint `GET /api/v1/scope/{eng_id}/revisions` en `dashboard/backend/app/api/endpoints/scope.py`.

3. **Cliente Frontend (`dashboard/frontend/src/api.js`)**:
   - Método `api.getScopeRevisions(id, type)`.

4. **Interfaz Dashboard (`dashboard/frontend/src/views/EngagementDetailView.vue`)**:
   - Botón interactivo «📜 Revisiones de Alcance» (`data-testid="scope-revisions-btn"`) en la barra de herramientas de la pestaña Alcance.
   - Modal táctico `scope-revisions-modal` con visor de diff unificado, identificador de revisión, autor, fecha y hashes criptográficos.

5. **Pruebas y Verificación**:
   - Pruebas unitarias Python en host (`scripts/verify/test_seclab_scope_revisions.py`).
   - Pruebas frontend en Vitest (`dashboard/frontend/tests/scope-revisions.test.js`).
   - Suite completa de frontend (186 pruebas aprobadas), build de producción Vite verificado y suite `make verify`.
