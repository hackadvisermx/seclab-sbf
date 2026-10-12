# Fase 202: citas navegables y fuentes verificables en respuestas del Copiloto

Fecha: 2026-10-12 UTC. Rama `phase/202-copilot-navigable-citations`, base `f5179f8`. V3-05i parcial.

## Problema y cambio

El Copiloto Táctico asiste al auditor formulando respuestas basadas en el contexto vivo del proyecto. Sin embargo, conforme al criterio de aceptación V3-05:
1. Las respuestas generadas por los modelos no incluían fuentes navegables ni citas estructuradas ligadas al workspace: el operador no podía verificar de forma inmediata si un archivo mencionado existía realmente ni contrastar su contenido original.
2. No existía validación de procedencia para contrastar si los artefactos citados por la IA correspondían a evidencias reales del engagement o si eran alucinaciones sintéticas del modelo.
3. Las afirmaciones técnicas requerían verificación manual navegando de pestaña en pestaña en el dashboard.

En esta fase:
1. Servicio de citas (`dashboard/backend/app/services/citations_service.py`):
   - `extract_file_references(text)`: detecta menciones textuales a artefactos conocidos del workspace (`evidence/*.md`, `recon/...`, `loot/...`, `target.yaml`, `notes.md`, `REPORT.md`, `fuzzing/...`, `screenshots/...`).
   - Rechaza URLs externas (`http://`, `https://`) y patrones de directory traversal (`../`).
   - `verify_citations(text, engagement_id, engagement_type)`: valida la existencia de cada archivo en el workspace a través de `workspace_service._resolve_dir`. Si existe, calcula el hash SHA-256 de los bytes actuales y tamaño en disco; si no existe, lo marca con `exists=False`.
2. Integración en el Copiloto (`dashboard/backend/app/api/endpoints/copilot.py` y `schemas.py`):
   - Se crearon los esquemas `CitationItem` y `CopilotCitationVerifyRequest`.
   - Endpoint `POST /api/v1/copilot/citations/verify` para verificación directa de citas en texto.
   - Endpoint `GET /api/v1/copilot/chat/history` para consulta del historial con re-verificación de citas contra el estado actual del workspace.
   - En `copilot_chat`: se inyecta la instrucción de sistema requiriendo citas estructuradas y lenguaje de incertidumbre; la respuesta devuelta por el asistente enriquece el payload con el campo `citations: List[CitationItem]` y se registra en `copilot_chat_history`.
3. Interfaz de usuario (`dashboard/frontend/src/views/EngagementDetailView.vue` y `api.js`):
   - En los mensajes del asistente en la ventana de chat del Copiloto, se renderiza la lista interactiva de fuentes citadas (`[data-testid="copilot-citations-list"]`).
   - Cada cita cuenta con insignia identificadora (`[data-testid="copilot-citation-link"]`), color distintivo según verificación (verde esmeralda si el archivo existe con su hash SHA-256 y tamaño, ámbar si no existe en el workspace).
   - Botón interactivo que al hacer clic navega automáticamente a la pestaña correspondiente (`findings`, `artifacts`, `scope`, `notes`, `report`, `loot`) permitiendo la auditoría inmediata de la fuente.
4. Pruebas y verificación:
   - Backend: `dashboard/backend/tests/test_copilot_citations.py` (extracción, verificación existente/ausente, hashes y endpoint HTTP).
   - Frontend: `dashboard/frontend/tests/copilot-citations.test.js` (renderizado de citas, badges y navegación).

## Verificación y límites

- 266 pruebas backend pasando al 100% en runner Docker.
- 257 pruebas de scripts y linters en `check-python-units.py` pasando al 100%.
- 161 pruebas de frontend en Node/Vitest aprobadas.
- Build de producción Vite completado exitosamente.
- La verificación de citas confirma la existencia y huella criptográfica de los archivos locales en el workspace; no garantiza la validez semántica de la interpretación realizada por el modelo de IA.
