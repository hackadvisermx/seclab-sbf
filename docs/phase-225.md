# Fase 225 — Exportación de Métricas Operacionales de Auditoría (V3-07c)

## Contexto y Motivación
El motor de métricas operacionales locales (V3-07a/b) calcula cuantitativamente el índice de madurez de auditoría (`audit_readiness_score`, 0-100%) y agrega trazabilidad en 4 pilares: alcance, reconocimiento, hallazgos (con procedencia vinculada) y reporte/entregables. Para fines de auditoría forense, evaluación de avance entre sesiones y reporte técnico determinista sin telemetría ni conexión externa, se requiere exportar estas métricas operacionales en formatos estructurados estándar (JSON) y legibles (Markdown).

## Cambios Implementados

1. **Módulo de Métricas (`scripts/seclab_metrics.py`)**:
   - `export_metrics_markdown(metrics)`: Función pura que genera un documento Markdown estructurado con la puntuación de madurez, desglose detallado de los 4 pilares (alcance, recon, hallazgos con porcentajes de procedencia y severidades, reporte y artefactos).
   - `export_metrics_report(engagement_dir, format="json")`: Soporta formatos `json` y `markdown`, validando el formato solicitado sin egress de red ni dependencias pesadas.

2. **Servicio Backend (`dashboard/backend/app/services/metrics_service.py`)**:
   - `export_metrics_report(eng_id, eng_type="engagement", format="json")`: Genera el reporte exportable a partir de los datos calculados para el engagement o reto.

3. **Endpoint FastAPI (`dashboard/backend/app/api/endpoints/engagements.py`)**:
   - `GET /api/v1/engagements/{eng_id}/metrics/export`:
     - Parámetros: `format` (`json` o `markdown`), `type` (`engagement` o `reto`).
     - Cabecera `Content-Disposition: attachment; filename="metrics_{eng_id}.{ext}"` y tipos MIME adecuados (`application/json` y `text/markdown; charset=utf-8`).

4. **Cliente Frontend (`dashboard/frontend/src/api.js`)**:
   - Método reactivo `api.exportMetrics(id, format, type)` para la descarga directa desde el navegador.

5. **Interfaz Dashboard (`dashboard/frontend/src/views/EngagementDetailView.vue`)**:
   - Botones tácticos «📥 Markdown» (`data-testid="metrics-export-md-button"`) y «📥 JSON» (`data-testid="metrics-export-json-button"`) en la cabecera de la pestaña «📊 Métricas de Auditoría».
   - Descarga interactiva reactiva vía Blob y enlaces transitorios.

6. **Pruebas y Verificación**:
   - Pruebas unitarias de exportación en host (`scripts/verify/test_seclab_metrics.py`).
   - Pruebas de integración de servicio y endpoint FastAPI (`dashboard/backend/tests/test_metrics_service.py`).
   - Pruebas frontend en Vitest (`dashboard/frontend/tests/metrics-tab.test.js`).
