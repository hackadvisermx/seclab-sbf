# Fase 240 — Historial Temporal Longitudinal de Métricas de Madurez de Auditoría

## Resumen Ejecutivo

- **ID de Mejora:** V3-07e (Historial temporal longitudinal de métricas de preparación para auditoría y trazabilidad de avance).
- **Objetivo:** Registrar instantáneas inmutables periódicas o manuales de la puntuación de preparación (`audit_readiness_score`), los 4 pilares operacionales (Alcance, Reconocimiento, Hallazgos y Entregables) y la cobertura de procedencia en `evidence/.metrics_history.jsonl`, visualizando deltas de evolución temporal en el dashboard.
- **Archivos creados:**
  - `scripts/verify/test_seclab_metrics_history.py`: Pruebas unitarias de persistencia, cálculo de deltas cronológicos y recuperación en orden inverso.
  - `dashboard/frontend/tests/metrics-history.test.js`: Pruebas de integración frontend en Vitest para la sección de historial de métricas y captura de instantáneas.
- **Archivos modificados:**
  - `scripts/seclab_metrics.py`: Funciones `record_metrics_snapshot` y `get_metrics_history`.
  - `dashboard/backend/app/services/metrics_service.py`: Métodos `record_snapshot` y `get_history`.
  - `dashboard/backend/app/api/endpoints/engagements.py`: Endpoints `GET /api/v1/engagements/{eng_id}/metrics/history` y `POST /api/v1/engagements/{eng_id}/metrics/snapshot`.
  - `dashboard/frontend/src/api.js`: Funciones `api.getMetricsHistory` y `api.recordMetricsSnapshot`.
  - `dashboard/frontend/src/views/EngagementDetailView.vue`: Sección interactiva `metrics-history-section`, botón `record-metrics-snapshot-btn`, listado cronológico `metrics-history-item` e indicador de delta `metrics-history-delta`.

## Detalles de Implementación

1. **Persistencia Inmutable de Instantáneas (`scripts/seclab_metrics.py`):**
   - Archivo: `evidence/.metrics_history.jsonl` (formato JSON Lines apilable, local y sin dependencias externas).
   - Estructura de cada captura: `snapshot_id`, `timestamp` (UTC ISO 8601), `audit_readiness_score` (0-100), `is_fully_audited`, `pillars` (score y status por disciplina), `total_findings`, `provenance_coverage_pct`, `recon_jobs_completed` y `author`.
   - `get_metrics_history`: Recorre las instantáneas calculando la variación secuencial (`delta_score`: e.g. `+25.0%` o `0.0%`) y devuelve los registros en orden cronológico inverso.

2. **Endpoints Backend (`engagements.py` & `metrics_service.py`):**
   - `GET /api/v1/engagements/{eng_id}/metrics/history`: Consulta el historial de instantáneas del proyecto.
   - `POST /api/v1/engagements/{eng_id}/metrics/snapshot`: Captura el estado actual de métricas y lo agrega al historial.

3. **Interfaz de Usuario Táctica (`EngagementDetailView.vue`):**
   - Sección `metrics-history-section` en la pestaña Métricas con botón «📸 Capturar Snapshot».
   - Renderizado cronológico con insignias coloreadas según ganancia o pérdida porcentual (+% en esmeralda, -% en rojo, 0% en neutro) y desglose de los 4 pilares.

4. **Verificación y Pruebas:**
   - 3 pruebas unitarias en `scripts/verify/test_seclab_metrics_history.py`.
   - 191 pruebas frontend Vitest aprobadas, Vite build exitoso.
   - 304 pruebas de la suite `make verify` aprobadas con 0 fallos ni fugas.
