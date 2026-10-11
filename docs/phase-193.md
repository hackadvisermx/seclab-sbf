# Fase 193: metadatos del reporte fieles al YAML revisado

Fecha: 2026-10-11 UTC. V3-03t parcial.

El compilador validaba el frontmatter con el lector estricto, pero descartaba los valores interpretados y volvía a leer estado y activo con un parser de líneas. En la base, `status: "PROVEN # pendiente"` se convertía en `PROVEN`; `asset: "example.test # fuera de alcance"` se convertía en `example.test`. Así, el informe podía contar una ficha no confirmada o aprobar un activo distinto del declarado.

El compilador toma ahora los valores semánticos del lector compartido. Conserva únicamente la representación JSON literal de `artifact_refs` y `verification_rationale`, necesaria para validar las fichas existentes y rechazar un motivo que no sea una cadena JSON. Un activo YAML nulo mantiene el diagnóstico de activo faltante. La regresión reproduce el falso `PROVEN` en la base y comprueba que el estado citado no cuenta como confirmado y que el activo citado bloquea check/build. Las 26 pruebas de seguridad del reporte pasan con y sin PyYAML.

`scripts/verify/local-pr-gates.sh build` pasó usando la base local verificada `seclab-sbf:base-phase172`, sin pulls, pushes ni arranque del laboratorio: 247 pruebas Python, 242 backend, 155 frontend, 4 UI Chromium, build/audit, smoke instalado, Actionlint, gate CVE High/Critical y SBOM CycloneDX válido. Imagen aislada `seclab-sbf:full-phase193` (`sha256:5d511fac382f3d1d5eaf99468961a072f1ed339d69d37e3fdb289c4f39beb3cd`), insumos `c1eebb8d4dcaa9f5`, SBOM SHA-256 `ea30ff0ed5303c0eb1524150fe318d0f47bb6de9c041ec40421c2087e280664f`.

El cambio corrige la interpretación en el reporte; no afirma suficiencia probatoria ni añade procedencia de artefactos o jobs. El laboratorio local permanece detenido y sus volúmenes no se modificaron. CI del head exacto y merge se registrarán tras la revisión del PR.
