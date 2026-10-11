# Fase 188: metadata ambigua permanece pendiente en checklist y cierre

Fecha: 2026-10-11 UTC. Rama `phase/188-checklist-metadata-parity`, base `1b7648f`. V3-03r parcial.

## Problema y cambio

El dashboard, el reporte y el contexto ya trataban una ficha con claves literales repetidas como fuente ambigua. El checklist instalado aún elegía la última aparición de `id`, `title`, `severity` o `asset`; una ficha declarada `PROVEN` podía influir en cobertura y cierre. El lector auxiliar de siguiente paso y el fallback de cierre solo detectaban `status` repetido. La regresión sobre la imagen anterior reproduce los cinco casos.

El checklist rechaza ahora cualquier clave literal repetida en el frontmatter. Conserva una fila `UNINTERPRETED` con el nombre de archivo y un código fijo de error, sin adoptar metadata ni cuerpo, y deja el cierre pendiente. El lector auxiliar clasifica esas fuentes como candidatas para que el recomendador solicite revisión y el fallback del packer bloquee el cierre si el checklist falta. Una ficha válida sigue contando según su estado declarado. Los originales permanecen intactos.

## Verificación y límites

La prueba local y la instalada cubren cinco claves repetidas, recomendación de triaje, checklist, cierre principal y fallback, ausencia de valores privados y fuente intacta; la instalada corre como `tester`, solo lectura y sin red, integrada en smoke. `make verify` aprobó 244 pruebas Python y linters; 237 backend instaladas, Compose, Actionlint, smoke y gate High/Critical aprobaron. Imagen aislada `seclab-sbf:full-phase188` (`sha256:60132baea5423077e3d1a0c1098a80c7543b59329eebb0ac6f8ba612122e67ba`) con insumos `2aef2ef439ad2ebc`. SBOM CycloneDX 1.7 válido, 2251 componentes y SHA-256 `8a33bf9944857fb8e6e89fe43e2a6c0bdecc74c3341abf1c9a97b11fea59df93`. CI [38146832126](https://github.com/hackadvisermx/seclab-sbf/actions/runs/38146832126) aprobó el head `850c730` antes del merge [#208](https://github.com/hackadvisermx/seclab-sbf/pull/208) en `a965f98`.

La detección cubre claves literales repetidas del parser plano; no valida todo YAML ni atribuye procedencia job–evidencia–finding. El laboratorio local quedó detenido por petición del owner para liberar espacio; no se borraron volúmenes ni proyectos ni se publicó imagen.
