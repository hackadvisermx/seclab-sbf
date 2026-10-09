# Fase 170: reducir descargas de Docker Hub en CI

Fecha: 2026-10-09. Rama `phase/170-ci-registry-dependency`, base `cb1b3aa`, worktree `/Users/castr/tmp/t01-ci-downloads`. Pedido del owner para mantener las pruebas en marcha frente a límites de Docker Hub; no completa una tarea funcional V3.

## Problema y cambio

La acción Docker de Actionlint fijaba el código, pero construía con Go/Alpine `latest` y ShellCheck `stable` desde Docker Hub. Cada runner nuevo resolvía esas imágenes. Node y Ubuntu usados en frontend/Fail2ban también se descargaban desde Docker Hub.

Actionlint 1.7.12, Hadolint 2.15.1 y ShellCheck 0.11.0 ahora se instalan como binarios Linux amd64/arm64 de sus releases oficiales. El lock contiene los seis SHA-256; se descargaron y midieron los seis archivos. Pyflakes, incluido en la acción anterior de Actionlint, se conserva como rueda 4.0.3 fijada por hash en un venv del runner. Hadolint mantiene el umbral warning; ShellCheck conserva selección recursiva por nombres/extensiones y ejecutables con shebang, salida gcc y fallo acumulado. La selección actual incluye 40 scripts. Actionlint sigue usando ShellCheck y Pyflakes.

La caché de Actions guarda archivos de releases por SHA-256, con clave de OS/arquitectura/hash del lock y acción fijada a commit. Cada instalación revalida los bytes incluso ante cache hit y reinstala los ejecutables desde esos bytes; nunca se ejecuta un binario restaurado sin verificar. Caché alterada provoca descarga y verificación, o rechazo en modo offline. Descargas HTTPS con reintentos y límite 128 MiB; escrituras atómicas. Para tar se lee solo el miembro regular declarado, sin extractall ni expansión de paths del archivo. El instalador no ejecuta los binarios.

Frontend y Fail2ban usan `public.ecr.aws/docker/library` con los mismos digests OCI de Node 24.21.0 y Ubuntu que antes. Se comprobaron ambos índices y se ejecutaron las pruebas desde ECR. No cambian npm 12.2.0, libpcre2, snapshot, versión/filtro/jail de Fail2ban ni criterios de aceptación. No se configura un mirror global ni se modifica Docker Desktop.

Fuentes primarias: [Dockerfile de Actionlint fijado anteriormente](https://github.com/rhysd/actionlint/blob/914e7df21a07ef503a81201c76d2b11c789d3fca/Dockerfile), [Actionlint 1.7.12](https://github.com/rhysd/actionlint/releases/tag/v1.7.12), [Hadolint 2.15.1](https://github.com/hadolint/hadolint/releases/tag/v2.15.1), [ShellCheck 0.11.0](https://github.com/koalaman/shellcheck/releases/tag/v0.11.0), [Pyflakes 4.0.3](https://pypi.org/project/pyflakes/4.0.3/), [ECR Public registries](https://docs.aws.amazon.com/AmazonECR/latest/public/public-registries.html).

## Validación

- `make verify`: 202 Python, incluyendo nueve regresiones de caché válida sin red, corrupción/reparación, descarga alterada, caché ausente offline, enlaces, tar con traversal/miembro enlazado, lock/URL/hash inválidos, límite y selección shell recursiva.
- Binarios arm64 reales instalados desde caché en contenedor desechable read-only/network-none; Hadolint warning, ShellCheck sobre 40 scripts y Actionlint con ShellCheck/Pyflakes aprobados. Los seis archivos amd64/arm64 se descargaron y verificaron por el instalador.
- Flujo frontend idéntico al workflow desde Node de ECR: audit 0, 122 pruebas y build aprobado. Fail2ban desde Ubuntu de ECR: versión 1.0.2-3ubuntu0.1, cinco ataques/umbral cinco y cero legítimos, configuración válida. No se prueba baneo efectivo en el host.
- `make build-full BUILD_TAG=-phase170`, smoke/regresiones instaladas, Compose y Compose VPN, Actionlint y gate High/Critical aprobados sin nuevas excepciones. Imagen aislada `seclab-sbf:full-phase170`, build-inputs `b393e89f56641f95`, image_id `sha256:185d3aff59356a836c286c98f4c860b6954787045d9092bd7f5423846c11591e`; etiqueta igual al hash medido. SBOM CycloneDX válido ligado al hash, SHA-256 `c5e7e2fd8fa43804766fb53d4bec5d2c15604928162b4353f86028f964b01338`.

Logs, archivos verificados y SBOM en `tmp/phase170` del checkout principal. CI del head exacto requerido antes de merge. Fase169/PR189 quedó fusionada en `cb1b3aa` con CI `38002433813` aprobado para head `9e331e2`; baseline sincronizado y rama/worktree retirados.

## Límites y operación

Un cache miss sigue requiriendo GitHub Releases/PyPI; frontend/Fail2ban necesitan ECR y repositorios de paquetes. Estos cambios reducen la dependencia de Docker Hub en las pruebas de CI, pero no sustituyen los orígenes de las imágenes del producto ni garantizan disponibilidad externa. Los checks fallan ante errores y mantienen los escáneres, umbrales y excepciones existentes. No añade excepciones de CVEs ni incorpora los binarios de CI a la imagen del laboratorio. No cambia UI, permisos de reconocimiento ni backlog funcional V3.

Laboratorio vivo, proyectos del owner, etiqueta full, publicación y despliegue intactos. PR hacia bootstrap/baseline con revisión de diff y CI del head exacto. Merge autorizado hasta 2026-10-10 14:56 UTC.
