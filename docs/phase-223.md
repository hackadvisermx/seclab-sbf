# Fase 223 — Conmutación de Redacción de Secretos en el Visor de Artefactos (V3-05l)

## Contexto y Motivación
Durante las auditorías de seguridad, la inspección de artefactos generados (como volcados HTTP de reconocimiento, credenciales encontradas, logs de fuzzing y capturas de cabeceras) expone contraseñas, tokens JWT, Bearer tokens y claves criptográficas. Para permitir revisiones operativas seguras, presentaciones y compartición de pantalla sin filtrar credenciales sensibles, el previsualizador de artefactos debe contar con un mecanismo de enmascaramiento determinista activable bajo demanda.

## Cambios Implementados

1. **Estado Reactivo y Conmutación (`dashboard/frontend/src/views/EngagementDetailView.vue`)**:
   - Variables reactivas: `artifactRedactActive`, `isRedactingArtifact`, `artifactRedactedContent`, `artifactRedactedCount`.
   - Propiedad computada `displayedArtifactContent`: Devuelve el texto enmascarado cuando el modo de redacción está activo o el contenido original en caso contrario.
   - Función `toggleArtifactRedaction()`: Invoca deterministamente `api.autoRedactText` (respaldado por `scripts/seclab_redact.py` en backend), almacena en caché el texto redactado y conmuta la visualización.
   - Restablecimiento automático de estado (`artifactRedactActive = false`) al seleccionar otra carpeta o cargar un nuevo archivo para evitar estados inconsistentes.

2. **Interfaz de Usuario del Previsualizador de Artefactos**:
   - Botón interactivo `data-testid="artifact-redact-toggle"`:
     - Permite alternar entre «🛡️ Redactar Secretos» y «🛡️ Mostrar Original» con estilos tácticos ámbar cuando está activo.
   - Insignia de seguridad `data-testid="artifact-redacted-badge"`:
     - Muestra el número de secretos detectados y enmascarados (e.g. `2 secretos enmascarados`).
   - El elemento `<pre data-testid="artifact-preview-content">` renderiza `displayedArtifactContent`.
   - El botón «Copiar Previsualización» copia la versión actualmente visible (redactada si el modo está activo).

3. **Pruebas y Verificación**:
   - Pruebas frontend dedicadas en Vitest (`dashboard/frontend/tests/artifact-redaction.test.js`):
     - Verifica la visualización inicial de credenciales crudas.
     - Verifica la invocación a `api.autoRedactText` y el cambio a `[REDACTED_BEARER_TOKEN]` y `[REDACTED_PASSWORD]`.
     - Verifica la aparición y texto del badge de secretos enmascarados.
     - Verifica la restauración del texto original al desmarcar el toggle.
   - 177 pruebas en Vitest aprobadas y bundle de Vite compilado sin errores.
