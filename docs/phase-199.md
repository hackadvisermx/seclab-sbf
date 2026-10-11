# Fase 199: detección y neutralización de contenido hostil y prompt injection en Copiloto

Fecha: 2026-10-11 UTC. Rama `phase/199-copilot-hostile-content`, base `05e3be7`. V3-05g parcial.

## Problema y cambio

Al recopilar contexto para el Copiloto desde evidencias técnicas, salidas de herramientas de auditoría (`nmap`, banners, scripts HTTP, archivos del proyecto), dicho contexto puede contener cargas maliciosas pasivas o activas destinadas a manipular al modelo de lenguaje:
1. Inyecciones indirectas de prompt ("Ignore previous instructions", "system prompt override", instrucciones de suplantación como DAN o Developer Mode).
2. Intentos de rotura o escape de delimitadores de contexto de LLM (`<|im_start|>`, `<|im_end|>`, `[INST]`, `[/INST]`, `<<SYS>>`, `<</SYS>>`, `---BEGIN INSTRUCTION---`), que alteran la estructura del mensaje del proveedor.
3. Cargas de exfiltración o ejecución simulada destinadas a engañar al LLM para que emita respuestas peligrosas.

Anteriormente, el Copiloto incluía el contexto sin analizar ni advertir de la presencia de inyecciones de prompt o delimitadores hostiles, permitiendo que un atacante que controle el banner de un servicio o el contenido de una evidencia manipule las respuestas del asistente.

En esta fase:
1. Módulo de detección y neutralización (`scripts/seclab_hostile.py`):
   - `detect_hostile_content(text)`: Inspecciona el texto contra firmas y patrones de inyección de prompt, evasión de sistema y delimitadores especiales de modelos. Devuelve una lista estructurada de hallazgos con categoría, severidad y fragmento coincidente.
   - `neutralize_hostile_content(text)`: Reemplaza tokens y delimitadores de control de LLM por representaciones neutralizadas seguras (e.g. `[TOKEN NEUTRALIZADO: im_start]`), impidiendo la ruptura de límites de rol en el prompt.
2. Integración en backend de Copiloto (`dashboard/backend/app/api/endpoints/copilot.py` y `core/artifact_snapshot.py`):
   - Los endpoints `GET /copilot/context/{id}` y `POST /copilot/review` analizan el contexto formateado y retornan el campo `hostile_findings`.
   - El endpoint `POST /copilot/chat` aplica `neutralize_hostile_content` sobre el contexto revisado antes de enviarlo al proveedor, y añade instrucciones defensivas para tratar el contexto como datos pasivos de auditoría sin ejecutar comandos incrustados.
3. Generador CLI de contexto (`scripts/pt-agent-context.py`):
   - Neutraliza delimitadores hostiles en la salida de contexto para agentes de línea de comandos.
4. Interfaz de usuario (`dashboard/frontend/src/views/EngagementDetailView.vue`):
   - El modal de revisión de contexto del Copiloto muestra un banner de alerta de seguridad visible cuando se detectan patrones hostiles, indicando el tipo de inyección encontrada y permitiendo al auditor editar o descartar el fragmento antes del envío.
5. Pruebas y verificación:
   - Nuevas pruebas unitarias en `dashboard/backend/tests/test_copilot_hostile.py` y `scripts/verify/check-python-units.py` cubren detección de inyecciones, neutralización de delimitadores, respuestas defensivas de API y rechazo de roturas.

## Verificación y límites

- Pruebas unitarias de Python y backend pasando al 100%.
- Frontend compilado sin errores con suite de pruebas aprobada.
- No garantiza detección del 100% de inyecciones de lenguaje natural altamente ofuscadas o ataques esteganográficos; proporciona capas defensivas deterministas y control humano explícito en el flujo de revisión antes del envío remoto.
