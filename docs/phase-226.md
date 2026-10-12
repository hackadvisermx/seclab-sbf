# Fase 226 — Advertencia Operacional Explícita de Terminal Libre en Scope Guard (V3-01g)

## Contexto y Motivación
El criterio de aceptación de la iniciativa V3-01 establece formalmente:
> «La terminal libre y cualquier herramienta que pueda eludir el límite de ejecución tienen un tratamiento explícito: se añade un control técnico viable o se declara con claridad que Scope Guard no intercepta esa acción. La UI nunca promete una garantía global que el producto no aplica.»

En SecLab-SBF, el Scope Guard actúa como compuerta determinista e interceptora sobre todos los flujos gestionados por la aplicación: el pipeline de reconocimiento (`pt-recon-pipeline`), la ejecución de playbooks deterministas (`seclab_playbook.py`), las consultas del Copiloto y los endpoints FastAPI. Sin embargo, las sesiones interactivas en terminal libre ttyd (:7681) y conexiones SSH directas operan con la shell del sistema operativo (`tester`) y no son interceptadas a nivel de socket por el validador de alcance. Para prevenir falsas expectativas de seguridad y dar cumplimiento estricto a V3-01, esta fase formaliza la especificación de fronteras técnicas y visualiza advertencias operacionales transparentes tanto en la pestaña Alcance como en la vista de Terminal.

## Cambios Implementados

1. **Módulo de Alcance (`scripts/seclab_scope.py`)**:
   - Función canónica `get_scope_guard_boundaries()` que clasifica los canales del sistema en:
     - `enforced_mechanisms`: Flujos interceptados y validados (`dashboard_pipeline`, `deterministic_playbooks`, `api_endpoints`, `copilot_context`).
     - `unenforced_mechanisms`: Flujos sin intercepción (`interactive_terminal_ttyd`, `direct_cli_tools`), destacando la responsabilidad exclusiva del operador.
     - Texto declarativo oficial `notice`.

2. **Backend FastAPI (`dashboard/backend/app/api/endpoints/scope.py`)**:
   - Endpoint público `GET /api/v1/scope/boundaries/info` que expone la especificación canónica de límites operacionales.

3. **Cliente Frontend (`dashboard/frontend/src/api.js`)**:
   - Método `api.getScopeBoundaries()`.

4. **Interfaz Dashboard (`dashboard/frontend/src/views/EngagementDetailView.vue`)**:
   - Tarjeta táctica de fronteras técnicas (`data-testid="scope-boundaries-card"`) en la pestaña Alcance, detallando mecanismos cubiertos frente a terminal libre.

5. **Terminal Web (`dashboard/frontend/src/views/TerminalView.vue`)**:
   - Banner de advertencia táctica (`data-testid="terminal-scope-guard-notice"`) encima del frame de ttyd informando al operador sobre la ausencia de intercepción en la shell interactiva.

6. **Pruebas y Verificación**:
   - Pruebas unitarias de estructura y advertencias en host (`scripts/verify/test_scope_boundaries.py`).
   - Pruebas frontend en Vitest (`dashboard/frontend/tests/scope-boundaries.test.js`, 179 tests aprobados).
