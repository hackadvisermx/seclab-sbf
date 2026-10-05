# Fase 91 — papelera y restauración de proyectos

Eliminar desde el dashboard mueve ahora el proyecto completo a una papelera persistente del workspace. No destruye sus notas, evidencia, reportes, logs, capturas, botín o banderas. La fase 90 ya protege esa carpeta en el respaldo completo.

## Flujo del operador

1. En la lista o detalle de auditorías/retos, pulsar **Eliminar**. La confirmación explica que el proyecto se moverá a la papelera y se puede recuperar.
2. Confirmar **Mover a la papelera**. El proyecto desaparece de la lista activa.
3. Abrir **Papelera** desde la lista de proyectos. Cada copia muestra nombre, tipo y fecha de eliminación; puede haber varias versiones con el mismo nombre.
4. Pulsar **Restaurar proyecto** en la versión deseada. Si existe un proyecto con ese nombre y tipo, se devuelve un conflicto y la copia permanece en la papelera. Resolver el nombre ocupado antes de reintentar; no se fusionan ni sobrescriben archivos.
5. Tras restaurar, **Abrir proyecto** permite acceder de nuevo a sus notas y evidencia.

Los estados de reconocimiento `running` y `cancelling` bloquean tanto la eliminación como la restauración del mismo tipo/ID. El último job de SQLite se limpia al mover/restaurar para no asociar una ejecución de otra instancia del proyecto. Sus artefactos y logs dentro del proyecto se conservan; no se crea un historial de jobs ni se relanzan procesos.

No hay caducidad, purga automática ni botón de borrado definitivo en esta fase. Las copias siguen ocupando disco y contienen el mismo material sensible que el workspace. La papelera no sustituye un respaldo fuera de la VM. Solo recupera eliminaciones realizadas por este flujo después de la actualización; no reconstruye carpetas borradas anteriormente o desde herramientas externas.

## API y persistencia

- `DELETE /api/v1/engagements/{id}?type=engagement|reto` conserva su contrato de `status`, `id`, `type` y añade `trash_entry` (`entry_id`, `project_id`, `type`, `deleted_at`).
- `GET /api/v1/trash` lista copias válidas, ordenadas por fecha descendente.
- `POST /api/v1/trash/{entry_id}/restore?project_id={id}&type=engagement|reto` restaura exactamente esa versión.
- Toda la API requiere sesión; `400` para entradas/rutas inválidas, `404` para copia ausente, `409` para reconocimiento activo o destino ocupado, `500` para fallo de permisos/movimiento.

`app/core/project_trash.py` almacena carpetas en `/workspace/.seclab-trash/{engagements|retos}/{id}/{fecha-UTC-microsegundos}-{uuid}`. Nombre/tipo se derivan de componentes validados y la fecha del identificador; no hay índice SQLite ni manifiesto separado que pueda perder sincronía con el movimiento. El listado se reconstruye después de reiniciar el servicio. La papelera queda fuera de los directorios activos y sus padres usan permisos `700`.

El movimiento usa `renameat2(RENAME_NOREPLACE)` del runtime Linux del laboratorio: es atómico dentro del mismo filesystem y rechaza incluso un destino vacío creado después de validar. No hace copia seguida de borrado ni fallback entre filesystems; un error de movimiento mantiene el origen. Las mutaciones del workspace (crear, mover, restaurar) comparten un bloqueo y las de papelera pasan también por el bloqueo de reconocimiento. El dashboard conserva su lease exclusivo de fase 89 para evitar múltiples instancias activas sobre su estado.

Se comparten las reglas de identificadores y tipos de `workspace_paths.py`. Se rechazan enlaces simbólicos en raíces, categorías, entradas, destino y contenido, además de archivos especiales. Las entradas dañadas o desconocidas se omiten del listado, sin borrarlas. El aislamiento frente a cambios realizados por el mismo usuario Unix `tester` sigue siendo un límite de arquitectura; operar desde el dashboard evita escritores manuales concurrentes. Si `renameat2` no está disponible (por ejemplo al ejecutar el backend directamente en macOS), la operación falla cerrada: usar el dashboard instalado en la imagen Linux.

## Validación

- `test_project_trash.py` añade 13 pruebas: round trip de archivos por ambos tipos, versiones repetidas, colisiones, jobs running/cancelling, recarga del servicio, identificadores/fechas inválidos, autenticación y estados API, enlaces, fallos de movimiento, aparición tardía de destino vacío y concurrencia con creación.
- `project-trash.test.js` añade tres pruebas DOM: restauración de una versión sin retirar otra, preservación de una copia ante conflicto y confirmación recuperable antes de llamar a la API de eliminación. El frontend conserva las cuatro pruebas anteriores.
- `make dashboard-backup-check` se amplía para respaldar una copia en papelera, restaurar el workspace/estado y recuperar sus notas desde esa papelera. Usa volúmenes y contenedores desechables sin red.
- Comprobación visual en Chrome con un servidor de fixtures publicado exclusivamente en `127.0.0.1:18091`: confirmar eliminación, ver la copia, restaurar, abrir y leer las notas conservadas. Servidor y workspace de prueba retirados; evidencia visual en `tmp/phase91-trash.jpg` y `tmp/phase91-restored.jpg` (sin versionar).

No se detuvo ni se reemplazó el laboratorio real, no se publicó una imagen y no se ejecutó reconocimiento sobre UAZ ni otros objetivos externos. Aceptación en el despliegue del operador y recuperación en cloud siguen pendientes; merge requiere aprobación del owner.

## Evidencia local — 2026-10-05

- `make verify`: gate completo verde, 117 pruebas Python. `make dashboard-tests`: 50 pruebas verdes en la imagen instalada, sin skips. Frontend: siete pruebas y auditoría npm con 0 vulnerabilidades al construir el builder; build de producción correcto.
- `make dashboard-backup-check`: recuperación real de bóveda/configuración/workspace/jobs/sesiones/permisos y papelera, seguida de restauración de las notas del proyecto eliminado.
- `make build-full`: build nativo arm64 correcto; insumos actuales y etiqueta coinciden en `f4c6660e528918bc`. ID local `sha256:b27a8c35931dc0f98b1a817710f32e2bf9c213328810acaf117f9c4a007407d8`; no es un digest publicado en un registro.
- `make scan-image`: gate High/Critical verde con Trivy 0.74.0 por digest, política ignore-unfixed y excepciones existentes. El primer intento compitió por caché con el SBOM y falló por lock; el reintento secuencial terminó correctamente. No hay excepciones nuevas.
- `make sbom`: `tmp/sbom/seclab-sbf-full-f4c6660e528918bc.json`, JSON válido, SHA-256 `79c98b2f767428ca5d123611db8b0d3ddee9abad7e812cc492cafd45f1d0538e`.
- Compose local/VPN con `.env.example`, Actionlint v1.7.12, referencias documentales y `git diff --check` correctos. El Makefile no cambió.
