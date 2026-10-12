# Fase 221 — Persistencia de Evidencias de Ejecución de Playbooks (V3-04e)

## Contexto y Motivación
Los playbooks deterministas introducidos en la suite V3-04 permiten ejecutar o simular flujos tácticos reproducibles de auditoría (como reconocimiento pasivo web, descubrimiento de puertos, análisis SSL/TLS y mapeo de rutas API). Para garantizar la reproducibilidad y el valor pericial de cada intervención, las ejecuciones deben persistirse como evidencia estructurada inmutable dentro del engagement (`evidence/playbooks/<playbook_id>_<timestamp>.json`).

## Cambios Implementados

1. **Motor de Playbooks (`scripts/seclab_playbook.py`)**:
   - `save_playbook_run_evidence(engagement_dir, run_result, parameters)`: Crea de forma atómica y determinista el archivo de evidencia en `evidence/playbooks/<playbook_id>_<timestamp>.json`. Registra versión de esquema `1.0`, tipo de evidencia `playbook_run`, parámetros utilizados, estado, indicador `dry_run` y la lista exhaustiva de pasos ejecutados con salidas y códigos de retorno.
   - `list_playbook_runs(engagement_dir, playbook_id=None)`: Lista de forma segura y cronológica inversa las ejecuciones previas persistidas para el engagement o filtradas por un playbook particular.

2. **Endpoints Backend FastAPI (`dashboard/backend/app/api/endpoints/playbooks.py`)**:
   - Parámetro `save_evidence: bool = True` en `PlaybookRunRequest`.
   - Al ejecutar un playbook con un `engagement_id` válido, se persiste automáticamente la corrida y se retorna `evidence_file` relativo en la respuesta JSON.
   - Nuevo endpoint `GET /api/v1/playbooks/runs/all`: Lista todas las ejecuciones registradas como evidencia para el engagement.
   - Nuevo endpoint `GET /api/v1/playbooks/{playbook_id}/runs`: Lista las ejecuciones registradas para el playbook indicado.

3. **Cliente Frontend (`dashboard/frontend/src/api.js`)**:
   - `api.getPlaybookRuns(id, engagementId, type)`: Consulta reactiva del historial de evidencias.

4. **Interfaz de Usuario Dashboard (`dashboard/frontend/src/views/EngagementDetailView.vue`)**:
   - Alerta reactiva `data-testid="playbook-evidence-file"` en el resumen de ejecución indicando la ruta canónica del archivo de evidencia guardado.
   - Panel «📜 Historial de Evidencias» (`data-testid="playbook-runs-history"`) con listado de ejecuciones pasadas, insignias de estado (`SIMULATED`, `COMPLETED`, `BLOCKED`, `STOPPED`), timestamp y referencia relativa del archivo.

5. **Pruebas y Verificación**:
   - Pruebas unitarias de persistencia y listado en `scripts/verify/test_seclab_playbook.py` (`test_save_playbook_run_evidence`, `test_list_playbook_runs`).
   - Pruebas de integración frontend en Vitest (`dashboard/frontend/tests/playbook-tab.test.js`) validando la carga del historial y visualización del archivo de evidencia.
