# Fase 203: redacción automática de secretos y datos sensibles en contexto del Copiloto

Fecha: 2026-10-12 UTC. Rama `phase/203-copilot-auto-redaction`, base `dd8c0c9`. V3-05j parcial.

## Problema y cambio

El Copiloto Táctico opera recopilando el contexto vivo del engagement (evidencias, notas, servicios detectados, loot de credenciales) y presentándolo al operador antes de enviarlo a un proveedor de modelo de lenguaje. Conforme al criterio de aceptación V3-05:
1. El contexto extraído puede contener credenciales sensibles, tokens de API, llaves privadas PEM, hashes NTLM/crypt o contraseñas descubiertas durante la auditoría.
2. Si el operador usa un proveedor de LLM remoto o externo (o incluso en un entorno de red privada), estos secretos corren riesgo de exfiltración accidental en el prompt si no se redactan previamente.
3. El operador debía identificar y ofuscar a mano cada secreto antes de enviar la consulta al Copiloto.

En esta fase:
1. Módulo de redacción (`scripts/seclab_redact.py`):
   - `redact_sensitive_text(text, custom_terms=None)`: detecta y enmascara automáticamente patrones sensibles comunes:
     - Claves privadas PEM (`-----BEGIN ... PRIVATE KEY-----` -> `[REDACTED_PRIVATE_KEY]`)
     - Tokens Bearer y JWT (`[REDACTED_BEARER_TOKEN]`, `[REDACTED_JWT_TOKEN]`)
     - Credenciales en URLs (`user:pass@host` -> `[REDACTED_CREDENTIALS]@host`)
     - API Keys comunes (AWS, GitHub, Slack, OpenAI, claves genéricas con prefijo `api_key=...` o `token=...`)
     - Hashes criptográficos (NTLM, MD5, SHA-256, crypt `$1$`, `$6$`)
     - Hashes o credenciales personalizadas extraídas de archivos `loot/credentials.csv` o `loot/credentials.json` mediante `parse_loot_credentials`.
   - Devuelve `text` redactado, conteo de reemplazos `replacements_count`, y lista de categorías enmascaradas `redacted_types`.
2. Integración en `scripts/pt-agent-context.py`:
   - Se añadió el flag `-r` / `--redact` para permitir la redacción automática de secretos al generar el contexto desde la CLI.
   - Detecta automáticamente `loot/credentials.csv` o `credentials.json` en el engagement para añadir contraseñas y hashes de loot a la lista de términos a redactar.
3. Integración en backend (`dashboard/backend/app/api/endpoints/copilot.py` y `artifact_snapshot.py`):
   - Exportación de `redact_sensitive_text` a través del módulo centralizado de snapshots.
   - Nuevo endpoint `POST /api/v1/copilot/redact` que acepta `{ text: string }` y retorna `{ redacted_text, replacements_count, redacted_types }`.
4. Interfaz de usuario (`dashboard/frontend/src/views/EngagementDetailView.vue` y `api.js`):
   - En el modal de revisión previa del Copiloto (`contextReview`), junto al encabezado de "Contexto que se enviará", se añadió el botón interactivo `🛡️ Redactar Secretos` (`data-testid="copilot-auto-redact-btn"`).
   - Al pulsar el botón, llama a la API de redacción y actualiza el área de texto editable con los secretos enmascarados de forma inmediata.
   - Muestra una insignia visual informativa (`data-testid="copilot-redact-badge"`) indicando el número de secretos enmascarados (ej. `3 secretos enmascarados` o `Sin secretos detectados`).
5. Pruebas y verificación:
   - Python unit tests: `scripts/verify/test_seclab_redact.py` con 9 casos de prueba integrados en `check-python-units.py` (266 tests en total).
   - Backend tests: `dashboard/backend/tests/test_copilot_redact.py` para el endpoint HTTP y respuesta de redacción.
   - Frontend tests: `dashboard/frontend/tests/copilot-auto-redact.test.js` para la interacción en el modal, renderizado del botón y actualización del contexto.

## Verificación y límites

- Verificado localmente en suite de pruebas de Python, backend Docker y pruebas de frontend Vitest.
- La redacción automática enmascara patrones sintácticos de alta fidelidad y secretos de loot estructurados. No sustituye la revisión humana obligatoria del contexto antes de su envío a modelos remotos.
