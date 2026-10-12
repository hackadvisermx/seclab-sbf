# Fase 212: Visualización reactiva de Métricas de Auditoría en el Dashboard (MetricsTab)

Fecha: 2026-10-12 UTC. Rama `phase/212-metrics-ui`, base `a8d74f7`. V3-07b parcial.

## Problema y cambio

En la Fase 209 (V3-07a) se diseñó e implementó el motor de métricas operacionales locales (`scripts/seclab_metrics.py`, `metrics_service.py` y `GET /api/v1/engagements/{eng_id}/metrics`), capaz de medir cuantitativamente el progreso y madurez de una auditoría sin telemetría ni llamadas externas. Sin embargo, el dashboard carecía de una pestaña reactiva donde el operador o auditor pudiera inspeccionar visualmente estos indicadores en tiempo real.

En esta fase:
1. Cliente API Frontend (`dashboard/frontend/src/api.js`):
   - Se añaden los métodos `api.getMetrics(id, type)` y `api.getEngagementMetrics(id, type)` para consultar el desglose de métricas operacionales del engagement.
2. Interfaz táctica (`dashboard/frontend/src/views/EngagementDetailView.vue`):
   - Se incorpora la pestaña «📊 Métricas de Auditoría» (`activeTab === 'metrics'`) tanto en modo engagement como reto.
   - Panel de control de métricas operacionales (`engagement-metrics-view`):
     - Insignia de estado e índice general de madurez (`audit_readiness_score` de 0 a 100), coloreada reactivamente según umbrales de auditoría (verde >= 75%, ámbar >= 50%, rojo < 50%).
     - Barra de progreso interactiva con 4 pilares formativos: Alcance (+25), Reconocimiento (+25), Hallazgos (+25), Reporte (+25).
     - Cuadrícula de 4 tarjetas tácticas especializadas:
       - **Alcance y Límites (`metrics-card-scope`)**: estado de `target.yaml`, conteo de dominios, IPs/CIDRs, exclusiones, 0 violaciones fuera de alcance y permisos vigentes (pasivo/activo).
       - **Pipeline de Reconocimiento (`metrics-card-recon`)**: estado de `recon_jobs.db`, jobs totales, completados, fallidos y etapas cubiertas.
       - **Hallazgos & Trazabilidad (`metrics-card-findings`)**: conteo por estado (`PROVEN`, `CANDIDATE`, `DISPROVED`), insignia y porcentaje de cobertura de procedencia (`provenance_coverage_pct`), y desglose visual por severidad (crítica, alta, media, baja, informativa).
       - **Entregables y Manifiesto (`metrics-card-report`)**: presencia y tamaño de `REPORT.md`, disponibilidad de `deliverables/`, estado de `artifact-manifest.json` y conteo de artefactos registrados.
     - Botón para recargar y sincronizar métricas bajo demanda.
3. Pruebas y verificación:
   - Nueva suite en Node test runner: `dashboard/frontend/tests/metrics-tab.test.js`.
   - 166 pruebas frontend en `npm test` aprobadas con 0 fallos.
   - Compilación exitosa de producción con Vite (`npm run build`).

## Verificación y límites

- 166 pruebas frontend unitarias y de integración pasando.
- Vite build validado sin errores.
- 293 pruebas Python en host previamente verificadas.
- Zero egress de red garantizado.
- V3-07b parcial: provee la superficie interactiva completa en dashboard para monitorear métricas operacionales de auditoría; exportación gráfica de métricas en formato PDF/JSON para informes ejecutivos continúa en el roadmap de entregables.
