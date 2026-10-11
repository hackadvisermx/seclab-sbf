# Fase 194: salida del reporte sin seguimiento de enlaces ni truncamiento

Fecha: 2026-10-11 UTC. V3-03u parcial, sobre la fase 193.

`pt-report build` escribía `REPORT.md` o la ruta elegida con `Path.write_bytes`. Si la salida era un enlace simbólico, seguía el enlace y reemplazaba los bytes del destino. Una escritura fallida también podía dejar truncado el reporte anterior. La CLI resolvía la ruta personalizada antes de validar, ocultando que era un enlace.

La salida ahora rechaza un enlace simbólico existente. Compone el reporte en un archivo temporal del mismo directorio, sincroniza sus bytes y reemplaza la entrada de destino de forma atómica al terminar. Una falla de reemplazo conserva el archivo anterior y limpia el temporal. La CLI mantiene la ruta absoluta sin resolver enlaces para aplicar la misma regla. Las regresiones reproducen el sobrescrito y la ausencia de reemplazo seguro en la base; cubren salida estándar y personalizada, CLI y fallo de reemplazo.

`scripts/verify/local-pr-gates.sh build` pasó con la base local verificada `seclab-sbf:base-phase172`: 249 pruebas Python, 242 backend, 155 frontend, 4 UI Chromium, build/audit, smoke instalado, Actionlint, gate CVE High/Critical y SBOM CycloneDX válido. Las 28 pruebas de seguridad del reporte también pasaron sin PyYAML. Imagen aislada `seclab-sbf:full-phase194` (`sha256:aabb8bc839abefc680ffc05ef969793e103798d1b56f936906810600c9943b7c`), insumos `9e77d9716fbc1368`, SBOM SHA-256 `25d466cace9b778c96c910e33af0e8e71065feffdb366f9944b1f35f112204a3`.

No cambia el contenido del reporte ni la validación de fichas. Esta entrega no añade historial de versiones, firma ni procedencia de hallazgos. El laboratorio local permanece detenido y sus volúmenes no se modificaron.

Integración: [PR #214](https://github.com/hackadvisermx/seclab-sbf/pull/214), head `a1ac48a`, [CI 38161288702](https://github.com/hackadvisermx/seclab-sbf/actions/runs/38161288702) aprobado para ese head y merge `089065e` en `bootstrap/baseline`.
