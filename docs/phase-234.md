# Fase 234 — Exportación Estructurada de Transcripciones del Copiloto en Markdown y JSON (V3-05n)

## Contexto y Motivación
La iniciativa V3-05 del Copiloto Táctico establece que las interacciones del operador con el asistente pedagógico deben ser transparentes, auditables y exportables para su inclusión en bitácoras de auditoría, evaluaciones académicas o reportes ejecutivos. Hasta el momento, las interacciones se almacenaban en la base de datos local `copilot_chat_history`, pero no existía un mecanismo para exportar de forma estructurada la conversación completa, incluyendo turnos de preguntas y respuestas, modelos empleados y el desglose de citas/evidencias verificadas asociadas a cada respuesta.

Esta fase implementa el formateador y exportador estructurado en Markdown y JSON (`scripts/seclab_copilot_export.py`), el endpoint backend `GET /api/v1/copilot/chat/export`, el cliente frontend `api.exportCopilotChat` y el botón interactivo «📥 Exportar Chat (.md)» (`data-testid="copilot-chat-export-btn"`) en la barra de herramientas del Copiloto en `EngagementDetailView.vue`.

## Cambios Implementados

1. **Módulo de Exportación (`scripts/seclab_copilot_export.py`)**:
   - `format_copilot_chat_markdown(engagement_id, messages, engagement_type)`: Genera un documento Markdown con encabezados estructurados, metadatos de auditoría, fecha UTC, total de turnos, preguntas en bloque de cita (`> `), respuestas del Copiloto con agente/proveedor/modelo, y sección detallada de fuentes/citas verificadas con su extracto y estado (`Válido` o `No verificado`).
   - `export_copilot_chat(engagement_id, messages, format, engagement_type)`: Serializa en formato JSON estructurado o Markdown, validando que el formato solicitado sea soportado.

2. **Endpoint Backend (`dashboard/backend/app/api/endpoints/copilot.py`)**:
   - `GET /api/v1/copilot/chat/export`: Recupera los mensajes del engagement desde `copilot_chat_history`, re-evalúa y verifica el estado de las citas en disco usando `citations_service.verify_citations`, genera el contenido y responde con encabezados de descarga `Content-Disposition: attachment; filename="copilot_chat_<id>.<ext>"`.

3. **Cliente Frontend (`dashboard/frontend/src/api.js`)**:
   - Método `api.exportCopilotChat(engId, format, type)` para descargar el archivo de transcripción desde el endpoint backend.

4. **Interfaz Dashboard (`dashboard/frontend/src/views/EngagementDetailView.vue`)**:
   - Botón interactivo «📥 Exportar Chat (.md)» con selector reactivo `data-testid="copilot-chat-export-btn"` en la cabecera de la pestaña Copiloto.
   - Manejador reactivo `exportCopilotChat(format)` con gestión de estado (`exportingCopilotChat`) y descarga mediante objeto Blob nativo.

5. **Pruebas y Verificación**:
   - Pruebas unitarias Python en host (`scripts/verify/test_seclab_copilot_export.py`).
   - Pruebas frontend en Vitest/Node (`dashboard/frontend/tests/copilot-chat-export.test.js`).
   - Verificación de suite completa (187 pruebas frontend aprobadas), build exitoso de Vite y suite `make verify`.
