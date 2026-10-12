# Fase 230 — Exportación de Hallazgos en Formato OASIS SARIF v2.1.0 (V3-03dd)

## Contexto y Motivación
La iniciativa V3-03 busca robustecer la interoperabilidad de los entregables de auditoría técnica. Para integrarse con herramientas de análisis de seguridad, plataformas DevSecOps y visores estándar de vulnerabilidades (como GitHub Code Scanning, DefectDojo o Azure DevOps), se requiere la capacidad de exportar las fichas de hallazgo estructuradas en el estándar abierto OASIS Static Analysis Results Interchange Format (SARIF) v2.1.0.

Esta fase implementa la generación determinista de documentos SARIF v2.1.0 a partir de las fichas en `evidence/*.md`, el endpoint backend, el método frontend en `api.js` y el botón de exportación en la pestaña de Hallazgos del dashboard.

## Cambios Implementados

1. **Módulo de Exportación SARIF (`scripts/seclab_sarif.py`)**:
   - `build_findings_sarif(engagement_dir)`: Lee las fichas de hallazgos del engagement y construye un documento JSON conforme a SARIF v2.1.0 (`https://json.schemastore.org/sarif-2.1.0.json`).
   - Mapeo estricto de severidades a niveles SARIF: `critical` y `high` -> `error`, `medium` -> `warning`, `low` e `info` -> `note`.
   - Definición de reglas con metadatos (`id`, `name`, `shortDescription`, `fullDescription`, `help`, `properties.tags`).
   - Mapeo de ubicaciones (`physicalLocation.artifactLocation.uri`) al archivo de evidencia correspondiente.

2. **Backend FastAPI (`dashboard/backend/app/api/endpoints/findings.py`)**:
   - Endpoint `GET /api/v1/findings/{eng_id}/export/sarif` retornando el documento SARIF con cabecera `Content-Disposition: attachment; filename="findings_<eng_id>.sarif.json"`.

3. **Cliente Frontend (`dashboard/frontend/src/api.js`)**:
   - Método `api.exportFindingsSarif(engId)` para descarga directa del archivo `.sarif.json`.

4. **Interfaz Dashboard (`dashboard/frontend/src/views/EngagementDetailView.vue`)**:
   - Botón interactivo «📥 Exportar SARIF v2.1.0» (`data-testid="export-findings-sarif-btn"`) en la barra de acciones de la pestaña Hallazgos.
   - Manejador reactivo `exportSarif()` que dispara la descarga en el navegador con gestión de notificaciones.

5. **Pruebas y Verificación**:
   - Pruebas unitarias Python en host (`scripts/verify/test_seclab_sarif.py`).
   - Pruebas frontend en Vitest (`dashboard/frontend/tests/findings-sarif.test.js`).
   - Suite completa de frontend (183 pruebas aprobadas) y build de producción Vite verificado.
