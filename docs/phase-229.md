# Fase 229 — Ejecutor Táctico Paso a Paso de Playbooks Deterministas (V3-04f)

## Contexto y Motivación
La iniciativa V3-04 especifica que los playbooks deterministas deben ofrecer tanto ejecución completa como control granular interactivo para que el auditor u operador en formación pueda inspeccionar y disparar pasos individuales aislados («step-by-step runner»), comprobando las restricciones de Scope Guard antes de cada acción.

Esta fase incorpora el soporte end-to-end para la ejecución individual de pasos por ID, con verificación de políticas de alcance, sanitización de comandos y actualización reactiva de resultados paso a paso en el dashboard.

## Cambios Implementados

1. **Backend FastAPI (`dashboard/backend/app/api/endpoints/playbooks.py`)**:
   - Endpoint `POST /api/v1/playbooks/{playbook_id}/step/run` aceptando `PlaybookStepRunRequest` (`step_id`, `engagement_id`, `type`, `parameters`, `dry_run`).
   - Resuelve el playbook y el paso correspondiente, evalúa permisos contra `target.yaml` y ejecuta `execute_playbook_step(...)` de forma determinista y segura.

2. **Cliente Frontend (`dashboard/frontend/src/api.js`)**:
   - Método `api.runPlaybookStep(id, payload)`.

3. **Interfaz Dashboard (`dashboard/frontend/src/views/EngagementDetailView.vue`)**:
   - Botón interactivo «▶️ Paso» (`data-testid="run-playbook-step-btn"`) en la tarjeta de cada paso del playbook.
   - Función reactiva `runSingleStep(stepId)` con indicador visual de ejecución y refresco automático del estado (`step-status-<step_id>`) y salida conservada.

4. **Pruebas y Verificación**:
   - Pruebas unitarias de ejecución de paso en host (`scripts/verify/test_playbook_step_run.py`).
   - Pruebas frontend en Vitest (`dashboard/frontend/tests/playbook-step-run.test.js`, build Vite limpio).
