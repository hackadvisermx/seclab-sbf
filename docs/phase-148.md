# Fase 148: origen de archivos exportados y reporte verificable

Fecha: 2026-10-07. Base: `d88a0f9`. Rama: `phase/148-report-source-manifest`. Worktree: `/Users/castr/tmp/t01-report-provenance`. V3-03b, corrige D08. [PR #168](https://github.com/hackadvisermx/seclab-sbf/pull/168) fusionado en `efc4e01` con la excepción autorizada.

## Resultado

El reporte describe las fichas y el alcance declarado, sin afirmar automáticamente que hubo pruebas autorizadas, cobertura OWASP/PTES o registro sellado. Distingue si `terminal.log` está disponible y conserva como referencia no verificada el log indicado por cada ficha. Un alcance vacío se muestra como ausencia de activos autorizados.

El export conserva además `terminal.log`, `recon/recon.log`, `probe_observations.jsonl`, `urls_all.txt` y `js_files.txt` cuando existen, junto a las fuentes previamente exportadas. Con sanitización habilitada se aplica la redacción existente a esos outputs. Los archivos originales no se modifican.

`source-manifest.json` v1 registra por ruta el SHA-256 de los bytes originales leídos, el hash de los bytes exportados y `content_changed`. Se conserva `manifest.sha256` para verificar todos los archivos entregados, incluido ese manifiesto de origen. No es una firma ni acredita autenticidad, completitud o autoría.

Se rechazan fuentes enlazadas y archivos resueltos fuera del engagement, en lugar de incorporar por accidente datos ajenos. Un REPORT.md enlazado bloquea antes de recompilar. Las fichas/directorio de evidencia enlazados también bloquean la revisión estricta.

## Validación

- Suite de reportes: 10 pruebas, incluidas original/copia redactada, preservación de CRLF, SHA-256 para TAR/ZIP con y sin sanitización, archivos fuente intactos y enlaces rechazados.
- Regresión en baseline `d88a0f9`: falla en los casos nuevos (4 fallos, 4 errores); versión corregida pasa.
- `make verify`: 153 Python; backend real en imagen: 127 pruebas. Smoke, Compose `.env.example`, Actionlint y escaneo High/Critical según política existente; resultados finales en el PR.
- Build aislado `seclab-sbf:full-phase148`, hash `3b4bb453d3677e5e`.
- [Medición 148](baselines/v3-phase148.json): ya no se omiten los dos outputs observados en 146 ni se declara archivado un log ausente. Se conserva el registro histórico 146/147.

## Límites y riesgos

El export puede ser mayor y contiene más datos técnicos; `--sanitize` conserva las mismas reglas de redacción, no promete detectar cualquier secreto. No se añaden archivos arbitrarios de loot ni todo el workspace. Los hashes corresponden a los bytes seleccionados, sin snapshot transaccional entre archivos ni protección contra una carrera de reemplazo de paths.

La relación finding → artefacto → job, tool/version y revisión humana sigue pendiente en V3-03; los hashes no la sustituyen. Tampoco se modifica la compuerta de cierre. La revisión con personas de V3-00 sigue pendiente.

No se consultaron targets reales ni se modificaron proyectos, imagen viva o contenedor del owner. Reversión: revertir el PR; no hay migraciones. Merges permitidos excepcionalmente durante esta sesión, después de gates y CI; fuera de ella vuelve aprobación individual.
