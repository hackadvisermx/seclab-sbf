# Fase 208: Componente UI interactivo de Supervisión Pedagógica en Dashboard (SupervisionTab)

Fecha: 2026-10-12 UTC. Rama `phase/208-supervision-ui`, base `c0c0689`. V3-06b parcial.

## Problema y cambio

En la Fase 206 (V3-06a) se introdujo el evaluador desacoplado de auditoría pedagógica (`scripts/seclab_supervision.py`, `supervision_service.py` y `GET /api/v1/engagements/{eng_id}/supervision`). Sin embargo, el operador, supervisor o estudiante en el dashboard aún no disponía de una interfaz visual reactiva para inspeccionar los 4 checkpoints de auditoría, las advertencias del flujo ni las acciones formativas recomendadas.

En esta fase:
1. Cliente API Frontend (`dashboard/frontend/src/api.js`):
   - Se añade `api.getSupervision(id, type)` para consultar el estado formativo y checkpoints pedagógicos del engagement.
2. Vista y Pestaña Táctica (`dashboard/frontend/src/views/EngagementDetailView.vue`):
   - Pestaña «🎓 Supervisión Pedagógica» integrada en el selector de pestañas tácticas del engagement y modo reto.
   - Panel de control de supervisión (`activeTab === 'supervision'`):
     - Insignia reactiva con el estado general (`PASS`, `WARNING`, `BLOCKED`).
     - Cuadrícula de 4 tarjetas de Checkpoint con estilo visual dinámico:
       - `cp_scope`: Alcance Autorizado (target.yaml)
       - `cp_recon`: Reconocimiento Estructurado
       - `cp_evidence`: Evidencia y Trazabilidad de Hallazgos
       - `cp_report`: Integridad de Entregables y Reporte
     - Cada tarjeta muestra nombre, estado, descripción técnica y orientación formativa guiada.
     - Bloques específicos para «⛔ Bloqueos Formativos Detectados», «⚠️ Advertencias Pedagógicas» y «📋 Acciones Pedagógicas Recomendadas».
     - Botón para recargar el estado formativo bajo demanda.
3. Pruebas y verificación:
   - Nueva suite en Node test runner: `dashboard/frontend/tests/supervision-tab.test.js`.
   - 163 pruebas frontend en `npm test` aprobadas con 0 fallos.
   - Compilación exitosa de producción con Vite (`npm run build`).

## Verificación y límites

- 163 pruebas frontend unitarias y de integración pasando.
- Vite build validado sin errores.
- V3-06b parcial: provee la visualización integral y reactiva de checkpoints en el dashboard; validaciones de campo adicionales con instructores continúan en el roadmap formativo.
