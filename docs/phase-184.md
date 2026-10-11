# Fase 184: claves duplicadas bloqueadas en el reporte

Fecha: 2026-10-11 UTC. Rama `phase/184-report-source-gate`, base `c99bb3b`. V3-03o parcial.

## Problema y cambio

El dashboard de fase182 marca la ficha con metadata duplicada como fuente dañada, pero `pt-report-compiler` interpretaba el frontmatter línea por línea y conservaba la última declaración de cada clave. Una fuente podía declarar dos estados y llegar a check/build/export con uno solo de ellos; lo mismo ocurría con activo y referencias de artefactos. La regresión sintética en baseline registra cuatro fallos: `check_findings` devuelve éxito para status repetido en ambos órdenes, asset repetido y artifact_refs repetido (`tmp/phase184/baseline-duplicate.log`).

El parser plano del compilador rechaza una segunda aparición literal de la misma clave con un error fijo, antes de aceptar la ficha. El check falla, build no reemplaza `REPORT.md` y el packer conserva el paquete anterior. Los bytes originales de la ficha tampoco se modifican. Claves únicas y el comportamiento previo de fuentes sin duplicados se conservan.

## Verificación y límites

La regresión prueba las cuatro variantes, check/build/packer, bytes de reporte/paquete preexistentes y fuente intacta. Las 25 pruebas de seguridad del compilador pasan. `make verify` aprobó 238 pruebas Python y linters; Compose local/inside y Actionlint aprobados. La imagen aislada `seclab-sbf:full-phase184` (`sha256:100ffa3d456d5bdf8daefe6377bf66689f11d70e77fee10f3cd7cb0d107f34ed`) coincide con los insumos `eb5ab16b633fca97`. Pasaron la regresión instalada sin red/solo lectura, smoke, 237 pruebas backend instaladas y el gate High/Critical. El SBOM JSON validado tiene SHA-256 `d4ac9bd63e627407206e9752e65405675ce2a13a6cbe5c07702cd6a795a1fea7`. CI del head exacto antes del merge. El cambio no añade dependencias ni excepciones CVE.

Este gate cubre claves repetidas interpretadas por el parser simple del reporte; no sustituye el parser YAML estricto del dashboard ni completa la validación de sintaxis, tipos, delimitadores, alias/merges y claves anidadas. El parser de contexto y `pt-finding` conservan su contrato; esa paridad sigue pendiente. No añade historial, identidad de artefactos o vínculo job–finding. El laboratorio y proyectos del owner permanecen intactos, sin publicar/desplegar.
