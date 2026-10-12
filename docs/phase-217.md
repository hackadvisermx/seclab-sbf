# Fase 217: Exportación estructurada y filtrado por texto de la Línea de Tiempo del Engagement

Fecha: 2026-10-12 UTC. Rama `phase/217-timeline-export`, base `c1664ab`. V3-02q parcial.

## Problema y cambio

La Fase 201 (V3-02o) introdujo la línea de tiempo unificada cronológica del engagement (`GET /api/v1/engagements/{eng_id}/timeline`), correlacionando eventos de alcance, reconocimiento, hallazgos, notas y reportes.

Sin embargo, el operador no disponía de:
1. Una funcionalidad para exportar este registro cronológico integral a formatos portables (JSON o Markdown) para auditorías externas o bitácoras forenses.
2. Un mecanismo de filtrado reactivo por texto libre para localizar rápidamente eventos específicos por título, resumen o referencia sin depender únicamente de las categorías predefinidas.

En esta fase:
1. Backend (`dashboard/backend`):
   - Método `export_timeline(eng_id, eng_type, format)` en `TimelineService`:
     - Formato `json`: exportación estructurada serializada con indentación.
     - Formato `markdown` (`md`): informe estructurado en Markdown con tabla cronológica de eventos (fecha/hora UTC, categoría, estado, título, resumen y referencia).
   - Endpoint `GET /api/v1/engagements/{eng_id}/timeline/export`:
     - Parámetros: `type` (engagement|reto) y `format` (json|markdown|md).
     - Retorna cabecera `Content-Disposition: attachment; filename="timeline_<eng_id>.<ext>"` con el tipo MIME correspondiente (`application/json` o `text/markdown; charset=utf-8`).
   - Pruebas unitarias de backend en `test_engagement_timeline.py` para ambos formatos y validación de endpoints.
2. Frontend (`dashboard/frontend`):
   - Método `api.exportEngagementTimeline(id, format, type)` en `src/api.js`.
   - Interfaz de usuario en `src/views/EngagementDetailView.vue`:
     - Botones «📥 Markdown» y «📥 JSON» con descarga directa en el navegador.
     - Campo de búsqueda interactivo `data-testid="timeline-search-input"` con botón de limpieza rápida `✕`.
     - Propiedad computada `filteredTimelineEvents` que filtra reactivamente por categoría y consulta de texto.
   - Pruebas unitarias en `tests/engagement-timeline.test.js`:
     - Búsqueda y filtrado en vivo de eventos.
     - Invocación de exportación con formatos correctos.
     - 173 pruebas frontend aprobadas en Vitest. Build de Vite exitoso.

## Verificación y límites

- 298 pruebas Python unitarias aprobadas en host (`check-python-units.py`).
- Pruebas de endpoint y servicio de backend aprobadas en `test_engagement_timeline.py`.
- 173 pruebas frontend unitarias aprobadas (`npm test`).
- Build de producción de Vite limpio.
- V3-02q parcial: exportación estructurada y filtrado reactivo de línea de tiempo del engagement.
