# Fase 160: huella de la versión revisada de un artefacto

Fecha: 2026-10-08. Rama `phase/160-artifact-fingerprint`, base `d0611da`, worktree `/Users/castr/tmp/t01-artifact-fingerprint`. Entrega parcial V3-03d.

## Estado observado y cambio

La API de artefactos devolvía solo nombre/ruta/tamaño/texto; sustituía UTF-8 inválido sin indicar que lo mostrado difería de los bytes originales. Comprobado en `full-phase159` instalado, como tester en contenedor read-only sin red, con archivo sintético propio: sin sha256/preview_status y con carácter de sustitución. Las funciones del visor aplicaban cualquier respuesta tardía sin comprobar selección, carpeta o proyecto.

La lectura devuelve además `sha256`, `modified` UTC, `fingerprint_status` y `preview_status`. SHA-256 representa los bytes originales completos hasta 32 MiB. El texto se previsualiza hasta 2 MiB; archivos mayores siguen teniendo huella hasta el límite de hash. Archivos por encima de 32 MiB no se leen y muestran explícitamente huella no disponible. NUL se trata como binario; UTF-8 inválido se sustituye solo en la vista, con aviso. El archivo vacío tiene la huella SHA-256 estándar y preview completo.

El lector abre cada componente relativo por descriptor con NOFOLLOW, comprueba archivo regular y usa NONBLOCK para evitar esperar en FIFO. Rechaza rutas absolutas, componentes vacíos/dot/traversal y enlaces. Compara inode/dispositivo/tamaño/mtime/ctime del descriptor antes/después y de la ruta final. Un cambio o reemplazo detectado produce 409 sin entregar contenido/huella; una ruta ausente/inaccesible conserva 404. Cierra descriptores tanto en éxito como en error.

El visor muestra tamaño/fecha/huella de la misma respuesta, permite copiar SHA-256 y distingue la previsualización del original. Copiar preview está deshabilitado durante carga/error o sin texto. Un contador de solicitud y la identidad de proyecto descartan respuestas tardías de lista/preview; cambiar carpeta/proyecto limpia selección y metadata. Desmontar invalida solicitudes pendientes.

## Validación

- `make verify`: 176 Python. Backend: 171, con cinco pruebas nuevas de snapshot/API y subcasos de vacío/UTF-8/binariedad, límite de lectura, mutación/reemplazo, traversal/symlink/FIFO, autenticación y conflicto 409.
- Frontend: 107; tres pruebas nuevas de metadata/reemplazos y carreras de lectura/listado/carpeta/error. Audit 0.
- 3 UI Chromium existentes con API simulada y 5 integraciones Chromium con backend instalado/tester temporal sin red. La nueva integración compara hashes con bytes locales, cambia versión, verifica límite de preview sin cambiar original, literalidad de HTML y ausencia de archivos adicionales. Captura `artifact-fingerprint.png` inspeccionada tras ajuste de legibilidad.
- Imagen aislada `seclab-sbf:full-phase160`, hash `10ae6ef8ef7a6bdc`, igual a insumos finales. Build, smoke, Compose `.env.example`, Actionlint y gate CVE High/Critical aprobados bajo política vigente; sin nuevas dependencias/excepciones.
- Recursos/credenciales temporales eliminados. Laboratorio vivo, proyectos del owner e imagen `seclab-sbf:full` intactos.

```sh
make verify
make build-full BUILD_TAG=-phase160
make dashboard-tests LAB_IMAGE=full-phase160 IMAGE_SOURCE=remote
npm --prefix dashboard/frontend test
npm --prefix dashboard/frontend run audit
npm --prefix dashboard/frontend run test:e2e
npm --prefix dashboard/frontend run test:e2e:integration
make smoke-test SCAN_IMAGE=seclab-sbf:full-phase160
make compose-config ENV_FILE=.env.example LAB_IMAGE=full-phase160
go run github.com/rhysd/actionlint/cmd/actionlint@v1.7.12
make scan-image SCAN_IMAGE=seclab-sbf:full-phase160
```

## Límites, compatibilidad y reversión

No añade identidad persistente de artefacto, captura inmutable, firma, parser ni vínculo con job/finding. Una huella identifica contenido, no procedencia, autorización o suficiencia de evidencia. No impide cambios después de la respuesta; volver a seleccionar obtiene una nueva lectura. Las comprobaciones de stat detectan los casos probados, no constituyen prueba forense contra escritores adversariales ni frontera global contra el mismo tester. El listado conserva metadata observada al listar; la cabecera de preview usa la lectura posterior.

API conserva campos anteriores y añade metadata. Las rutas relativas antes normalizadas que contenían dot/traversal ya no se aceptan. Binarios con NUL muestran aviso en vez de texto sustituido. El límite de hash evita trabajo no acotado por solicitud. No cambia exports/manifest, autorización, hallazgos ni datos existentes. Solo Chromium/macOS Docker Desktop comprobados; lector usa APIs POSIX de la imagen Linux y macOS. Revert restaura visor anterior sin migración.

PR #180 fusionado en `eef7924974b1f78b1d18e1db5052cf2fc0744a40`; CI `37858140399` aprobado para head `9748e659624941aa2dd4c15561af5b5877be1f06`. Autorización temporal del owner vigente hasta 2026-10-09 19:09:04 UTC, condicionada a CI aprobado del head exacto; después vuelve aprobación individual.
