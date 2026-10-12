# Fase 214: Modal de verificación criptográfica e integridad de artefactos en Dashboard

Fecha: 2026-10-12 UTC. Rama `phase/214-artifact-verify-ui`, base `dd49a4a` (integrada sobre `ddb0a88`). V3-03aa parcial.

## Problema y cambio

En la Fase 210 (V3-03y) se integró el motor CLI y el endpoint de backend `POST /api/v1/loot/{eng_id}/artifacts/verify` y `GET /api/v1/loot/{eng_id}/artifacts/verify` para auditar la integridad criptográfica de los artefactos del engagement contra `artifact-manifest.json`.

Sin embargo, el dashboard web no exponía un control interactivo ni modal para que el operador o auditor ejecutara y visualizara esta auditoría desde la interfaz gráfica sin recurrir a la terminal.

En esta fase:
1. Interfaz de usuario en `dashboard/frontend/src/views/EngagementDetailView.vue`:
   - Botón interactivo «🛡️ Verificar Integridad» en la cabecera de la pestaña de artefactos y entregables.
   - Estado reactivo (`verifyingArtifacts`, `showArtifactVerifyModal`, `artifactVerifyResult`, `artifactVerifyError`).
   - Modal táctico `artifact-verification-modal` con accesibilidad ARIA (`role="dialog"`):
     - Insignia de estado global: `INTEGRIDAD VÁLIDA` (verde) vs `INTEGRIDAD COMPROMETIDA` (rojo).
     - Métricas consolidadas: total de artefactos, verificados conformes, corruptos/adulterados (`hash_mismatch`), ausentes (`missing`) o rechazados (`rejected` / `symlink_rejected`).
     - Alerta visual en caso de detección de discrepancias o violaciones de seguridad.
     - Tabla detallada por artefacto con ruta relativa, categoría, estado y visualización de hashes SHA-256 (esperado en manifiesto vs calculado en disco).
     - Botón para reejecutar verificación en vivo o cerrar el modal.
2. Pruebas y verificación:
   - Suite de pruebas en `dashboard/frontend/tests/artifact-verify.test.js`:
     - Apertura del modal y visualización de resultados válidos (`INTEGRIDAD VÁLIDA`).
     - Renderizado de anomalías y hashes discrepantes en caso de corrupción (`INTEGRIDAD COMPROMETIDA`).
   - 169 pruebas frontend unitarias ejecutadas y aprobadas en Vitest.
   - Build de producción Vite completado exitosamente.

## Verificación y límites

- 169 pruebas frontend aprobadas (`npm test`).
- Build de producción de Vite limpio sin errores.
- V3-03aa parcial: interfaz web para verificación criptográfica de artefactos contra manifiesto estructurado.
