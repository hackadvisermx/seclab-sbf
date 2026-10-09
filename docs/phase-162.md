# Fase 162: compuerta de confirmación de hallazgos

Fecha: 2026-10-08. Rama `phase/162-finding-confirmation-gate`, base `a655678`, worktree `/Users/castr/tmp/t01-confirmation-gate`. Entrega parcial V3-03f.

## Cambio y compatibilidad

El estado confirmado (`PROVEN`, `VERIFIED` o `CONFIRMADO`, sin distinguir mayúsculas/espacios exteriores) requiere activo, al menos una referencia path/SHA-256 y `verification_rationale` no vacío. La política estructural y normalización de estados se comparten en `scripts/seclab_findings.py`; el compilador conserva su función importable `normalize_status` por reexportación.

Guardar una ficha confirmada por API revalida hashes incluso si se omitió el campo de referencias, y exige activo IN_SCOPE según target.yaml actual. Ausencia de scope, YAML inválido, activo excluido/desconocido o evidencia cambiada/ausente rechazan el guardado con 409 antes de escribir la ficha. Omisión del motivo conserva el anterior; cambios explícitos se guardan como string JSON de una sola línea dentro del frontmatter YAML. Máximo 4000 caracteres y sin NUL; los saltos y comillas se conservan mediante escapes JSON.

La UI pide el motivo y bloquea guardar PROVEN mientras falte activo/vínculo/motivo. Un vínculo por sí mismo no cambia el estado. Alias confirmados se editan como PROVEN. Fichas antiguas incompletas siguen legibles, conservan estado/cuerpo/metadata y muestran “Revisión pendiente”; pueden completarse o pasar explícitamente a CANDIDATE. Leerlas no migra ni modifica archivos. El motivo se muestra también en el reporte.

Check/build y export aplican la misma compuerta a todos los alias confirmados. Un confirmado antiguo sin requisitos bloquea la compilación nueva y descarga, incluso si existía un reporte/paquete anterior; no se degrada ni se ignora automáticamente. CANDIDATE/DISPROVED/MITIGATED/DRAFT conservan soporte sin referencias ni motivo, aunque referencias declaradas inválidas siguen bloqueando según fase161. Crear por `pt-finding new --status proven` o alias se rechaza: crear primero CANDIDATE y revisar/completar en dashboard. Editar Markdown directamente sigue posible y se verifica al compilar; terminal libre no se intercepta.

## Verificación

```sh
make verify
make build-full BUILD_TAG=-phase162
make dashboard-tests LAB_IMAGE=full-phase162 IMAGE_SOURCE=remote
npm --prefix dashboard/frontend test
npm --prefix dashboard/frontend run audit
npm --prefix dashboard/frontend run test:e2e
npm --prefix dashboard/frontend run test:e2e:integration
make smoke-test SCAN_IMAGE=seclab-sbf:full-phase162
make compose-config ENV_FILE=.env.example LAB_IMAGE=full-phase162
go run github.com/rhysd/actionlint/cmd/actionlint@v1.7.12
make scan-image SCAN_IMAGE=seclab-sbf:full-phase162
```

- Reproducción en imagen fase161: la API permitía guardar PROVEN sin referencias ni motivo; fase162 rechaza el mismo caso antes de escribir.
- `make verify`: 183 Python; 180 backend; 112 frontend; audit 0. Pruebas cubren alias confirmados, omisión/preservación del motivo, NUL/formato/tamaño, alcance ausente/cambiado/excluido/validador indisponible, evidencia cambiada y conservación de fichas/reportes/paquetes ante rechazos.
- 3 UI Chromium y 5 integraciones con backend instalado, tester temporal y `--network none` aprobadas. Capturas `confirmation-gate.png` y `legacy-review-pending.png` inspeccionadas. Se corrigió la prueba para esperar la respuesta de guardado y el cierre del formulario antes de consultar el listado; el título previo permanecía visible durante la petición. Fixture y credenciales eliminados al terminar.
- Imagen aislada `seclab-sbf:full-phase162`, hash final de insumos `c87297afe2d83cf1`, idéntico al checkout. Build, smoke, Compose con `.env.example`, Actionlint y gate CVE High/Critical aprobados bajo política vigente, sin nuevas dependencias ni excepciones.
- Integración en [PR #182](https://github.com/hackadvisermx/seclab-sbf/pull/182) hacia `bootstrap/baseline`; estado y evidencia de CI del head exacto registrados en el PR. El merge requiere comprobarlos conforme a la autorización temporal.
- Merge confirmado en `999ae8106a91d62391ca74f864aadf871dcd8e61` el 2026-10-09 00:38:29 UTC. CI `37865534256` aprobado para head `1cfa3936d617a8547fac2f030fc9320adfaea5c0`; rama/worktree retirados y baseline sincronizado.

## Límites y reversión

Motivo y estado representan una declaración del operador. La compuerta comprueba campos, hash y alcance; no demuestra que el texto sea cierto, la severidad correcta o la evidencia suficiente. No firma revisiones ni identifica de forma inmutable al revisor, no vincula job/herramienta ni captura snapshot global. El listado advierte requisitos estructurales; hashes y alcance se revalidan al guardar/compilar/exportar, no al listar todas las fichas. No modifica permisos operativos ni añade capacidades a IA.

El campo manual `verification_rationale` debe ser string JSON en una línea del frontmatter (por ejemplo `verification_rationale: "Comparé respuesta y control negativo"`); Markdown escrito a mano con otro formato debe corregirse. Reportes anteriores visibles siguen siendo documentos guardados; esta fase protege compilación/export nuevos. Los originales y entregables previos se conservan ante los rechazos probados. Cambios después de una comprobación siguen posibles.

Revert restaura el comportamiento anterior y conserva metadata aditiva. Sin nuevas dependencias ni migración destructiva. Laboratorio vivo, proyectos del owner e imagen full intactos; merge autorizado durante la ventana de AGENTS.md solo con CI aprobado del head exacto.
