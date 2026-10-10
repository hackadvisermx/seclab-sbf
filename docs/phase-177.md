# Fase 177: fichas fuente y versiones seleccionadas en reporte/export

Fecha: 2026-10-10. Segunda de dos tareas adicionales; V3-03k parcial. Rama `phase/177-finding-source-manifest`, base integrada `50e92a3`, worktree `/Users/castr/tmp/t01-finding-source-manifest`.

## Problema y resultado

La fase176 identifica las fichas por UUID, pero el paquete no relaciona esa identidad con su fuente Markdown y selección de artefactos. La regresión contra full-phase176 confirma ausencia de finding-manifest y admite cambios de ficha/reporte entre compilación y copia.

El compilador lee cada ficha mediante el lector acotado/NOFOLLOW compartido, calcula SHA-256 de los mismos bytes que analiza y conserva la normalización de saltos de línea para Markdown. Fichas mayores de 32 MiB no son verificables y bloquean la compilación. El reporte enlaza la fuente y cada artefacto seleccionado mediante ruta relativa y fragmento SHA-256. El dashboard abre esos enlaces locales en su visor actual, compara el hash esperado con la lectura actual y conserva el manejo de respuestas tardías. La apertura es lectura: no guarda fichas ni inicia jobs. Enlaces externos conservan su comportamiento; DOMPurify sigue filtrando HTML.

Cada export añade `finding-manifest.json` esquema1 sin modificar source-manifest v1. Contiene hash original/copia del reporte y, por ficha compilada, UUID (null y unregistered si legacy), ruta/hash original/copia de su Markdown y referencias seleccionadas con hash esperado/original/copia. El manifest.sha256 incluye el nuevo archivo. Los hashes de copias se calculan después de sanitizar; los originales permanecen intactos. No copia título, activo, motivo ni cuerpo al nuevo payload.

El packer comprueba la huella del reporte generado y de las fichas compiladas antes de incluirlos. Cambios o ausencia bloquean antes de reemplazar el archivo comprimido anterior y limpian staging. Conserva los controles de scope, confirmación e integridad de referencias. Formatos tar.gz/zip y exports sanitizados/sin sanitizar mantienen compatibilidad.

## Verificación

237 Python (`make verify`), 215 backend sobre Python de la imagen instalada, 128 frontend/audit 0 y 4 UI aprobados. Cuatro regresiones de manifiesto pasan también sobre scripts instalados sin extensión, como tester/read-only/sin red, integradas en smoke: formatos tar.gz/zip sanitizados/sin sanitizar, CRLF, hashes original/copia, checksum del manifiesto, legacy/ausencia de fichas y cambios posteriores de ficha/reporte sin reemplazar paquetes previos ni dejar staging. Las mismas regresiones fallan en full-phase176. Smoke general, ocho identidades CLI y 21 regresiones de checkpoint aprobados.

Cinco integraciones Chromium con backend/tester/workspace desechables y sin red aprobadas. La auditoría abre desde el reporte la ficha fuente y su artefacto seleccionado, compara SHA-256 y verifica UUID, fuente, selección y hashes de finding-manifest contra originales/copias del paquete descargado. Capturas `report-finding-source.png` y `report-selected-artifact.png` inspeccionadas. Logs/capturas en `tmp/phase177` del checkout principal. Compose host/inside y Actionlint aprobados.

Imagen aislada `seclab-sbf:full-phase177`, label build-inputs `aa0523c8ec5142ca`, ID `sha256:52458010d0458879e3d04bbb031735523e64bd10acfce7748c72bb61f99a4d1c`, igual a los insumos del checkout. Gate High/Critical aprobado bajo política existente sin nuevas excepciones. SBOM CycloneDX1.7 válido, 2251 componentes, `tmp/phase177/sbom/seclab-sbf-full-phase177-aa0523c8ec5142ca.json`, SHA-256 `510e1dc9782fc8b32a29065275aad45dbf1714cb5240f15384b5672e9eafaaf6`. PR [#197](https://github.com/hackadvisermx/seclab-sbf/pull/197) fusionado en `91a5766` el 2026-10-10 19:02:01 UTC; CI `38078031646` aprobado para head `7ad2820c7780f79ae63b116895d0ffad31d473ef`. Rama/worktree retirados y baseline sincronizado.

## Límites

El manifiesto relaciona contenido e identidad declarada; no firma procedencia, autoría o vínculo job/finding. No conserva bytes históricos fuera del paquete ni añade timeline de revisiones. Los enlaces llevan la huella original: una copia sanitizada puede diferir; su huella entregada se consulta en el manifiesto. La UI abre el archivo actual del workspace y distingue cambios; no recupera versiones antiguas. Fichas legacy no reciben UUID por compilar/exportar. V3 global permanece parcial.

Merges autorizados hasta 2026-10-11 16:43:06 UTC con diff revisado, gates y CI del head exacto aprobados. Sin publicar/desplegar ni modificar proyectos del owner.
