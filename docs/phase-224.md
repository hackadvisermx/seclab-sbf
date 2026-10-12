# Fase 224 — Exportación de Informe de Supervisión Pedagógica (V3-06c)

## Contexto y Motivación
La supervisión pedagógica continua (V3-06a/b) evalúa de forma determinista 4 checkpoints clave de la auditoría: alcance (`cp_scope`), reconocimiento (`cp_recon`), evidencia de hallazgos (`cp_evidence`) e informe final (`cp_report`). Para fines de evaluación docente, archivo pericial y reporte de progreso sin conexión, se requiere la capacidad de exportar el estado de supervisión en formatos universales estructurados (JSON) y legibles (Markdown).

## Cambios Implementados

1. **Módulo de Supervisión (`scripts/seclab_supervision.py`)**:
   - `export_supervision_markdown(state)`: Función pura que genera un documento Markdown estructurado con tablas de checkpoints, resumen operacional por disciplina y estado de la etapa actual.
   - `export_supervision_report(engagement_dir, format="json")`: Soporta formatos `json` y `markdown`, validando el formato solicitado sin dependencias externas.

2. **Servicio Backend (`dashboard/backend/app/services/supervision_service.py`)**:
   - `export_supervision_report(eng_id, eng_type="engagement", format="json")`: Genera el reporte exportable a partir del estado consolidado de la auditoría.

3. **Endpoint FastAPI (`dashboard/backend/app/api/endpoints/engagements.py`)**:
   - `GET /api/v1/engagements/{eng_id}/supervision/export`:
     - Parámetros: `format` (`json` o `markdown`), `type` (`engagement` o `reto`).
     - Cabecera `Content-Disposition: attachment; filename="supervision_{eng_id}.{ext}"` y tipos MIME correctos (`application/json` y `text/markdown`).

4. **Cliente Frontend (`dashboard/frontend/src/api.js`)**:
   - Método `api.exportSupervision(id, format, type)` para la descarga directa desde el navegador.

5. **Interfaz Dashboard (`dashboard/frontend/src/views/EngagementDetailView.vue`)**:
   - Botones tácticos «📥 Markdown» (`data-testid="supervision-export-md-button"`) y «📥 JSON» (`data-testid="supervision-export-json-button"`) en la cabecera de la pestaña «🎓 Supervisión Pedagógica».
   - Descarga interactiva vía Blob y enlaces temporales.

6. **Pruebas y Verificación**:
   - Pruebas unitarias de exportación en host (`scripts/verify/test_supervision_checkpoints.py`).
   - Pruebas de integración de servicio y endpoint FastAPI (`dashboard/backend/tests/test_supervision_service.py`).
   - Pruebas frontend en Vitest (`dashboard/frontend/tests/supervision-tab.test.js`).
