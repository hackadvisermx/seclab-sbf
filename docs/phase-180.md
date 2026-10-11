# Fase 180: edición de hallazgos ligada a la versión revisada

Fecha: 2026-10-10. V3-03l parcial. Rama `phase/180-finding-edit-version`, base `e1015f8`, worktree `/Users/castr/tmp/t01-finding-edit-version`.

## Problema y resultado

La identidad persistente de fase176 evita sustituir el UUID de una ficha; no evita que dos vistas editen la misma identidad sobre contenido diferente. La reproducción contra fase179 acepta la segunda escritura obsoleta y dos procesos guardando sobre la misma lectura, sobrescribiendo cambios previos.

Lista, detalle y guardado devuelven `source_sha256`, calculado sobre los mismos bytes que se decodifican para mostrar cuerpo/metadatos. Reusan el lector por descriptores sin enlaces, con detección de cambios y máximo 32 MiB. Leer una ficha legacy no la migra ni le asigna UUID.

Editar exige `expected_source_sha256` de esa lectura. Falta, formato inválido, cambio o eliminación devuelve 409 sin reemplazar la fuente ni recrear una ficha eliminada. El servicio serializa creación/edición/borrado de fichas por directorio evidence mediante flock y reconsulta la versión antes del reemplazo atómico. Mantiene UUID, cuerpo y metadata desconocida; siguen vigentes los gates de confirmación/artefactos/alcance.

El formulario envía la versión leída, conserva campos y Markdown ante error y ofrece comparar la ficha actual sin reemplazar el borrador. Presenta título, estado/severidad, activo/CWE/CVSS, cuerpo, vínculos y motivo de verificación de la fuente. Adoptar la versión requiere revisión explícita y no guarda: conserva los campos del borrador y prepara la nueva expectativa para otro clic de Guardar. No adopta una ficha con identidad diferente ni referencias/identidad marcadas inválidas. Guardado en curso deshabilita el formulario y evita doble envío; cambios de proyecto/tipo cierran el editor y descartan respuestas antiguas de lista/guardado/comparación.

## Compatibilidad y límites

Crear fichas nuevas no requiere versión. Clientes API que editan fichas existentes deben GET/listar primero y enviar `expected_source_sha256`, además del cuerpo completo; solicitudes antiguas reciben 409 con recuperación concreta. No hay override ni merge automático de contenido. El token es una precondición de edición, no una firma ni secreto, y no se persiste como metadata.

El bloqueo cubre escritores de fichas del servicio/dashboard, incluso procesos distintos. Editores libres/CLI no toman ese bloqueo; cambios terminados antes de leer o detectados al revalidar se rechazan, pero no se promete exclusión atómica frente a un escritor ajeno que cambie el archivo entre la última comprobación y replace. No añade snapshots históricos, autoría firmada, historial de revisiones ni vínculo job/finding. V3 global sigue parcial. El límite de lectura de fichas es 32 MiB; archivos mayores requieren revisión fuera del formulario.

## Verificación

`make verify`: 237 Python aprobados. `make dashboard-tests LAB_IMAGE=seclab-sbf:full-phase180 IMAGE_SOURCE=remote`: 226 backend aprobados, incluidos seis casos nuevos; las fuentes también pasaron sobre fase179. Comparan hash con bytes, rechazan edición obsoleta/ausente/inválida y fuente eliminada, permiten legacy tras recarga sin migración al leer y revalidan cambios/eliminación durante validación antes de replace. Dos procesos distintos con la misma versión permiten exactamente un guardado. Contra las fuentes fase179, las cinco regresiones iniciales fallan: API devuelve 200 ante escritura obsoleta y ambos procesos guardan; evidencia `tmp/phase180/baseline-version-final.log`.

Frontend: 147 pruebas y audit 0; seis casos nuevos cubren conflicto/borrador/comparación/adopción, falta de versión, guardado duplicado y tardío tras proyecto/tipo, comparación tardía/identidad ajena y lista tardía del proyecto previo. Cuatro UI Chromium aprobadas. Las fixtures previas de edición envían ahora versión fresca para conservar sus verificaciones de cuerpo, UUID, referencias, confirmación y CVSS cero.

Cinco integraciones Chromium contra backend instalado, usuario temporal y contenedor sin red aprobadas. La sesión existente incluye conflicto real provocado por otra escritura API, bytes intactos ante 409, comparación y adopción sin escritura, guardado posterior con hash/UUID correctos y recarga conservando borrador guardado. Alcance intacto e historial vacío. Capturas `finding-edit-conflict-comparison.png` y `finding-edit-version-saved.png` inspeccionadas y conservadas en `tmp/phase180/captures/`.

Imagen aislada `seclab-sbf:full-phase180`, build-inputs `454779822e1eda69`, ID `sha256:554ce8141f73055fd0585ec132e48f0555a6eaf931f101ec4561c31faddfc0b8`, igual al checkout. Base phase172 comprobada (`f772cb17ffe418a0`). Build, smoke (cuatro manifiesto, ocho UUID y 21 checkpoint), Compose local/inside y Actionlint aprobados. Gate High/Critical aprobado bajo política existente sin nuevas excepciones ni dependencias.

SBOM CycloneDX 1.7 válido, 2251 componentes, `tmp/phase180/sbom/seclab-sbf-full-phase180-454779822e1eda69.json`, SHA-256 `be285ffabb87390c035d96ba7277990ea83042676b8025f0cda8175b8e79a7ad`. PR [#200](https://github.com/hackadvisermx/seclab-sbf/pull/200), CI `38096673181` aprobado para head `930887040219f0b8f945963adc7fa1d0bc251d11`, merge `a51ce6ef74926ac6309fc4424319bc1b5279b252` confirmado a las 23:57:13 UTC; rama/worktree retirados y baseline sincronizado. Autorización hasta 2026-10-11 16:43:06 UTC. Sin publicar/desplegar ni modificar proyectos del owner.

Para completar la construcción se liberaron 6.229 GB de caché antigua y las etiquetas aisladas de fases ya fusionadas 173–178; se conservaron imágenes full/base del owner y phase179 para la regresión. El laboratorio siguió healthy. Evidencia local en `tmp/phase180/`, fuera del contexto Docker y de Git.
