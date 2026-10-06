# Fase 100 — Chat IA Táctico con Selector de Modelos OpenRouter y Configuración de Modelo Inicial para Auditorías

Implementación de un centro de chat interactivo directo con modelos de lenguaje de vanguardia ([`ChatView.vue`](file:///Users/castr/tmp/t01/dashboard/frontend/src/views/ChatView.vue)) accesible desde la barra principal ([`Navbar.vue`](file:///Users/castr/tmp/t01/dashboard/frontend/src/components/Navbar.vue) en `/chat`), con selector exhaustivo de modelos OpenRouter (Claude 3.5 Sonnet, DeepSeek V3, DeepSeek R1, Llama 3.3 70B, GPT-4o, etc.), soporte nativo de proveedor OpenRouter en el API Key Vault ([`VaultView.vue`](file:///Users/castr/tmp/t01/dashboard/frontend/src/views/VaultView.vue) y [`vault_service.py`](file:///Users/castr/tmp/t01/dashboard/backend/app/services/vault_service.py)), comprobación de salud y saldo (`/auth/key`), e integración de selección de modelo inicial para el Copiloto Táctico de Auditorías ([`EngagementDetailView.vue`](file:///Users/castr/tmp/t01/dashboard/frontend/src/views/EngagementDetailView.vue) y [`copilot.py`](file:///Users/castr/tmp/t01/dashboard/backend/app/api/endpoints/copilot.py)).

## Diagnóstico y Requisitos

1. **Chat Directo con Modelos (OpenRouter Hub)**:
   - El operador requería una opción en el Dashboard donde poder interactuar directamente con modelos de OpenRouter mediante un selector de modelos interactivo, sin necesidad de estar dentro de un engagement ni recurrir a herramientas externas.
   - Capacidad para elegir entre modelos populares de OpenRouter (`anthropic/claude-3.5-sonnet`, `deepseek/deepseek-chat`, `deepseek/deepseek-r1`, `meta-llama/llama-3.3-70b-instruct`, `meta-llama/llama-3.3-70b-instruct:free`, `openai/gpt-4o`, `openai/gpt-4o-mini`, etc.) o ingresar cualquier slug de modelo personalizado.
   - Ajuste de roles tácticos (Red Team, Triaje Evidence-First, Lógica & APIs, Exploit Dev, General) y control de temperatura de inferencia.

2. **Modelo Inicial para Auditorías**:
   - Una vez registrada la API key de OpenRouter en el Vault, el operador requería poder elegir qué modelo se utilizará de manera inicial en el Copiloto Táctico durante las auditorías, con persistencia y conmutación ágil en la interfaz.

3. **Seguridad y Trazabilidad del Tactical Proxy**:
   - El despacho de peticiones debía enrutarse por el Tactical Proxy Backend (`proxy_service.py`), inyectando cabeceras seguras (`Authorization: Bearer <key>`, `HTTP-Referer`, `X-Title`) y registrando métricas de latencia, tokens y estado en la base de datos `proxy_audit_log` sin exponer la clave al navegador.

## Solución Técnica

1. **Soporte Backend para OpenRouter (`proxy_service.py` & `vault_service.py`)**:
   - **Despacho OpenRouter**: Inclusión de `openrouter` en la rama OpenAI-compatible con endpoint predeterminado `https://openrouter.ai/api/v1/chat/completions`, modelo por defecto `anthropic/claude-3.5-sonnet`, cabeceras `HTTP-Referer: http://localhost:8080` y `X-Title: SecLab Tactical Dashboard`.
   - **Perfiles de Inferencia (`PROFILE_DEFAULTS`)**: Priorización de OpenRouter (`openrouter:deepseek/deepseek-chat` en perfil rápido `quick`, y `openrouter:anthropic/claude-3.5-sonnet` en perfil profundo `deep`).
   - **Resolución Inteligente de Candidatos**: Si se especifica un modelo con formato `proveedor/modelo` (típico de OpenRouter), se enruta prioritariamente a OpenRouter si su clave está activa en el Vault.
   - **Comprobación de Salud del Vault**: Endpoint `https://openrouter.ai/api/v1/auth/key` para validar tokens, reportando saldo consumido, límites configurados y estado en [`vault_service.py`](file:///Users/castr/tmp/t01/dashboard/backend/app/services/vault_service.py).
   - **CLI Tools Bridge**: Mapeo `"openrouter": ["OPENROUTER_API_KEY"]` en [`scripts/pt-vault-bridge.py`](file:///Users/castr/tmp/t01/scripts/pt-vault-bridge.py) para inyección directa en comandos de terminal.

2. **Copiloto Táctico con Selección de Modelo (`copilot.py`)**:
   - Esquema [`CopilotChatRequest`](file:///Users/castr/tmp/t01/dashboard/backend/app/api/endpoints/copilot.py) ampliado con campos opcionales `provider` y `model`.
   - Enrutamiento dinámico hacia el modelo elegido por el operador en lugar de forzar únicamente perfiles genéricos.

3. **Vista de Chat Táctico (`ChatView.vue`)**:
   - Nueva ruta `/chat` registrada en [`router/index.js`](file:///Users/castr/tmp/t01/dashboard/frontend/src/router/index.js).
   - Acceso directo mediante enlace `💬 Chat IA` en [`Navbar.vue`](file:///Users/castr/tmp/t01/dashboard/frontend/src/components/Navbar.vue).
   - Selector interactivo de proveedores (OpenRouter, OpenAI, Anthropic, Gemini, Local) y selector de modelos con presets agrupados (Recomendados, Gratuitos, Especializados, Personalizado).
   - Ajuste de persona técnica, barra de temperatura, telemetría de latencia/tokens por mensaje, copia de respuestas en 1 clic y persistencia del historial en `localStorage`.
   - Botón para definir el modelo activo como el predeterminado global para auditorías futuras (`seclab_default_audit_model`).
   - Detección reactiva de claves LLM en el Vault con banner informativo y acceso directo a `/vault`.

4. **Configuración de OpenRouter en el Vault (`VaultView.vue`)**:
   - Opción `OpenRouter (100+ Modelos: Claude, DeepSeek, Llama)` en el formulario de creación de claves.
   - Pre-llenado automático de `base_url` (`https://openrouter.ai/api/v1`) y selector del modelo inicial predeterminado (`model_name`).
   - Icono distintivo `🔀` para OpenRouter en la grilla del almacén.

5. **Selección de Modelo en Auditorías (`EngagementDetailView.vue`)**:
   - Selector de modelo en la barra del Copiloto Táctico con soporte para modelos de OpenRouter (`openrouter:anthropic/claude-3.5-sonnet`, `openrouter:deepseek/deepseek-chat`, `openrouter:deepseek/deepseek-r1`, `openrouter:meta-llama/llama-3.3-70b-instruct`, etc.) y perfiles clásicos (`quick`, `deep`, `local`).
   - Inicialización automática desde `localStorage` (`seclab_copilot_model_<id>` o `seclab_default_audit_model`) para que la preferencia del operador se aplique de forma consistente en cada auditoría.
   - Despacho de `provider` y `model` hacia el backend en `sendCopilotMessage`.

## Validación y Cobertura

- **Frontend Tests**: 24 pruebas aprobadas (+4 nuevas en [`chat-openrouter.test.js`](file:///Users/castr/tmp/t01/dashboard/frontend/tests/chat-openrouter.test.js)):
  - Enlace táctico a Chat IA en Navbar.
  - Renderizado del selector de modelos OpenRouter y presets populares en ChatView.
  - Despacho de consultas al proxy táctico con proveedor y modelo especificados.
  - Configuración y pre-llenado de OpenRouter en VaultView.
- **Auditoría npm**: 0 vulnerabilidades (`npm run audit`).
- **Compilación Frontend**: Build exitoso en 439ms con Vite (`npm run build`).
- **Backend Tests (`make dashboard-tests`)**: 72 pruebas aprobadas (+4 nuevas en [`test_openrouter_proxy.py`](file:///Users/castr/tmp/t01/dashboard/backend/tests/test_openrouter_proxy.py)):
  - Despacho con cabeceras y modelo de OpenRouter.
  - Enrutamiento automático de slugs con barra hacia OpenRouter cuando la clave está activa.
  - Comprobación de salud del token OpenRouter y formato de saldo.
  - Aceptación y reenvío de `provider` y `model` en el endpoint `/api/v1/copilot/chat`.
- **Regresión Completa (`make verify`)**: 117 pruebas aprobadas (`python_units_check=ok`).
- **Análisis de Secretos (`gitleaks`)**: 0 leaks encontrados (aprobado con 0 alertas).
