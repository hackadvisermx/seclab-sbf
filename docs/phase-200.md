# Fase 200: clasificación verificable y advertencias de seguridad para destinos de proveedor custom_llm

Fecha: 2026-10-11 UTC. Rama `phase/200-custom-llm-destination`, base `17ac4ab`. V3-05h parcial.

## Problema y cambio

El Copiloto Táctico y el Vault de credenciales permiten registrar proveedores LLM personalizados (`custom_llm`) mediante una URL base (`base_url`). Sin embargo:
1. No existía una clasificación verificable del destino de red: los operadores no podían determinar si el procesamiento se realizaría en un endpoint local (loopback), en un segmento de red interna/privada o en un servidor público en internet.
2. El perfil `local` del Copiloto —cuyo objetivo de seguridad es evitar que el contexto sensible del engagement salga de la máquina del auditor— solo verificaba que la clave no fuera de OpenRouter, pero no validaba si `base_url` apuntaba a una IP pública o dominio remoto de internet. Un operador podía asumir que estaba utilizando inferencia local privada cuando en realidad los datos se enviaban a un servidor remoto.
3. El uso de protocolos sin cifrar (`http://`) en destinos remotos públicos no era señalado ni advertido, exponiendo el contexto del engagement, notas técnicas y API keys a intercepción en tránsito (texto claro).
4. El modal de revisión previa del Copiloto y la vista del Vault no exponían el destino del modelo antes de autorizar el envío.

En esta fase:
1. Módulo de clasificación de red (`scripts/seclab_network.py`):
   - `classify_endpoint(url)`: analiza el hostname e IP del endpoint utilizando `ipaddress` y `urllib.parse`. Clasifica en:
     - `LOCAL_LOOPBACK`: `127.0.0.0/8`, `::1`, `localhost`, `*.localhost`, `0.0.0.0`.
     - `PRIVATE_NETWORK`: RFC 1918 (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`), link-local (`169.254.0.0/16`), ULA IPv6 (`fc00::/7`), dominios mDNS/internos (`.local`, `.internal`, `.lan`, `.home.arpa`) y endpoints Docker (`host.docker.internal`).
     - `PUBLIC_REMOTE`: dominios o direcciones IP públicamente enrutables.
   - Evalúa `is_insecure_transport` y emite `transport_warning` ante el uso de `http://` en destinos remotos públicos o redes no cifradas.
2. Enforzamiento de límite local en `proxy_service.py`:
   - En consultas con perfil `profile="local"`, el enrutador valida que el destino no sea `PUBLIC_REMOTE`. Cualquier intento de enviar contexto a un servidor remoto público bajo el perfil local es rechazado de inmediato con `ValueError` sin contactar al upstream.
3. Metadatos en Vault y esquemas (`schemas.py` y `vault_service.py`):
   - `ApiKeyResponse` incorpora `destination_classification`, `is_insecure_transport` y `transport_warning`.
   - `list_keys()` y `get_response_by_provider()` calculan e informan la clasificación para todos los proveedores registrados o por defecto.
4. Integración en el Copiloto (`copilot.py`):
   - `GET /copilot/context/{id}` y `POST /copilot/review` retornan el objeto `destination` con la clasificación de red y avisos de transporte.
5. Interfaz de usuario (`VaultView.vue` y `EngagementDetailView.vue`):
   - Las tarjetas del Vault muestran insignias identificadoras (`Local`, `Red Privada`, `Remoto Público`) y una alerta visible ante transporte HTTP sin cifrar.
   - El modal de revisión de contexto del Copiloto incluye un bloque de información del destino que indica si los datos saldrán a internet público o permanecerán en el entorno local, junto con advertencias de transporte si aplica.
6. Pruebas y verificación:
   - Nuevas pruebas en `dashboard/backend/tests/test_custom_llm_destination.py`, `scripts/verify/check-python-units.py` y `dashboard/frontend/tests/custom-llm-destination.test.js`.

## Verificación y límites

- 257 pruebas unitarias de Python y backend pasando al 100%.
- 158 pruebas de frontend en vitest aprobadas.
- Clasifica según resolución sintáctica de IP y dominios estándar; no resuelve DNS en caliente durante la comprobación estática para evitar fugas de consultas o bloqueos por latencia de red.
