# Fase 196: revisión de pregunta e historial del Copiloto

Fecha: 2026-10-11 UTC. Rama `phase/196-copilot-transcript-review`, base `e0b15be`. V3-05f parcial.

## Problema y cambio

La fase 190 permitió revisar y redactar el contexto generado, pero el Copiloto seguía enviando la pregunta y el historial de chat sin ofrecer una edición equivalente. El modal advertía que esos mensajes se enviarían, aunque su única caja editable era la del contexto. Una respuesta de error visible también podía reaparecer como historial en la siguiente consulta.

Cada consulta muestra ahora la pregunta y cada mensaje anterior en cajas editables; el operador puede omitir mensajes previos. La revisión local produce un token ligado al proyecto, tipo, agente, modelo/perfil, contexto vigente y transcripción original. Al confirmar, el backend comprueba ese token y entrega al proxy solo los mensajes y el contexto revisados. Una diferencia en la transcripción original o el contexto devuelve 409 sin contactar al proveedor. La conversación visible pasa a reflejar la versión enviada; los mensajes de error del Copiloto se excluyen del próximo envío.

El inspector `GET /copilot/context/{id}` queda para lectura y ya no emite un token de envío. Los clientes deben llamar `POST /copilot/review` con `messages`, luego `POST /copilot/chat` con `source_messages`, `reviewed_messages`, `context_review_token` y `reviewed_context`; el contrato anterior recibe 422. Se rechazan roles distintos de usuario/asistente, mensajes vacíos o con NUL, más de 50 mensajes o más de 128 KiB de transcripción. La pregunta final debe seguir siendo de usuario. El servidor local recibe la transcripción original para validar el token; el proveedor recibe únicamente la versión revisada y las instrucciones fijas del sistema, indicadas en el modal.

## Verificación y límites

La regresión contra la imagen de fase 194 falla porque el endpoint de revisión de transcripción aún no existe. Las pruebas nuevas comprueban redacción de pregunta/historial, omisión de respuestas, bloqueo por cambio del historial original y rechazo del contrato anterior. La prueba de navegador inspecciona el payload de ambas llamadas antes de recibir una respuesta simulada; se inspeccionó la captura del modal.

`scripts/verify/local-pr-gates.sh build` pasó usando la base local verificada `seclab-sbf:base-phase172`, sin Docker Hub ni pushes intermedios: 249 pruebas Python/linters, 245 backend, 156 frontend, 4 UI Chromium, audit 0, smoke instalado, Actionlint, gate CVE High/Critical y SBOM CycloneDX válido. Imagen aislada `seclab-sbf:full-phase196` (`sha256:a195d42b9c400d27bba52c0d884a087a99b3895ee7665f5628168c476b07bedc`), insumos `947709d95daa4db3`, SBOM SHA-256 `9e770b8ad7d97493c68a8f1636b06dfac515415d4057fd96b73644550e99aa83`. CI del head exacto aún requerido antes de fusionar.

Esta entrega no clasifica de manera verificable el destino de un proveedor `custom_llm`, no redacta automáticamente datos y no garantiza que el proveedor obedezca instrucciones. No conserva un registro firmado de revisiones ni incorpora citas navegables. El laboratorio local permanece detenido; no se publican imágenes ni se modifican proyectos o volúmenes.
