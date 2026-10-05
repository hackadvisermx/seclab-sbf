# Fase 90 — respaldo y restauración del dashboard

El respaldo anterior solo empaquetaba el workspace. Esta fase añade una copia conjunta del workspace y `/var/lib/seclab/dashboard`: `vault.db`, `recon-jobs.db` y `.vault.key`. No cambia el borrado de proyectos (fase 91).

## Operación

Requiere Python 3 en el host, Docker y un contenedor `lab` creado pero detenido. Se resuelven sus montajes reales mediante `docker inspect`, sin adivinar el nombre de `lab-state`. Para conservar el contenedor, usar `stop`, no `down`:

```bash
docker compose -f compose.yaml -f compose.local.yaml stop lab
make dashboard-backup
# salida: ./backups/dashboard/dashboard-<fecha>-<id>.tar.gz y .sha256
make dashboard-backup DASHBOARD_BACKUP_DEST=/ruta/privada/copias
```

No se detiene ni se inicia el laboratorio automáticamente. Durante la operación no iniciar otro contenedor ni editar el workspace desde el host. Se rechazan contenedores activos que monten el mismo estado o un workspace solapado. El helper obtiene también el bloqueo exclusivo de reconocimiento. Un nombre de contenedor reservado por volumen impide dos operaciones de copia/restauración simultáneas incluso si usan directorios de respaldo distintos. Con `scripts/lab`, usar el mismo workspace y proyecto Compose del laboratorio que se quiere proteger.

Para recuperación, preparar un workspace vacío y un volumen `lab-state` nuevo (o con `dashboard` ausente/vacío) en el proyecto de destino. Crear el contenedor sin arrancarlo con `docker compose ... create lab`, pasando las mismas variables de workspace, imagen y secretos usadas normalmente. Los directorios host deben existir; no usar `make workspace-dir`, que los sembraría. Restaurar desde una copia local privada:

```bash
make dashboard-restore BACKUP=/ruta/privada/dashboard-<fecha>-<id>.tar.gz
make compose-up
```

No hay `FORCE`: un destino con datos se rechaza. La recuperación se prueba en otro workspace y volumen; no borrar los originales para ensayarla. Deben configurarse aparte las credenciales de acceso, SSH y VPN. Las sesiones antiguas se revocan en la copia restaurada y los jobs pendientes pasan a `interrupted` al arrancar el dashboard, con el mecanismo de fase 89.

## Consistencia, integridad y secretos

- El contenedor detenido permite copiar el workspace y estado en una ventana sin escritores del laboratorio. El helper no tiene red, usa la imagen local por ID con `--pull=never`, rootfs de solo lectura y solo los montajes de workspace, estado, copia y script. No monta `/run/secrets`, perfiles VPN del host ni Docker socket; del volumen `lab-state` solo empaqueta el subdirectorio `dashboard`. Usa root con capabilities `DAC_OVERRIDE`, `CHOWN` y `FOWNER` para leer archivos privados y devolver datos restaurados a UID/GID 1000.
- Las bases y sus auxiliares WAL/journal se copian primero a un directorio temporal privado. SQLite valida `integrity_check` y su API de backup crea bases autocontenidas en modo DELETE; no se empaquetan WAL, SHM ni locks. Se rechazan archivos de estado desconocidos, claves ausentes o inválidas y enlaces/archivos especiales. Tampoco se siguen enlaces del workspace.
- El manifiesto versionado registra SHA-256 de cada archivo. La restauración exige checksum externo y manifiesto coincidentes, valida todas las entradas tar sin usar extracción automática, rechaza rutas absolutas, `..`, duplicados, enlaces y tipos especiales, y comprueba SQLite antes de escribir los destinos.
- El directorio de copias debe tener permisos `700`; archivo y checksum se generan con `600` y propietario del operador del host. Los archivos restaurados quedan privados (`600`, o `700` si eran ejecutables), con directorios `700` y propietario `tester` (1000:1000).
- **El archivo contiene la clave de bóveda y secretos recuperables; no está cifrado.** Guardarlo localmente en almacenamiento privado/cifrado bajo control del operador; no subirlo a Git, CI, Docker Hub ni almacenamiento cloud. SHA-256 detecta corrupción, no autentica una copia manipulada junto a sus hashes. `.env`, perfiles VPN y claves SSH fuera del workspace no forman parte de la copia. Si se introducen secretos en el workspace, también se respaldan.

## Validación y límites

`make dashboard-backup-check` prueba en contenedores sin red y volúmenes/workspaces desechables una copia/restauración real: descifrado de una entrada AES-GCM, configuración, evidencia, jobs interrumpidos, revocación de sesiones, permisos/propietario y rechazo de una segunda restauración. Usa únicamente la imagen local ya disponible; limpia sus fixtures y no toca el laboratorio activo.

`make python-units-check` incluye 12 regresiones de backup: WAL, copia/restauración, secretos y permisos, corrupción/checksum/manifiesto, destinos ocupados, enlaces/FIFO, traversal tar, escritores activos y rollback ante fallo de movimiento.

La restauración no es una transacción atómica entre workspace y volumen: revierte los archivos nuevos ante errores controlados, pero una caída de host/proceso durante la escritura requiere revisar los destinos parciales y repetir sobre destinos vacíos. No conserva ACL, xattrs ni propietarios originales distintos de tester; se privilegian permisos privados. Requiere espacio para la copia temporal y archivo, y en restauración para staging y destinos. No incluye programación, subida remota ni restauración destructiva sobre datos existentes. La prueba real es local Docker Desktop; recuperación en VM cloud sigue pendiente.

## Evidencia local — 2026-10-05

- `make verify`: gate completo verde, 117 pruebas Python (12 nuevas). `make dashboard-tests`: 37 pruebas verdes. `make dashboard-backup-check`: restauración real verde, incluido descifrado AES-GCM y recuperación como UID 1000. Rechazo comprobado al intentar backup con el laboratorio real activo.
- `make build-full`: build nativo arm64 correcto. Hash actual de insumos `7af66e7c6b3c2281`, igual a la etiqueta de la imagen. ID local `sha256:1637b627cc8a549d6bbd61027a64742bb0325131eee0154964ef6cfcbdc1fd92` (no es un digest publicado en un registro).
- `make scan-image`: gate High/Critical verde con la política vigente de ignore-unfixed y excepciones existentes; no se agregaron excepciones. Trivy 0.74.0 fijado por digest.
- `make sbom`: `tmp/sbom/seclab-sbf-full-7af66e7c6b3c2281.json`, JSON válido; SHA-256 `9adbfdf645ad726be48fa7551d383b1989cfd7beaf0b65a8296706e6a7a8c39a`.
- Compose local/VPN con `.env.example`, Actionlint v1.7.12, referencias documentales y diff sin errores. Parseo de las nuevas recetas en Make 3.81 y GNU Make 4.4.1; CI verifica el Makefile en Ubuntu 24.04.
- Imagen construida y escaneada localmente; no se publicó ni reemplazó el contenedor activo. Pruebas sin objetivos externos.
