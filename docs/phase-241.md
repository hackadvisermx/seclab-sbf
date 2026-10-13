# Fase 241 — Vista Agregada de Supervisión Pedagógica para Cohortes Docentes

## Resumen Ejecutivo

- **ID de Mejora:** V3-06e (Vista agregada de supervisión pedagógica para cohortes docentes y aulas de formación).
- **Objetivo:** Proporcionar al docente o instructor una visión consolidada del avance y los bloqueos formativos a través de todos los proyectos (engagements y retos) de la cohorte, calculando la tasa de cumplimiento global de checkpoints pedagógicos (`cohort_completion_pct`) y el estado individual por proyecto.
- **Archivos creados:**
  - `scripts/verify/test_seclab_cohort_supervision.py`: Pruebas unitarias de agregación de métricas de cohorte, conteo de bloqueos y desglose por checkpoints.
  - `dashboard/frontend/tests/cohort-supervision.test.js`: Pruebas de integración frontend en Vitest para la tarjeta de supervisión de cohorte en la pestaña Supervisión.
- **Archivos modificados:**
  - `scripts/seclab_supervision.py`: Función `compute_cohort_supervision_summary`.
  - `dashboard/backend/app/services/supervision_service.py`: Método `get_cohort_supervision_summary`.
  - `dashboard/backend/app/api/endpoints/engagements.py`: Endpoint `GET /api/v1/engagements/supervision/cohort/summary`.
  - `dashboard/frontend/src/api.js`: Función `api.getCohortSupervisionSummary`.
  - `dashboard/frontend/src/views/EngagementDetailView.vue`: Tarjeta `cohort-supervision-overview-card`, botón `refresh-cohort-supervision-btn`, badge reactivo `cohort-completion-pct` y listado de proyectos `cohort-project-row`.

## Detalles de Implementación

1. **Agregador de Cohorte Docente (`scripts/seclab_supervision.py`):**
   - Función `compute_cohort_supervision_summary`: Explora los directorios `engagements/` y `retos/` en el workspace local.
   - Evalúa cada proyecto mediante `evaluate_supervision_checkpoints`.
   - Métricas agregadas:
     - `total_cohort_projects`: Total de proyectos/alumnos encontrados.
     - `cohort_total_checkpoints`: Cantidad global de checkpoints (`total_cohort_projects * 4`).
     - `cohort_passed_checkpoints`: Checkpoints aprobados acumulados en el aula.
     - `cohort_completion_pct`: Porcentaje de cumplimiento global de la cohorte.
     - `blocked_projects_count`: Alumnos/proyectos con al menos un checkpoint en estado `BLOCKED`.
     - `fully_completed_projects_count`: Proyectos con los 4 checkpoints en `PASSED`.
     - `checkpoint_breakdown`: Estado detallado (`passed`, `blocked`, `in_progress`, `not_started`) para `cp_scope`, `cp_recon`, `cp_evidence` y `cp_report`.

2. **Capa API Backend (`engagements.py` & `supervision_service.py`):**
   - `GET /api/v1/engagements/supervision/cohort/summary`: Retorna el resumen consolidado de la cohorte para el instructor.

3. **Interfaz de Usuario Táctica (`EngagementDetailView.vue`):**
   - Tarjeta `cohort-supervision-overview-card` en la pestaña Supervisión con botón «🔄 Actualizar Cohorte».
   - Indicador visual `cohort-completion-pct` y cuadrícula de estadísticas.
   - Listado reactivo de proyectos con insignia de estado general (`PASS`, `WARNING`, `BLOCKED`, `NOT_STARTED`) y contador de checkpoints completados.

4. **Verificación y Pruebas:**
   - 2 pruebas unitarias en `scripts/verify/test_seclab_cohort_supervision.py`.
   - 192 pruebas frontend Vitest aprobadas, Vite build exitoso.
   - 304 pruebas de la suite local `make verify` aprobadas con 0 fallos ni fugas.
