# Fase 103 — Catálogo de modelos y reparación del Chat OpenRouter

## Problema comprobado

El historial del laboratorio contenía peticiones a `openrouter` sin clave encontrada y consultas a `custom_llm` que enviaban `llama3:latest` al endpoint de OpenRouter. Su comprobación de salud validaba `/auth/key`, pero el selector del Chat utilizaba presets independientes de la configuración guardada.

La consulta de lectura al catálogo real `/api/v1/models/user` respondió HTTP 200 con 464 modelos de salida de texto; el modelo base guardado no figuraba en esa respuesta. Esta cifra es una observación de esta sesión, no una garantía de catálogo estable. No se enviaron prompts con la clave real ni se cambiaron sus credenciales/modelo.

## Implementación

- `VaultService.get_key_entry("openrouter")` resuelve una clave existente bajo `custom_llm` únicamente si el hostname es exactamente `openrouter.ai` o `eu.openrouter.ai`. No renombra entradas ni confunde una etiqueta «Open Router» de Ollama con OpenRouter. Las claves inactivas no se usan para Chat.
- Normalización común de OpenRouter hacia HTTPS `/api/v1`, incluso con URL de chat completa. Se rechazan hosts engañosos, credenciales en URL y puertos alternativos antes de transmitir la clave.
- `GET /api/v1/vault/{provider}/models` consulta el catálogo con la clave guardada. `POST /api/v1/vault/models/preview` consulta con una clave recién ingresada o la guardada, sin persistir la clave de previsualización. Ambos requieren sesión.
- Chat y configuración muestran el catálogo completo devuelto, con búsqueda por nombre/ID, recarga y errores explícitos. Configuración exige elegir un modelo del catálogo consultado antes de guardar. El modelo base se conserva en `api_keys.model_name`; Chat lo usa al abrir y el Copiloto lo adopta cuando no hay preferencia específica previa.
- Copiloto también sustituye los ocho presets por el catálogo de la cuenta. Se conservan preferencias explícitas previas y perfiles tácticos. Los IDs con `:free` no pierden su sufijo al separar proveedor/modelo.
- Un modelo retirado no se reemplaza silenciosamente por uno de pago. El Chat exige una selección cuando el predeterminado no existe en el catálogo. Los perfiles no envían identificadores de Ollama a OpenRouter.
- Los errores upstream incluyen HTTP y mensaje de rechazo, con la clave redactada; se reconocen errores dentro de HTTP 200 y respuestas sin texto. El cliente HTTP del frontend conserva mensajes no JSON sin leer el cuerpo dos veces.

La lista respeta preferencias, privacidad y guardrails de la cuenta según la [documentación oficial de OpenRouter](https://openrouter.ai/docs/api/api-reference/models/list-models-filtered-by-user-provider-preferences-privacy-settings-and-guardrails). No asegura saldo, cuota ni disponibilidad de inferencia. El selector de Chat permite además introducir manualmente un ID; el upstream decide si lo acepta. Los demás proveedores conservan sus controles existentes.

## Operación

En API Vault, editar la clave existente, pulsar **Consultar modelos con esta clave**, buscar y elegir el **Modelo Inicial / Predeterminado** y guardar. Al crear una clave, consultar el catálogo después de introducirla, antes de confirmar. Abrir Chat para usar el modelo base o elegir otro de la lista. «Online» confirma la clave; el mensaje de salud explica que el modelo se verifica al consultar.

## Validación

- Pruebas de frontend: 29, incluyendo proveedor legado, catálogo sin presets, selección y guardado del modelo base, modelo retirado y errores HTTP no JSON.
- Backend: 83 pruebas sin red, tanto con fuentes montadas como contra la aplicación instalada en la imagen final, incluyendo catálogo de 150 modelos sin truncación, previsualización sin persistencia, hostname exacto, clave inactiva, modelo inválido de Ollama y errores upstream.
- `make verify`: 117 pruebas y gates de lint/secretos/Compose en verde.
- Auditoría npm: 0 vulnerabilidades; build del frontend correcto.
- Validación visual en Chrome con servidor de fixtures exclusivo en `127.0.0.1:18093`: consulta de catálogo de 151 modelos, búsqueda del último modelo, preservación de la selección al filtrar y respuesta del Chat con el modelo base. Capturas locales `tmp/phase103-chat.jpg` y `tmp/phase103-vault.jpg`; el servidor y la pestaña se cerraron.
- Imagen local aislada `seclab-sbf:full-phase103`, construida mediante `make build-full BUILD_TAG=-phase103`. Insumos `a2003ee300d0852b`, imagen local `sha256:d94af7510304f1f70a3b353b0a7252c815c354893af2856f523a79e2e331ee15`. No reemplaza la etiqueta ni el contenedor del laboratorio real.

- Escaneo final `make scan-image SCAN_IMAGE=seclab-sbf:full-phase103`: gate High/Critical en verde con la política existente (`ignore-unfixed` y excepciones vigentes); sin excepciones nuevas. No se añadieron dependencias ni se cambiaron lockfiles.

Trabajo aislado en `/Users/castr/tmp/t01-openrouter`, rama `phase/103-openrouter-model-catalog`, porque el checkout original tenía cambios simultáneos de fase 102. No se publicó ni desplegó una imagen y no se hicieron pruebas sobre UAZ. Merge pendiente de aprobación explícita del owner según `AGENTS.md`.
