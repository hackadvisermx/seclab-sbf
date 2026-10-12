# Fase 209: Métricas operativas locales de auditoría (seclab_metrics)

Fecha: 2026-10-12 UTC. Rama `phase/209-engagement-metrics`, base `cba1263`. V3-07a parcial.

## Problema y cambio

Conforme a la iniciativa V3-07, el producto requiere trazabilidad y medición cuantitativa de calidad de auditoría sin comprometer la privacidad del engagement ni recurrir a telemetría o servicios externos de analítica:
1. No existía un módulo consolidado que compute métricas de progreso de auditoría a partir del estado real de los artefactos en el workspace.
2. Faltaban indicadores agregados sobre cobertura de procedencia de hallazgos (`provenance_coverage_pct`), desglose de severidades, ratio de confirmación y cumplimiento de alcance (`out_of_scope_actions_executed`).
3. El backend no exponía un endpoint seguro para que la UI o scripts de evaluación consulten estas métricas bajo demanda.

En esta fase:
1. Módulo de métricas operacionales (`scripts/seclab_metrics.py`):
   - `compute_engagement_metrics(engagement_dir)`: analiza de forma estrictamente local y determinista:
     - `scope`: existencia de `target.yaml`, targets autorizados, exclusiones y verificación de 0 acciones fuera de alcance.
     - `recon`: jobs en SQLite (`recon_jobs.db`), etapas completadas y fallidas.
     - `findings`: fichas en `evidence/*.md`, desglose por severidad y estado (`PROVEN`, `CANDIDATE`, `DISPROVED`), y cobertura de procedencia (`source_job_id` + `source_stage`).
     - `report`: presencia de `REPORT.md`, entregables y recuento de artefactos en `artifact-manifest.json`.
     - `audit_readiness_score`: índice de completitud formativa de 0 a 100.
2. Backend y API (`dashboard/backend/app/services/metrics_service.py` y `endpoints/engagements.py`):
   - Servicio `MetricsService.get_metrics(eng_id, eng_type)`.
   - Endpoint `GET /api/v1/engagements/{eng_id}/metrics`.
3. Pruebas y verificación:
   - Nueva suite de pruebas `scripts/verify/test_seclab_metrics.py` integrada en `check-python-units.py` (283 pruebas totales aprobadas).

## Verificación y límites

- 283 pruebas Python en host ejecutadas y aprobadas.
- Zero egress de red garantizado en el cálculo de métricas.
- V3-07a parcial: sienta la base de telemetría y métricas operacionales locales; la visualización gráfica agregada en reportes y dashboard se aborda en fases posteriores.
