# Fase 186: fichas enlazadas no alimentan contexto ni cierre

Fecha: 2026-10-11 UTC. Rama `phase/186-finding-source-links`, base `115e16e`. V3-03q/V3-05 parcial.

## Problema y cambio

Una entrada `evidence/*.md` enlazada a un archivo externo podía aparecer como hallazgo confirmado en `pt-context` y contaminar su título/activo con contenido fuera del proyecto. El checklist, el recomendador de siguiente paso y el cierre también seguían el enlace o ignoraban errores de lectura. Un fixture sintético en fase185 muestra `PRIVATE` y `private.test` en el contexto desde un enlace a `../private.md`.

Los cuatro consumidores usan ahora una lectura compartida de fichas con descriptor de directorio y archivo, ambos sin seguimiento de enlaces, apertura no bloqueante, comprobación de archivo regular y límite de 32 MiB. El contexto conserva una fila `UNINTERPRETED` sin contenido externo; checklist, siguiente paso y cierre mantienen la ficha como pendiente, incluso en el fallback de cierre sin checklist. También se rechaza un directorio `evidence/` enlazado y un FIFO sin esperar a un escritor. El archivo externo y los entregables previos no cambian.

## Verificación y límites

Tres pruebas nuevas cubren enlaces de archivo/directorio, FIFO, ausencia de contenido privado en contexto/checklist, recomendación de triaje, cierre principal/fallback y fuente intacta. La regresión instalada corre como `tester`, solo lectura y sin red, integrada en smoke. `make verify` aprobó 243 pruebas Python y linters; Compose, Actionlint, smoke y 237 backend instaladas aprobaron. La imagen aislada `seclab-sbf:full-phase186` (`sha256:ddcd2084feabd4567ddd26aadb67d0ee3d694d256afe692dcc2a032af9f42a05`) coincide con los insumos `ca655f4838ad2186`. Gate High/Critical aprobado sin nuevas excepciones; SBOM CycloneDX 1.7 válido, 2251 componentes y SHA-256 `99de030d2f06a32676f3cb51df2963dda98ce41ff5dc19b4e6e0544598c78021`. CI [38110351287](https://github.com/hackadvisermx/seclab-sbf/actions/runs/38110351287) aprobó el head `45060d0` antes del merge [#206](https://github.com/hackadvisermx/seclab-sbf/pull/206) en `07b4951`.

La compuerta se limita a fichas `evidence/*.md` y al último componente del directorio `evidence/`; no convierte todo el workspace en una vista inmutable ni valida la procedencia de bytes creados por herramientas. Los parsers planos aún no sustituyen una validación YAML completa. No añade permisos de ejecución, publica imágenes ni toca el laboratorio vivo.
