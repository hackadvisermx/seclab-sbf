# Fase 201: línea de tiempo unificada cronológica del engagement en backend y visualización en dashboard

Fecha: 2026-10-12 UTC. Rama `phase/201-engagement-timeline`, base `749125e`. V3-02o parcial.

## Problema y cambio

Hasta ahora, los eventos y actividades desarrolladas a lo largo de un engagement o reto CTF (definición y actualizaciones del alcance en `target.yaml`, ejecuciones de pipelines y simulaciones de reconocimiento, revisiones humanas de planes y resultados, hallazgos registrados en `evidence/*.md`, notas tácticas en `notes.md`, compilación del informe final `REPORT.md` y generación de paquetes exportables en `deliverables/`) se encontraban dispersos en diferentes pestañas y herramientas sin una vista agregada cronológica unificada.

Un operador o auditor que deseaba reconstruir la secuencia temporal de acciones, correlacionar la aparición de un hallazgo con la fase de reconocimiento de origen, o auditar el flujo de trabajo completo del proyecto requería consultar manualmente múltiples fuentes independientes.

En esta fase:
1. Esquemas Pydantic (`dashboard/backend/app/models/schemas.py`):
   - Se crearon los esquemas `TimelineEvent` y `EngagementTimelineResponse`, tipificando metadatos estructurados como `category` (`scope`, `recon`, `finding`, `report`, `notes`), `type`, `title`, `status` (`success`, `warning`, `error`, `info`), `summary`, `source_ref` y diccionario de `details`.
2. Servicio unificado de timeline (`dashboard/backend/app/services/timeline_service.py`):
   - Agrega cronológicamente eventos procedentes de:
     - Alcance autorizado (`target.yaml` y su timestamp mtime/revisión).
     - Historial y revisiones de jobs de reconocimiento (`recon_jobs.db`, `recon_job_history`, `recon_job_outcome_reviews`).
     - Fichas de hallazgo (`evidence/*.md` con fecha de frontmatter o mtime de archivo, incluyendo severidad y procedencia `source_job_id`/`source_stage`).
     - Notas del auditor (`notes.md`).
     - Informe compilado (`REPORT.md`).
     - Paquetes y manifiestos de entregables exportados (`deliverables/`).
   - Aplica ordenamiento cronológico unificado descendente (más recientes primero).
3. Endpoint de API (`dashboard/backend/app/api/endpoints/engagements.py`):
   - Endpoint autenticado `GET /api/v1/engagements/{eng_id}/timeline` que admite parámetro `type` (`engagement` o `ctf`) y devuelve la respuesta tipificada.
4. Consumo en frontend (`dashboard/frontend/src/api.js`):
   - Método `getEngagementTimeline(id, type)`.
5. Interfaz de usuario en el Dashboard (`dashboard/frontend/src/views/EngagementDetailView.vue`):
   - Se añadió la pestaña `timeline` ("⏱️ Línea de Tiempo") tanto en el perfil de Engagement como en el de CTF Jeopardy.
   - Componente visual interactivo con línea de tiempo vertical, tarjetas de eventos enriquecidas con insignias de estado y categoría, visualización de metadatos de procedencia y botones de salto directo a la sección correspondiente (ej. ver hallazgo, ver reconocimiento, etc.).
   - Filtro reactivo por categoría (`all`, `scope`, `recon`, `finding`, `notes`, `report`), botón de recarga y manejo de estados vacío/cargando/error.
6. Pruebas y verificación:
   - Backend: `dashboard/backend/tests/test_engagement_timeline.py` (3 pruebas unitarias probando agregación cronológica, metadatos y endpoint HTTP).
   - Frontend: `dashboard/frontend/tests/engagement-timeline.test.js` (2 pruebas validando renderizado, eventos mockeados, filtrado por categorías y estado vacío).

## Verificación y límites

- 263 pruebas de backend ejecutadas dentro del contenedor de pruebas y aprobadas al 100%.
- 257 pruebas de scripts y unidades Python en `make verify` aprobadas.
- 160 pruebas de frontend en Node/Vitest aprobadas.
- Build de producción frontend con Vite generado exitosamente.
- No almacena eventos duplicados en base de datos adicional: se reconstruye de manera determinista a partir de las fuentes de verdad existentes en disco y SQLite para garantizar consistencia absoluta sin desincronización.
