# Fase 213: Historial de revisiones de hallazgos y audit log de evidencias (finding-revisions)

Fecha: 2026-10-12 UTC. Rama `phase/213-finding-revisions`, base `f709b46`. V3-03z parcial.

## Problema y cambio

Conforme a la iniciativa V3-03 de integridad y trazabilidad en el ciclo de vida de evidencias, las modificaciones sobre fichas de hallazgo (`evidence/*.md`) contaban con validación estricta de concurrencia y SHA-256 (`expected_source_sha256`), pero no registraban un rastro de auditoría histórico local accesible e inmutable que documentase qué campos cambiaron, quién realizó la acción (`author`), marcas de tiempo UTC y la evolución de los hashes SHA-256 a lo largo de las distintas versiones. Además, al eliminar una ficha no quedaba constancia auditable del estado en el que se encontraba previamente.

En esta fase:
1. Almacenamiento y registro atómico (`dashboard/backend/app/services/workspace_sync.py`):
   - Cada evento de creación, edición o eliminación de ficha en `evidence/` registra de forma atómica y bajo el mismo flock de escritura un registro estructurado JSON Lines en `evidence/.revisions/<slug>.jsonl`.
   - Campos auditados por revisión:
     - `revision_id`: identificador único de la revisión.
     - `timestamp`: marca de tiempo en estándar ISO 8601 UTC.
     - `action`: tipo de operación (`create`, `update`, `delete`).
     - `slug`, `title`, `severity`, `status`, `author`.
     - `previous_sha256`: hash SHA-256 de la versión anterior (o `None` al crear).
     - `new_sha256`: hash SHA-256 generado de la nueva versión (o `None` al borrar).
     - `modified_fields`: lista ordenada de campos modificados en el payload.
   - `get_finding_revisions(eng_id, slug, eng_type)`: consulta segura con saneamiento contra path traversal que retorna la secuencia cronológica de revisiones.
   - La carpeta `.revisions` queda aislada de la enumeración de fichas (`list_findings`), preservando la compatibilidad completa.
2. Endpoint API Backend (`dashboard/backend/app/api/endpoints/findings.py`):
   - `GET /api/v1/findings/{eng_id}/{slug}/revisions`: expone el historial de revisiones con conteo total.
3. Cliente API Frontend (`dashboard/frontend/src/api.js`):
   - Se añade `api.getFindingRevisions(id, slug, type)`.
4. Interfaz interactiva (`dashboard/frontend/src/views/EngagementDetailView.vue`):
   - Botón «📜 Revisiones» en cada tarjeta de hallazgo (`activeTab === 'findings'`).
   - Modal interactivo de historial de revisiones (`finding-revisions-modal`):
     - Desglose cronológico de cada revisión con insignias de acción (`create`, `update`, `delete`).
     - Metadatos de severidad, estado, autor y fecha UTC.
     - Lista de campos modificados.
     - Hashes criptográficos SHA previo y SHA nuevo para trazabilidad forense.
5. Pruebas y verificación:
   - Suite backend: `dashboard/backend/tests/test_finding_revisions.py` (creación, actualización con seguimiento de SHA, eliminación con preservación de rastro y aislamiento frente a `list_findings`).
   - Suite frontend: `dashboard/frontend/tests/finding-revisions.test.js` (apertura de modal, inspección de eventos y campos modificados).
   - 167 pruebas frontend en `npm test` aprobadas con 0 fallos.
   - Vite build exitoso.

## Verificación y límites

- Backend y frontend probados y verificados.
- 167 pruebas frontend en `npm test` aprobadas.
- Zero egress de red garantizado; los logs residen localmente en el workspace del engagement.
- V3-03z parcial: garantiza la trazabilidad forense de todas las mutaciones sobre fichas de hallazgos; diff visual interactivo línea a línea entre revisiones históricas continúa en el roadmap.
