# Fase 227 — Registro Inmutable de Consentimiento y Auditoría del Copiloto (V3-05m)

## Contexto y Motivación
El criterio de aceptación de la iniciativa V3-05 establece que el Copiloto no debe enviar telemetría ni datos del proyecto sin el consentimiento explícito y rastreable del auditor. Cada interacción con modelos externos o locales debe generar un registro inmutable de auditoría que garantice la no repudiación, verificabilidad y transparencia del intercambio de información:
> «Cada consulta al modelo registra de forma inmutable el hash SHA-256 del prompt, del contexto revisado, la clasificación del destino de red (LOCAL_LOOPBACK, PRIVATE_NETWORK, PUBLIC_REMOTE) y el token de revisión.»

Esta fase implementa el registro atómico y persistente de consentimiento en `evidence/.copilot_consent.jsonl`, su consulta estructurada vía API y la visualización interactiva del historial de auditoría de consentimientos en el dashboard.

## Cambios Implementados

1. **Módulo de Auditoría del Copiloto (`scripts/seclab_copilot_audit.py`)**:
   - `log_copilot_consent(...)`: Registra atómicamente en `evidence/.copilot_consent.jsonl` la marca de tiempo UTC, `engagement_id`, `agent_id`, `provider`, `model`, `network_tier`, `prompt_hash`, `context_hash`, `context_bytes`, `token` y estado `consented`.
   - `read_copilot_consent_history(...)`: Lee en orden cronológico inverso las entradas auditadas con límite configurable.

2. **Backend FastAPI (`dashboard/backend/app/api/endpoints/copilot.py`)**:
   - Inyección de registro de consentimiento en `POST /api/v1/copilot/chat` previo a la llamada a inferencia.
   - Endpoint `GET /api/v1/copilot/consent/history` para consulta paginada del historial de consentimientos del engagement.

3. **Cliente Frontend (`dashboard/frontend/src/api.js`)**:
   - Método `api.getCopilotConsentHistory(engId, type, limit)`.

4. **Interfaz Dashboard (`dashboard/frontend/src/views/EngagementDetailView.vue`)**:
   - Indicador y aviso de auditoría activa (`data-testid="copilot-consent-notice"`) en el modal de revisión de contexto.
   - Botón «📜 Log Consentimiento» (`data-testid="copilot-consent-history-btn"`) en la cabecera del Copiloto.
   - Modal táctico de inspección de consentimientos (`data-testid="copilot-consent-modal"`) con visualización de entradas (`data-testid="consent-entry-item"`), hashes de prompt/contexto y distintivos cromáticos de red.

5. **Pruebas y Verificación**:
   - Pruebas unitarias de registro y lectura en host (`scripts/verify/test_copilot_audit.py`).
   - Pruebas frontend en Vitest (`dashboard/frontend/tests/copilot-consent.test.js`, 180 tests aprobados, Vite build limpio).
