# Fase 176: identidad persistente de hallazgos

Fecha: 2026-10-10. Primera de dos tareas adicionales; V3-03j parcial. Rama `phase/176-finding-identity`, base `90cd8aa`, worktree `/Users/castr/tmp/t01-finding-identity`.

## Problema y resultado

El dashboard crea fichas sin identidad persistente; el reporte usa el nombre de archivo si falta el ID legible de plantilla. Renombrar una ficha puede cambiar esa referencia. Regresión nueva contra full-phase175 falla: falta finding_id y la API admite intentos de elegir/sustituir identidad. La regresión Zsh ampliada falla en esa imagen por ausencia del campo.

API y `pt-finding new` asignan `finding_id` UUID v4 hexadecimal nuevo, independiente del título, slug e ID legible. Edición conserva el UUID; la UI lo muestra y envía como expectativa al editar. Una expectativa distinta del UUID actual, campo inválido o UUID duplicado bloquea antes de escribir. Creación usa archivo temporal y hard link exclusivo para no sustituir una ficha aparecida entre revisión y escritura; temporales se limpian. Renombrar/mover la ficha conservando el frontmatter mantiene la identidad.

Legacy sigue legible con identidad no registrada; leer/listar/reportar no reescribe fichas ni inventa UUID históricos. El primer guardado válido asigna uno y los siguientes lo conservan. El ID legible y metadatos anteriores se mantienen. El compilador incluye el UUID o indica su ausencia; check/build/export rechazan identidades explícitas inválidas o duplicadas. Copiar una ficha con su UUID representa una colisión: revisar/eliminar la copia o crear una ficha nueva, no sustituir silenciosamente el ID.

## Verificación

233 Python (`make verify`), 215 backend de fuentes sobre Python instalado, 126 frontend/audit 0 y 4 UI aprobados. Backend prueba edición/rename/reapertura, legacy sin escritura/asignación única, sustitución/corrupción/duplicados y creación concurrente. Reporte comprueba rename y bloqueo sin reemplazar entregable; lectura legacy no altera fuente. Smoke instalado aprobado como tester/solo lectura/sin red: UUID distintos en ocho fichas de plantillas/fallback y rename, junto a 21 regresiones de checkpoint. Backend final 215 aprobado sobre imagen instalada. Chromium: 5 integraciones aprobadas con identidad conservada en creación, confirmación, recarga, rename y reporte; capturas finding-identity y finding-identity-renamed inspeccionadas. Compose host/inside y Actionlint aprobados.

Imagen aislada `seclab-sbf:full-phase176`, label build-inputs `4275905c09839e09`, ID `sha256:de2718d9635792526ca4a2acdbcdb724b3b2fafb7357d67eefd518d168306859`, igual a los insumos del checkout. Gate High/Critical aprobado bajo política existente, sin nuevas excepciones. SBOM CycloneDX válido, 2251 componentes, `tmp/phase176/sbom/seclab-sbf-full-phase176-4275905c09839e09.json`, SHA-256 `06eb9becbd69f4facc2401ffdaee590a66177625e90054b3b5dc27ee929d644b`. Logs/capturas en tmp/phase176 del checkout principal. PR/CI del head exacto requeridos antes del merge.

## Límites

El UUID identifica una ficha; no acredita autor, evidencia suficiente, productor ni job. Editar manualmente el frontmatter o eliminar/recrear una ficha queda fuera de la protección de edición API. No migra todo legacy ni crea timeline de revisiones, IDs de artefactos o relación job/finding. Segunda tarea añadirá enlaces de fuente al reporte/export; V3 global permanece parcial.

Merges autorizados hasta 2026-10-11 16:43:06 UTC, siempre con diff revisado, gates y CI aprobados del head exacto. Sin publicar/desplegar ni modificar proyectos del owner.
