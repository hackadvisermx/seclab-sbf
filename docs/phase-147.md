# Fase 147: validación obligatoria de reportes y exportación

Fecha: 2026-10-07. Base: `154ebfc`. Rama: `phase/147-report-scope-gate`. Worktree: `/Users/castr/tmp/t01-report-gate`. V3-03a; [PR #167](https://github.com/hackadvisermx/seclab-sbf/pull/167) fusionado en `d88a0f9` hacia `bootstrap/baseline` con la excepción autorizada por el owner.

## Cambios

- `pt-report check` y `build` comparten la revisión de las mismas fichas y scope cargados. `build` retorna 1 antes de escribir cuando falla estructura/lectura, falta activo, el activo está excluido o no tiene alcance confirmado. Scope inválido/ausente o validador indisponible también bloquean.
- Se mantiene el tuple público `(ok, issues, duplicate_warnings)`, la advertencia no bloqueante de duplicados y el cómputo de riesgo solo con `PROVEN`. Cero hallazgos es válido con directorio de evidencia y scope válidos.
- El packer recompila antes de crear staging/export y no reutiliza `REPORT.md`. Un fallo conserva el reporte y cualquier archivo de salida anterior. CLI `pack -j` comunica `status: blocked` y retorna 1.
- El runner consume el resultado JSON del packer. El dashboard no anuncia un paquete viejo al fallar; download siempre genera una entrega con los datos actuales, devuelve 409 ante bloqueo y descarga exactamente el archivo generado, sin escoger por mtime.
- Se corrigieron los imports de scripts instalados sin extensión mediante `SourceFileLoader`. Las pruebas de integración revelaron que el import anterior omitía Scope Guard en la imagen, y el packer silenciaba fallos del compilador.

## Validación

- Regresión de 7 pruebas reales CLI/Python: en baseline `154ebfc` falla con 14 aserciones; con el cambio pasa. Targets sintéticos `.test`, sin consultas externas.
- `make verify`: 150 pruebas Python aprobadas, incluido scope ausente/inválido, UNKNOWN/exclusión, fichas ilegibles, PoC ausente, falta de validador, salida personalizada, no sobrescritura y hash de paquete válido.
- `make dashboard-tests LAB_IMAGE=full-phase147 IMAGE_SOURCE=remote`: 127 pruebas; nuevos casos API ejecutan los scripts instalados reales, comprueban 409 ante exclusión y paquete antiguo con mtime futuro.
- `make build-full BUILD_TAG=-phase147`: imagen aislada `seclab-sbf:full-phase147`, hash `9090d8974368a11c`, igual a los insumos de la rama.
- Smoke, Compose `.env.example`, Actionlint y gate de CVEs High/Critical: aprobados sobre la imagen final; política existente, sin nuevas excepciones.
- Recorder en host y contenedor `--read-only --network none --user tester`: misma [medición 147](baselines/v3-phase147.json), conservando la [línea base 146](baselines/v3-phase146.json).

## Cambios de comportamiento y límites

El reporte sigue siendo borrador para revisión humana. Todas las fichas incluidas, cualquiera que sea su estado, requieren un activo autorizado y estructura válida. Los engagements antiguos deben completar esos campos antes de compilar/exportar. No se infiere ni amplía autorización.

Exportar o descargar recompila `REPORT.md`: las ediciones manuales de ese archivo generado se sustituyen por los datos de las fichas. Un fallo de validación no lo modifica. La vista previa puede conservar el último borrador; no equivale a una entrega validada actual.

Esta fase no certifica veracidad de PoC, procedencia original, integridad frente a edición concurrente ni validez legal de autorización. Cierre y `--force` mantienen su contrato; se revisarán con las compuertas de evidencia de V3-03. Las afirmaciones de trazabilidad y los outputs omitidos del export siguen pendientes (D08).

No se modificó el workspace/proyecto, la imagen viva ni el contenedor del owner. Reversión: revertir el PR restaura los caminos anteriores; los archivos de engagement no se migran.

El owner autorizó por excepción los merges durante esta sesión después de validaciones y CI. La regla normal de aprobación por PR vuelve al terminar la sesión.
