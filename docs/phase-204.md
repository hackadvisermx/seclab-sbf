# Fase 204: manifiesto integral de artefactos del engagement (artifact-manifest v1)

Fecha: 2026-10-12 UTC. Rama `phase/204-artifact-manifest`, base `ef2fac4`. V3-03x parcial.

## Problema y cambio

Durante la auditoría de seguridad y el empaquetado final de entregables, el laboratorio genera múltiples tipos de artefactos: reportes técnicos, alcances definidos, notas de campo, resúmenes de reconocimiento, logs de sesión y evidencias de vulnerabilidades. Conforme al criterio de aceptación V3-03:
1. El empaquetador generaba `manifest.sha256` plano, `source-manifest.json` y `finding-manifest.json`, pero no existía un manifiesto estructurado único que consolidara el inventario completo de todos los artefactos generados en el engagement clasificados por categoría, tamaño, hash SHA-256 e indicación de procedencia.
2. Los consumidores externos (APIs, plataformas SIEM, auditores) no contaban con un endpoint para consultar el manifiesto estructurado de artefactos en tiempo real sobre el workspace sin tener que descargar o desempaquetar el bundle comprimido.

En esta fase:
1. Empaquetador (`scripts/pt-engagement-packer.py`):
   - Se añadió la generación de `artifact-manifest.json` (schema `artifact-manifest v1`) dentro del paquete exportado antes de `manifest.sha256`.
   - Clasifica cada artefacto en categorías semánticas: `report`, `scope`, `notes`, `evidence`, `recon`, `terminal`, `manifest`, `loot`, etc.
   - Registra `path`, `category`, `size_bytes`, `sha256`, `original_sha256`, `content_changed`, `source_job_id` y `source_stage`.
   - Incorpora metadatos globales: `schema_version: 1`, `engagement_id`, `generated_at` (UTC), `sanitized`, `total_artifacts` y `total_bytes`.
   - Integra `artifact-manifest.json` en `manifest.sha256` para garantizar su inmutabilidad criptográfica.
2. Backend y API (`dashboard/backend/app/services/workspace_sync.py` y `dashboard/backend/app/api/endpoints/loot.py`):
   - Método `workspace_service.get_artifact_manifest(eng_id, eng_type)` que recorre de forma segura los archivos y carpetas permitidas del workspace (`recon/`, `evidence/`, `loot/`, `fuzzing/`, `screenshots/`, `deliverables/`, `exports/` y archivos raíz).
   - Calcula hashes SHA-256, tamaños y marcas de tiempo UTC.
   - Nuevo endpoint `GET /api/v1/loot/{eng_id}/artifacts/manifest` (y vía proxy de engagement) para consultar el inventario estructurado bajo demanda.
3. Pruebas y verificación:
   - Python tests: `scripts/verify/test_artifact_manifest.py` integrado en `check-python-units.py` verificando el empaquetado, esquema y contenido de `artifact-manifest.json`.
   - Backend tests: `dashboard/backend/tests/test_artifact_manifest.py` en Docker validando el servicio y el endpoint HTTP autenticado.

## Verificación y límites

- Verificado en el runner Docker y suite de pruebas unitarias Python.
- `artifact-manifest v1` audita la integridad criptográfica y tamaño de los artefactos del engagement; no firma con clave asimétrica externa.
