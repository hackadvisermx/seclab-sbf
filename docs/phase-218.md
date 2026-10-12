# Fase 218: Comparador visual de versiones e inspección de diferencias en Revisiones de Hallazgos

Fecha: 2026-10-12 UTC. Rama `phase/218-finding-revisions-diff`, base `78c41d1`. V3-03bb parcial.

## Problema y cambio

La Fase 213 (V3-03z) introdujo el registro de auditoría inmutable de revisiones de hallazgos (`evidence/.revisions/<slug>.jsonl`), exponiendo metadatos esenciales como acción, autor, timestamps y hashes SHA-256.

Sin embargo, el modal de revisiones en el dashboard (`finding-revisions-modal`) no proporcionaba:
1. Registro detallado de diferencias por campo (`field_diffs`) con valores previos y nuevos.
2. Un comparador visual interactivo entre cualquier par de versiones (Versión Base A vs Versión Comparada B).
3. Visualización clara e intuitiva de adiciones y supresiones (resaltado en verde y rojo/tachado).

En esta fase:
1. Backend (`dashboard/backend`):
   - En `workspace_sync.py` (`update_finding` y `create_finding`):
     - Registro atómico de `field_diffs` en cada entrada de `.revisions/<slug>.jsonl`.
     - Identificación precisa de campos modificados con par de valores `old` y `new`.
   - Pruebas unitarias en `test_finding_revisions.py` verificando captura de `field_diffs` al actualizar hallazgos.
2. Frontend (`dashboard/frontend`):
   - En `EngagementDetailView.vue`:
     - Barra de herramientas con botón `data-testid="toggle-comparator-btn"` («⚖️ Comparar Versiones»).
     - Panel del comparador visual `data-testid="revision-comparator-panel"` con selectores reactivos para Versión A y Versión B.
     - Vista de diferencias `data-testid="revisions-diff-view"` detallando campos modificados con insignias rojas (valor anterior tachado) y verdes (nuevo valor).
     - Tarjetas de revisión enriquecidas con bloque `data-testid="revision-field-diffs"` para cambios detallados inline y botón «⚖️ Comparar con versión anterior».
   - Pruebas unitarias en `tests/finding-revisions.test.js`:
     - Validación de renderizado de `revision-field-diffs`.
     - Alternancia y visualización del comparador `revisions-diff-view`.
     - 174 pruebas frontend aprobadas en Vitest. Build de Vite exitoso.

## Verificación y límites

- 298 pruebas Python unitarias aprobadas en host.
- Pruebas de backend en `test_finding_revisions.py` aprobadas.
- 174 pruebas frontend aprobadas en Vitest.
- Build de producción Vite completado limpiamente.
- V3-03bb parcial: comparador visual interactivo de revisiones y diff detallado por campo en fichas de hallazgos.
