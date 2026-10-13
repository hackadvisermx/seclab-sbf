# Fase 242 — Harness de Integración de Modelos Locales (Ollama / vLLM) con Fallback Determinista y Cero Pérdida de Estado

## Resumen Ejecutivo

- **ID de Mejora:** V3-05o (Harness de integración con modelos locales Ollama/vLLM, sondeo de salud con timeout estricto, fallback determinista y cero pérdida de estado).
- **Objetivo:** Garantizar la continuidad operativa del Copiloto Táctico en entornos locales y air-gapped cuando el proveedor local (Ollama o vLLM) no está disponible o falla su socket, degradando de manera transparente a orientación técnica heurística y determinista basada en el alcance y evidencias del proyecto, sin perder el estado de la sesión, los mensajes del usuario ni las citas navegables.
- **Archivos creados:**
  - `scripts/seclab_copilot_harness.py`: Módulo con funciones `probe_local_provider` (sondeo con socket timeout de 2.0s y catálogo de modelos) y `generate_heuristic_fallback` (motor heurístico de orientación contextual).
  - `scripts/verify/test_copilot_local_harness.py`: Pruebas unitarias de sondeo online/offline, parseo de modelos Ollama/vLLM y generación heurística adaptada por especialidad.
  - `dashboard/frontend/tests/copilot-local-harness.test.js`: Pruebas de integración frontend en Vitest para el botón de comprobación de salud y la insignia interactiva de estado.
- **Archivos modificados:**
  - `dashboard/backend/app/api/endpoints/copilot.py`: Nuevo endpoint `GET /api/v1/copilot/providers/health` y manejo de degradación determinista con cero pérdida de estado en `copilot_chat`.
  - `dashboard/frontend/src/api.js`: Nuevo método `api.getCopilotProviderHealth`.
  - `dashboard/frontend/src/views/EngagementDetailView.vue`: Botón interactivo `check-provider-health-btn`, indicador reactivo `copilot-provider-health-pill` e insignia `copilot-fallback-active-badge` en mensajes degradados.
  - `scripts/verify/check-python-units.py`: Integración de `test_copilot_local_harness` en la suite de verificación.

## Detalles de Implementación

1. **Sondeo de Salud No Bloqueante (`scripts/seclab_copilot_harness.py`):**
   - Función `probe_local_provider(base_url, timeout_seconds=2.0)`:
     - Normaliza el endpoint a un esquema HTTP/HTTPS limpio.
     - Aplica un timeout estricto de 2.0 segundos para evitar bloqueos del hilo en caso de demonio caído.
     - Inspecciona rutas de Ollama (`/api/tags`, `/api/version`) y de vLLM/OpenAI (`/v1/models`, `/models`).
     - Extrae lista de modelos instalados y calcula la latencia en milisegundos.
     - Retorna `status: ONLINE` o `status: OFFLINE` con el error capturado sin levantar excepciones 500/502.

2. **Motor de Fallback Heurístico con Cero Pérdida de Estado:**
   - Función `generate_heuristic_fallback(engagement_dir, agent_id, user_message)`:
     - Extrae el alcance activo desde `target.yaml` o `scope.txt`.
     - Enumera fichas de hallazgos en `evidence/`.
     - Genera recomendaciones metodológicas específicas según la especialidad del agente (`recon-agent`, `triage-agent`, `auth-agent`, `logic-agent`, `injection-agent`, `report-agent`).
     - Incluye encabezado estructurado `ℹ️ [Modo Degradación Determinista Local: Proveedor sin conexión — Respuesta heurística generada sin pérdida de estado]`.
     - Incorpora citas navegables (`[ref:scope:target.yaml]`, `[ref:evidence:...]`) y notas explícitas de incertidumbre técnica.
   - En `copilot.py` (`copilot_chat`):
     - Ante fallos de conexión o timeouts hacia proveedores locales, se activa automáticamente la degradación determinista.
     - Se valida el alcance con Scope Guard, se verifican las citas contra el workspace vivo y se persiste el turno en `copilot_chat_history`, preservando intacto el flujo del operador.

3. **Capa API Backend (`copilot.py`):**
   - `GET /api/v1/copilot/providers/health?provider=custom_llm`:
     - Consulta la configuración activa en el Vault y ejecuta el sondeo en tiempo real.

4. **Interfaz de Usuario Táctica (`EngagementDetailView.vue`):**
   - Botón `check-provider-health-btn` («🔌 Estado Local») en la barra de herramientas del Copiloto.
   - Píldora de estado `copilot-provider-health-pill` con latencia y modelo detectado (o indicador offline).
   - Insignia `copilot-fallback-active-badge` («⚡ Fallback Heurístico Local») en mensajes generados bajo degradación.

5. **Verificación y Pruebas:**
   - 5 pruebas unitarias en `scripts/verify/test_copilot_local_harness.py`.
   - 193 pruebas frontend Vitest aprobadas, Vite build exitoso.
   - 309 pruebas unitarias de la suite local `make verify` aprobadas con 0 fallos.
