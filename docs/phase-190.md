# Fase 190: revisión del contexto antes de consultar al Copiloto

Fecha: 2026-10-11 UTC. Rama `phase/190-copilot-context-review`, base `ff83eda`. V3-05e parcial.

## Problema y cambio

El inspector enseñaba el contexto de `pt-agent-context`, pero el botón de consulta generaba otro contexto y lo remitía completo al proveedor sin revisión ni opción de redacción. En la imagen anterior, una petición `/copilot/chat` sin inspección llegaba al proxy y la vista previa no tenía identificador de versión.

Cada consulta abre ahora una vista previa editable. La pregunta y el historial quedan pendientes hasta que el operador confirme el texto que se enviará; puede borrar o sustituir datos. La API exige un token ligado al proyecto, tipo, agente, modelo/perfil y contenido actual. Si cambian los datos entre revisión y envío, responde 409 sin llamar al proveedor; la UI conserva la pregunta para repetir la revisión. El token omite únicamente las dos marcas horarias generadas por cada lectura, porque no representan cambios del proyecto. El texto enviado al proxy es el revisado, no la segunda salida del generador. Se rechaza un texto con NUL o mayor de 256 KiB.

La ventana explica que también se envían pregunta e historial y que un perfil puede usar proveedores del Vault como fallback. La orientación local sigue disponible sin modelo ni envío remoto. La API anterior que enviaba sin revisión recibe 422; los clientes de `/copilot/chat` deben obtener primero `/copilot/context/{id}` y aportar `context_review_token` y `reviewed_context`.

## Verificación y límites

La regresión falla en la imagen de fase188: acepta el chat sin revisión y no emite token. Con el cambio pasan casos de contexto redactado, cambio de contenido/modelo/agente/proyecto, marcas horarias volátiles, tamaño y NUL; ningún rechazo llama al proxy. Un texto de ficha que imita una marca horaria sigue versionado. `make verify` aprobó 244 pruebas Python y linters; 242 backend y 155 frontend; 4 pruebas UI Chromium, captura de la revisión inspeccionada, audit 0, Compose, Actionlint y smoke instalados. Imagen aislada `seclab-sbf:full-phase190` (`sha256:01c0bb37a4564ef1f23535b9e21df220541a658a3f567680940dc760fcacae1c`) con insumos `be09baad68fbd7ee`. Gate High/Critical aprobado; SBOM CycloneDX 1.7 válido, 2251 componentes, SHA-256 `13909854be2b169c9592501f6d9700eedea19e509607bd246ac2898363d34784`. CI del head exacto requerido antes de fusionar.

Esta entrega no identifica de forma verificable si un endpoint `custom_llm` está dentro o fuera de la instancia; el operador debe revisar su Base URL en Vault. Tampoco redacta automáticamente pregunta, historial ni contenido hostil: la revisión es una decisión explícita del operador por consulta. No conserva un historial firmado de consentimiento ni añade fuentes navegables a las respuestas. Laboratorio local detenido, sin publicar imagen ni tocar volúmenes o proyectos.

Integración: [PR #210](https://github.com/hackadvisermx/seclab-sbf/pull/210), head `bf96b4f`, [CI 38158197265](https://github.com/hackadvisermx/seclab-sbf/actions/runs/38158197265) aprobado y merge `138e083` en `bootstrap/baseline`.
