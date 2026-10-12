# Fase 210: Verificación criptográfica e integridad de artefactos del engagement (artifact-manifest verify)

Fecha: 2026-10-12 UTC. Rama `phase/210-manifest-verify`, base `dd49a4a`. V3-03y parcial.

## Problema y cambio

En la Fase 204 (V3-03x) se introdujo la generación del manifiesto integral estructurado de artefactos (`artifact-manifest.json`, schema version 1) durante el empaquetado del engagement y su consulta vía API. Sin embargo:
1. No existía una herramienta para verificar de forma determinista y estricta la integridad de los artefactos del engagement frente a su manifiesto previo o paquetes exportados (`.zip` / `.tar.gz`).
2. No se detectaban de forma sistemática modificaciones no autorizadas (adulteración de hashes SHA-256), archivos ausentes ni ataques de escape de límites (rutas con `..`, rutas absolutas o enlaces simbólicos maliciosos insertados en el engagement).
3. El backend no exponía un endpoint operativo (`POST /api/v1/loot/{eng_id}/artifacts/verify`) para que auditores, instructores o procesos automatizados auditen el estado criptográfico de los artefactos en tiempo real.

En esta fase:
1. Motor de verificación criptográfica de artefactos (`scripts/pt-engagement-packer.py`):
   - Función `verify_artifact_manifest(engagement_dir, manifest_source=None) -> Dict[str, Any]`:
     - Soporta tanto directorios de engagement en disco como paquetes exportados comprimidos (`.zip`, `.tar.gz`).
     - Localización automática de `artifact-manifest.json` en raíz, `deliverables/` o archivos exportados.
     - Valida `schema_version: 1` y lista de artefactos.
     - Audita cada artefacto:
       - Rechazo estricto de rutas inseguras (`..` traversal o rutas absolutas) marcadas como `rejected`.
       - Detección de archivos ausentes marcados como `missing`.
       - Bloqueo y rechazo de enlaces simbólicos (`is_symlink()`) marcados como `symlink_rejected`.
       - Recálculo determinista de SHA-256 y comparación contra `sha256` o `original_sha256`, detectando adulteraciones (`hash_mismatch`).
     - Emite reporte consolidado con `is_valid`, `total_artifacts`, `verified_count`, `corrupted_count`, `missing_count` y desglose detallado por artefacto.
   - CLI subcomando `verify-manifest`:
     - `pt-engagement-packer verify-manifest [engagement] [-m/--manifest PATH] [-j/--json]`.
     - Soporte para flags `--verify-manifest`, `--manifest`, `--json`.
     - Código de salida 0 en caso de integridad válida, 1 si falla la integridad o existe error de auditoría, 2 para argumentos inválidos.
2. Backend y API (`dashboard/backend/app/services/workspace_sync.py` y `dashboard/backend/app/api/endpoints/loot.py`):
   - Servicio `workspace_service.verify_artifact_manifest(eng_id, eng_type, manifest_source)`.
   - Endpoints `POST /api/v1/loot/{eng_id}/artifacts/verify` y `GET /api/v1/loot/{eng_id}/artifacts/verify`.
3. Cliente Frontend API (`dashboard/frontend/src/api.js`):
   - Métodos `getArtifactManifest(id, type)` y `verifyArtifactManifest(id, data, type)`.
4. Pruebas y verificación:
   - 9 pruebas nuevas en `scripts/verify/test_artifact_manifest.py` (293 pruebas totales en `check-python-units.py` aprobadas en host).
   - Pruebas backend en `dashboard/backend/tests/test_artifact_manifest.py` (4 pruebas pasando).
   - 163 pruebas frontend en `npm test` aprobadas.
   - Build de producción Vite exitoso.

## Verificación y límites

- 293 pruebas Python en host ejecutadas y aprobadas.
- 4 pruebas backend FastAPI/TestClient ejecutadas y aprobadas.
- 163 pruebas frontend unitarias pasando sin fallos.
- V3-03y parcial: consolida la verificación criptográfica, auditoría de integridad y rechazo de symlinks y adulteraciones de artefactos del engagement.
