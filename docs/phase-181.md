# Fase 181: borrado de fichas ligado a la versión revisada

Fecha: 2026-10-11 UTC. Primera de dos tareas adicionales. V3-03m parcial. Rama `phase/181-finding-delete-version`, base `a51ce6e`.

## Problema y resultado

Fase180 protege ediciones, pero DELETE aceptaba eliminar una fuente cambiada desde el listado o una identidad nueva bajo el mismo slug. Cuatro regresiones API sobre fase180 fallan: el borrado devuelve 200 y elimina la fuente. Evidencia `tmp/phase181/baseline-delete.log`.

DELETE y el servicio requieren `expected_source_sha256` de la lectura actual. Bajo el mismo flock del directorio evidence de fase180 se lee por descriptores y compara el hash antes de unlink. Falta, formato inválido, cambio/reemplazo o lectura fallida bloquea con 409; fuente ausente conserva 404. Legacy puede eliminarse tras leer la versión sin migración ni UUID inventado.

La UI envía el hash de la ficha listada y pide confirmación de esa versión. Conflicto conserva la tarjeta y muestra un error con recarga manual; recargar no elimina ni confirma automáticamente. Después de revisar la fuente actual, otro clic exige otra confirmación. Borrado pendiente evita duplicados y las respuestas tardías no actualizan otro proyecto/tipo o componente desmontado.

## Compatibilidad y límites

Clientes API de DELETE deben listar/GET primero y enviar el hash como query `expected_source_sha256`; solicitudes antiguas reciben 409. No hay override ni recuperación automática. El hash no es secreto ni firma. Conserva el bloqueo compartido con edición/creación y los límites de lectura de fase180. Escritores libres no toman flock: no promete exclusión atómica frente a cambios ajenos entre lectura y unlink. No añade papelera de fichas, snapshots, historial firmado o vínculo job/finding. V3 global sigue parcial.

## Verificación

Cinco regresiones backend cubren conflicto tras edición, token ausente/inválido, reemplazo de UUID/mismo slug, aislamiento de proyecto, legacy sin migración y carrera real edición/borrado entre dos procesos: exactamente una acción gana y la otra devuelve conflicto sin borrar una versión no leída ni recrear una fuente eliminada.

Cuatro casos frontend cubren hash enviado, conflicto/recarga/nueva confirmación, falta de versión/cancelación, doble envío y respuestas tardías de éxito/error tras cambiar proyecto. Chromium instalado amplía la sesión existente: segunda escritura API, DELETE obsoleto 409 conserva bytes, recarga sin escritura y nuevo DELETE 200 tras confirmar versión actual; GET posterior 404 y alcance/historial intactos.

Resultados finales: 237 Python (`make verify`), 231 backend instalado, 151 frontend/audit 0, 4 UI y 5 integraciones Chromium aprobados. Captura de conflicto inspeccionada. La limpieza de una fixture anterior de integración se actualizó para GET + DELETE versionado; el recorrido completo volvió a pasar. Build, smoke (cuatro manifiesto, ocho UUID y 21 checkpoint), Compose local/inside, Actionlint y gate High/Critical aprobados sin nuevas excepciones/dependencias.

Imagen aislada `seclab-sbf:full-phase181`, insumos `d56bca522c5034a2`, ID `sha256:2a737ef346e27234f50da77bb2a7d72bb8c50522eea2d1e190382a51cd3f4e02`, igual al checkout; base172 comprobada `f772cb17ffe418a0`. SBOM CycloneDX 1.7, 2251 componentes, `tmp/phase181/sbom/seclab-sbf-full-phase181-d56bca522c5034a2.json`, SHA-256 `418b9710fb3494452fb52b17b754bcdb9ce8f72880a5b674f6d6024119d4843e`. Evidencia local `tmp/phase181/`; sin publicar/desplegar ni modificar proyectos del owner. PR/CI del head exacto requeridos antes del merge bajo autorización hasta 2026-10-11 16:43:06 UTC.
