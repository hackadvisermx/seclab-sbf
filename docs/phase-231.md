# Fase 231 — Resumen Consolidado de Madurez y Postura entre Auditorías (V3-07d)

## Contexto y Motivación
La iniciativa V3-07 requiere métricas operacionales de auditoría con utilidad concreta para el operador y el instructor, basadas en resultados locales sin telemetría externa. Tras implementar las métricas por auditoría individual (V3-07a, V3-07b y V3-07c), se precisaba un resumen cruzado a través de todo el espacio de trabajo (`/workspace`) para visualizar la postura global de auditorías y retos, su puntuación media de madurez, hallazgos agregados y trazabilidad de evidencia.

Esta fase incorpora la agregación determinista cruzada entre auditorías, el endpoint backend, el método de API cliente y la tarjeta táctica de madurez global en la vista principal de proyectos (`EngagementsView.vue`).

## Cambios Implementados

1. **Motor de Métricas Cruzadas (`scripts/seclab_metrics.py`)**:
   - Función `compute_cross_engagement_summary(workspace_dir)`:
     - Escanea los proyectos registrados en `engagements/` y `retos/` (y directorios con `target.yaml`).
     - Agrega estadísticas: total de proyectos, total de auditorías, total de retos, promedio de madurez (`avg_readiness_score`), auditorías completadas (`fully_audited_count`), total de hallazgos (con desglose de confirmados `PROVEN`, candidatos y severidades), cobertura de procedencia global (`overall_provenance_coverage_pct`) y total de corridas de reconocimiento.
     - Funciona localmente de forma determinista y sin egress de datos.

2. **Servicio y Endpoint Backend (`dashboard/backend`)**:
   - `MetricsService.get_cross_engagement_summary()` en `app/services/metrics_service.py`.
   - Endpoint `GET /api/v1/engagements/metrics/summary` en `app/api/endpoints/engagements.py`.

3. **Cliente Frontend (`dashboard/frontend/src/api.js`)**:
   - Método `api.getCrossEngagementMetricsSummary()`.

4. **Interfaz Dashboard (`dashboard/frontend/src/views/EngagementsView.vue`)**:
   - Tarjeta reactiva táctica «📊 Postura & Madurez de Auditoría Global» (`data-testid="cross-engagement-maturity-card"`).
   - Indicadores clave:
     - `avg-readiness-score`: Madurez promedio con barra de progreso estilizada.
     - `total-projects-count`: Conteo desagregado por tipo (auditorías y retos).
     - `total-findings-count`: Hallazgos totales y confirmados `PROVEN` con desglose de severidades críticas y altas.
     - `overall-provenance-pct`: Porcentaje de cobertura de procedencia entre hallazgos y evidencias.
     - `total-recon-jobs`: Historial agregado de corridas de reconocimiento.

5. **Pruebas y Verificación**:
   - Pruebas unitarias Python en host (`scripts/verify/test_seclab_metrics_cross.py`).
   - Pruebas frontend en Node/Vitest (`dashboard/frontend/tests/cross-engagement-maturity.test.js`).
   - Suite completa frontend (184 pruebas aprobadas), Vite build exitoso y suite de seguridad/verificación (`make verify`).
