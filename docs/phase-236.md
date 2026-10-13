# Fase 236 — Firma Criptográfica y Sellado de No Repudio de Entregables (V3-03ee)

## Contexto y Motivación
La iniciativa V3-03 establece que la procedencia y la cadena de custodia de la evidencia deben garantizar que los entregables sean verificables, inmutables y defendibles. Tras la implementación de `artifact-manifest.json` v1 y su verificación en la Fase 214, el sistema podía detectar discrepancias de hash o archivos alterados; no obstante, carecía de un mecanismo de firma y sellado formal que acreditara la identidad del auditor y sellara criptográficamente el manifiesto contra una clave local de auditoría para garantizar no repudio.

Esta fase implementa el motor de firma criptográfica y verificación (`scripts/seclab_signature.py`), soporte CLI en `pt-engagement-packer.py` (`sign-manifest`, `verify-signature`), endpoints backend en `dashboard/backend/app/api/endpoints/loot.py` (`POST /api/v1/loot/{id}/artifacts/sign`, `GET /api/v1/loot/{id}/artifacts/signature`), métodos frontend en `api.js` y el componente de sello criptográfico (`artifact-signature-badge`, botón `sign-artifact-manifest-btn`) en el modal de verificación de artefactos en `EngagementDetailView.vue`.

## Cambios Implementados

1. **Módulo de Firma Criptográfica (`scripts/seclab_signature.py`)**:
   - `get_or_create_signing_key(engagement_dir)`: Genera o recupera de forma persistente una clave secreta de auditoría de 256 bits protegida con permisos estrictos `0600` en `.credentials/.audit_signing_key`.
   - `sign_artifact_manifest(engagement_dir, signer, custom_key)`: Calcula el hash SHA-256 del `artifact-manifest.json`, genera una firma HMAC-SHA256 y persiste de forma atómica `artifact-manifest.sig.json` con metadatos del firmante, timestamp UTC, key ID y firma.
   - `verify_manifest_signature(engagement_dir, custom_key)`: Verifica la coincidencia criptográfica entre el manifiesto actual en disco y la firma registrada, detectando manifiestos alterados (`tampered_manifest`), firmas inválidas o estados sin firma (`unsigned`).

2. **Integración en Empaquetador (`scripts/pt-engagement-packer.py`)**:
   - Subcomandos CLI `sign-manifest` y `verify-signature`.
   - Inclusión automática del estado de firma dentro del resultado retornado por `verify_artifact_manifest`.

3. **Backend (`dashboard/backend`)**:
   - Métodos `sign_artifact_manifest` y `get_manifest_signature` en `WorkspaceSyncService`.
   - Endpoints `POST /api/v1/loot/{eng_id}/artifacts/sign` y `GET /api/v1/loot/{eng_id}/artifacts/signature` en `loot.py`.

4. **Frontend Dashboard (`dashboard/frontend`)**:
   - Métodos `api.signArtifactManifest` y `api.getArtifactManifestSignature`.
   - Sección interactiva en el modal de verificación de artefactos (`EngagementDetailView.vue`) con selector de estado `data-testid="artifact-signature-badge"` y botón `data-testid="sign-artifact-manifest-btn"`.

5. **Pruebas y Verificación**:
   - 6 pruebas unitarias Python en host (`scripts/verify/test_seclab_signature.py`).
   - 1 prueba frontend en Vitest/Node (`dashboard/frontend/tests/artifact-signature.test.js`).
   - 189 pruebas frontend aprobadas, build Vite verificado y suite `make verify`.
