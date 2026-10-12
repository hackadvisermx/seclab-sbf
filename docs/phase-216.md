# Fase 216: Franja de siguiente decisión táctica y navegación unificada en Dashboard

Fecha: 2026-10-12 UTC. Rama `phase/216-audit-next-banner`, base `b34414b`. V3-02p parcial.

## Problema y cambio

El dashboard disponía de recomendaciones tácticas y de estado de siguiente paso en los paneles de Reconocimiento y Resumen, pero el operador debía navegar hacia esas pestañas para conocer qué acción estratégica seguir en el ciclo de auditoría. Además, el manejador `openNextDecision` solo admitía transiciones hacia las vistas `scope` y `recon`, ignorando recomendaciones hacia `findings`, `evidence`, `report`, `checklist`, `playbooks` o `metrics`.

En esta fase:
1. Interfaz de usuario en `dashboard/frontend/src/views/EngagementDetailView.vue`:
   - Franja táctica prominente `data-testid="audit-next-banner"` ubicada sobre la barra de navegación de pestañas.
   - Presenta la fase del ciclo (`next_step.phase`), el título descriptivo de la acción recomendada y un botón de navegación directa.
   - Botón de refresco manual `🔄` para actualizar la decisión en tiempo real invocando `loadNextStep()`.
   - Expansión de `openNextDecision` para enrutar de forma reactiva a todas las vistas pertinentes: `scope`, `recon`, `findings`/`evidence`, `report`, `checklist`, `playbooks` y `metrics`.
2. Pruebas y verificación:
   - Suite unitaria en `dashboard/frontend/tests/audit-next-banner.test.js`:
     - Renderizado de la franja con título y fase.
     - Navegación reactiva al hacer clic en el botón de acción hacia la pestaña correspondiente (`findings`, etc.).
   - 171 pruebas frontend unitarias ejecutadas y aprobadas en Vitest.
   - Build de producción Vite completado exitosamente.

## Verificación y límites

- 171 pruebas frontend aprobadas (`npm test`).
- 298 pruebas Python unitarias aprobadas en host.
- Build de producción de Vite limpio sin errores.
- V3-02p parcial: franja accesible y navegación unificada hacia la siguiente decisión táctica del ciclo de auditoría.
