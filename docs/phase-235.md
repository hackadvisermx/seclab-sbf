# Fase 235 — Grafo Estructurado de Procedencia y Trazabilidad de Auditoría (V3-02s)

## Contexto y Motivación
La iniciativa V3-02 sobre trazabilidad y supervisión operacional establece que la auditoría debe garantizar una cadena de custodia técnica verificable desde el alcance hasta los entregables. Hasta ahora, el sistema disponía de una línea de tiempo cronológica lineal (`timeline_service.py`) y métricas cuantitativas (`metrics_service.py`), pero carecía de una estructura formal de grafo acíclico dirigido (DAG) que correlacione explícitamente:
1. Nodos de Alcance (`target.yaml`): activos y dominios/IPs autorizados.
2. Nodos de Ejecución (`recon_jobs.db`): herramientas y escaneos lanzados contra el objetivo.
3. Nodos de Hallazgo (`evidence/*.md`): vulnerabilidades identificadas con metadatos de procedencia (`source_job_id`).
4. Nodos de Entregables (`REPORT.md`, `artifact-manifest.json`): reporte técnico compilado y manifiesto de artefactos sellado con hashes criptográficos.

Esta fase implementa el motor de grafo dirigido de procedencia (`scripts/seclab_provenance.py`), el servicio backend (`provenance_service.py`), los endpoints `GET /api/v1/engagements/{eng_id}/provenance/graph` y `GET /api/v1/engagements/{eng_id}/provenance/export`, el cliente frontend (`api.getProvenanceGraph`, `api.exportProvenanceGraph`) y la tarjeta interactiva de flujo visual (`data-testid="provenance-flow-graph"`) en la pestaña Línea de Tiempo del dashboard (`EngagementDetailView.vue`).

## Cambios Implementados

1. **Módulo de Grafo de Procedencia (`scripts/seclab_provenance.py`)**:
   - `build_provenance_graph(engagement_dir)`: Construye el DAG correlacionando alcance, jobs, evidencias y entregables, identificando hallazgos con job vs manuales y calculando cadenas completas (Scope ➔ Job ➔ Finding ➔ Report).
   - `export_provenance_graph_mermaid(graph)`: Genera diagramas de flujo interactivos Mermaid (`flowchart LR`) con subgrafos agrupados por pilar.
   - `export_provenance_graph_markdown(graph)`: Genera informes en Markdown con resumen ejecutivo y diagrama Mermaid.
   - Soporta ejecución CLI (`python3 scripts/seclab_provenance.py <dir> --format json|mermaid|markdown`).

2. **Servicio y Endpoints Backend (`dashboard/backend`)**:
   - `ProvenanceService` en `dashboard/backend/app/services/provenance_service.py`.
   - `GET /api/v1/engagements/{eng_id}/provenance/graph` en `app/api/endpoints/engagements.py`.
   - `GET /api/v1/engagements/{eng_id}/provenance/export` con soporte para formatos JSON, Mermaid (`.mmd`) y Markdown (`.md`).

3. **Cliente Frontend (`dashboard/frontend/src/api.js`)**:
   - Métodos `api.getProvenanceGraph` y `api.exportProvenanceGraph`.

4. **Interfaz Dashboard (`dashboard/frontend/src/views/EngagementDetailView.vue`)**:
   - Componente táctico `provenance-flow-graph` en la cabecera de la pestaña Línea de Tiempo.
   - Métricas reactivas: Total de Nodos, Total de Aristas, Cobertura de Procedencia (`provenance-coverage-badge`) y Cadenas Completas (`provenance-chains-badge`).
   - 4 columnas visuales de flujo: Alcance, Jobs/Escaneos, Hallazgos y Entregables.
   - Botones de exportación rápida a Mermaid (`.mmd`) y JSON.

5. **Pruebas y Verificación**:
   - Pruebas unitarias Python en host (`scripts/verify/test_seclab_provenance_graph.py`).
   - Pruebas frontend en Vitest/Node (`dashboard/frontend/tests/provenance-graph.test.js`).
   - 188 pruebas frontend de Vitest/Node aprobadas.
   - Build de producción Vite sin errores.
   - Suite `make verify` (304 pruebas Python en host, flake8, gitleaks) aprobada.
