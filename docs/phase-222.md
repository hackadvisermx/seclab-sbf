# Fase 222 — Indicador Proactivo de Cobertura de Citas en el Copiloto (V3-05k)

## Contexto y Motivación
En entornos de auditoría estricta y auditorías Evidence-First, las recomendaciones y afirmaciones del Copiloto deben estar directamente ancladas a artefactos y evidencias verificables del workspace (`evidence/*.md`, `target.yaml`, etc.). Cuando el modelo responde con referencias a archivos inexistentes o sin citar fuentes locales, el auditor necesita visibilidad inmediata de la integridad y cobertura de las fuentes citadas.

## Cambios Implementados

1. **Lógica de Evaluación de Cobertura (`dashboard/frontend/src/views/EngagementDetailView.vue`)**:
   - Función auxiliar reactiva `getCitationCoverage(citations)`:
     - Evalúa de forma exhaustiva el número total de citas, cuántas existen (`verified`) y cuántas no se encontraron (`missing`).
     - Determina el estado de cobertura: `full` (100% verificada), `partial` (parcialmente verificada), `unverified` (ninguna fuente encontrada) o `none` (sin citas).
   - Propiedad computada reactiva `copilotSessionCitationStats`:
     - Agrega métricas en tiempo real de toda la conversación de la sesión (total de citas, verificadas, ausentes y porcentaje de cobertura global).

2. **Interfaz de Usuario del Chat**:
   - **Barra Global de Sesión** (`data-testid="copilot-session-citation-stats"`):
     - Muestra el porcentaje de verificabilidad acumulado de toda la conversación en la cabecera del chat con código de colores según madurez (esmeralda, ámbar, rosa).
   - **Insignia Proactiva por Mensaje del Asistente** (`data-testid="copilot-citation-coverage-badge"`):
     - Ubicada en la cabecera de cada respuesta del Copiloto junto al modelo y latencia.
     - Muestra inmediatamente `✓ Citas: 100% verificada (X/X)`, `⚠️ Citas: Y% parcial (X/Z)`, `✗ Citas: 0/X verificadas`, o `ℹ️ Citas: Sin fuentes citadas`.
   - **Desglose en Lista de Citas** (`data-testid="copilot-citations-list"`):
     - Encabezado con contador explícito: `X de Y verificadas en disco`.
   - **Aviso de Contenido No Anclado** (`data-testid="copilot-citation-unanchored-notice"`):
     - Renderiza una alerta sutil y clara cuando una respuesta del asistente no contiene referencias a artefactos locales.

3. **Pruebas y Verificación**:
   - Pruebas frontend en Vitest (`dashboard/frontend/tests/copilot-citations.test.js`):
     - Valida la insignia proactiva de cobertura completa (100% verificada) y la barra de estadísticas de la sesión.
     - Valida la respuesta sin citas con aviso de contenido no anclado (`copilot-citation-unanchored-notice`).
     - Valida la respuesta con citas parciales (50% parcial).
   - 176 pruebas Vitest aprobadas y compilación exitosa de Vite.
