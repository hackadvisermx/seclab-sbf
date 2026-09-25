# Fase 3 — Imagen light, acceso y herramientas base

## Estado

La fase 3 v1 está implementada y verificada en Docker Desktop ARM64, con build y comprobación básica de la variante AMD64. Incluye imagen `light`, ttyd, OpenSSH, shell no root para `tester` y herramientas base de Ubuntu. SFTP y las cuentas separadas de transferencia/proxy se eliminan del diseño. La subfase de herramientas upstream Go está incorporada con commits fijados, builder Go pineado y hashes por arquitectura en el lockfile.

## Artefactos

- `images/light/Dockerfile`: imagen `light` basada en la imagen `base` fijada y stage separado para compilar `fzf` con Go 1.25.13.
- `scripts/install-light-packages.sh`: instalación desde snapshot de Ubuntu y limpieza de índices APT.
- `security/ssh/sshd_config`: SSH por clave para `tester`, sin contraseña, sin forwarding y sin SFTP.
- `scripts/entrypoint/light-entrypoint.sh`: parseo seguro de `.env`, host keys persistentes y supervisores de sshd/ttyd.
- `scripts/entrypoint/ttyd-as-tester.sh`: ttyd con logging debug bajo, origen comprobado y un cliente máximo.
- `scripts/health/light-healthcheck.sh`: valida procesos y binarios de acceso.
- `compose.yaml`: monta `/workspace`, secret file y estado persistente.
- `supply-chain/tools.lock.yaml`: snapshot APT, commits, checksums Go y hashes por arquitectura de los binarios construidos.

## Herramientas upstream Go

`images/light/Dockerfile` añade el stage `upstream-builder` con
`golang:1.26.8` pineado por digest (requerido por `httpx`/`katana`/`nuclei`,
que exigen Go 1.26). Cada herramienta se clona por commit exacto, se
verifica con `rev-parse` y se compila estática (`CGO_ENABLED=0`,
`trimpath`, `buildvcs=false`):

- `subfinder` 2.16.0 (`b360529e`), `httpx` 1.11.0 (`c5f67adc`),
  `katana` 1.7.0 (`17b0af27`), `nuclei` 3.11.1 (`a8c88feb`),
  `ffuf` 2.2.0 (`0aa36bcf`), `gobuster` 3.8.2 (`e8410cad`).
- `dalfox` 3.2.1 no se compila: el upstream se reescribió en Rust y se
  consume el binario musl oficial con SHA-256 por arquitectura, con el
  mismo patrón que `ttyd`/`zoxide`.

`ffuf` v2.2.0 conserva `VERSION 2.1.0-dev` en `pkg/ffuf/constants.go`;
es un detalle cosmético del upstream, el commit pineado es el del tag.
El primer build reportó 11C/25H en dependencias Go transitivas
(`x/crypto`, `x/net`, `x/mod`, `pgx`, `grpc`, `go-git`); el Dockerfile
aplica `go get` pineados (`x/crypto` v0.56.0, `x/net` v0.56.0/0.57.0/0.58.0
según grafo, `x/mod` v0.40.0, `pgx/v5` v5.9.0, `grpc` v1.83.2,
`go-git/v5` v5.19.2, registrados por herramienta en el lockfile) más
`go mod tidy`, y Scout quedó en 0C/0H/0M/0L en ARM64.
`nuclei` (~132 MB) domina el tamaño nuevo de la imagen (~290 MB entre
las 7). Quedan fuera de esta tanda: `naabu` (requiere libpcap/CGO),
`feroxbuster` (requiere toolchain Rust), plantillas de Nuclei, wordlists
y pwntools.

## Paquetes light

Incluye herramientas oficiales de Ubuntu 24.04: OpenSSH, `nmap`, `sqlmap`, `socat`, `openvpn`, `wireguard-tools`, `zsh`, `tmux`, `ripgrep`, `fd-find`, Python, GDB y utilidades de red/archivos. `fzf` 0.74.4 se compila desde el commit `a140afeb4d733cad3c96a56bf6db7e26853b6757` con Go 1.25.13 y `x/sys` 0.44.0. `ttyd` 1.7.7 se descarga como binario C con SHA-256 por arquitectura; no se usa el paquete APT de ttyd.

No se agregan todavía `naabu` (libpcap/CGO), `feroxbuster` (Rust) u otros binarios descargados de releases hasta tener checksum y validación de arquitectura. `openssh-sftp-server` puede permanecer como dependencia transitiva de `openssh-server`, pero el subsistema SFTP está deshabilitado en `sshd_config`.

## Acceso

- `tester`: shell Bash/Zsh, UID 1000, sin grupos elevados; único usuario operativo.
- No existe una cuenta Unix `transfer` ni una cuenta Unix `proxy`.
- SFTP está desactivado; el workspace se usa desde la shell.
- `sshd`: escucha internamente en `2222`; no se publica con `ports:`.
- `ttyd`: escucha internamente en `7681`; no se publica con `ports:`.
- Host keys: persistidos en el volumen `lab-state`.
- Credenciales: se leen de `/run/secrets/lab.env`; no se imprimen en logs.
- `ttyd` mantiene el acceso web como defensa secundaria; Tailscale seguirá siendo la barrera principal.

## Comandos

Construir:

```text
make build-light
```

Levantar el servicio completo:

```text
make compose up
```

Abrir una shell como `tester` sin iniciar sshd/ttyd:

```text
make compose shell
```

Detener:

```text
make compose down
```

`make compose up` exige `TTYD_PASSWORD` y `SSH_PUBLIC_KEY` en `.env`. El archivo vacío no permite iniciar el servicio porque el entrypoint falla cerrado.

## Verificación realizada

- Build ARM64 y build AMD64 desde digests Ubuntu fijados.
- `fzf` 0.74.4: commit, Go 1.25.13, `x/sys` 0.44.0 y hashes ARM64/AMD64 coinciden con `supply-chain/tools.lock.yaml`.
- `ttyd` 1.7.7: hash ARM64/AMD64 validado durante el build.
- Scout no detecta vulnerabilidades Critical/High en `light` ARM64 ni AMD64.
- El escaneo completo de ARM64 reporta 39 Medium y 9 Low en paquetes Ubuntu del snapshot; se mantienen pendientes de una actualización con correcciones disponibles.
- `tester` no pertenece a `sudo` ni a grupos elevados.
- SSH con clave pública: correcto.
- SSH con contraseña: bloqueado.
- SFTP: desactivado y no disponible mediante `sshd`.
- ttyd acepta credencial correcta y rechaza la incorrecta.
- El contenedor no tiene puertos Docker publicados.
- `nmap -sT` funciona como usuario `tester`.
- `subfinder`, `httpx`, `katana`, `nuclei`, `ffuf`, `gobuster` y `dalfox`
  están presentes en `light` ARM64 y AMD64; `subfinder` reporta v2.16.0 y
  `nuclei` v3.11.1; los hashes de ambas arquitecturas coinciden con
  `supply-chain/tools.lock.yaml`; `pt-tools` lista las 7 nuevas.
- `read_only=true`, `CapDrop=ALL` y `no-new-privileges=true` activos.
- `make verify`, Actionlint, validación de pins y `docker compose config` pasan.

## Pendiente de fase 3

- `naabu` (libpcap/CGO) y `feroxbuster` (toolchain Rust).
- Nuclei templates versionados.
- wordlists controladas.
- Pruebas de humo nativas AMD64, no solo build y ejecución básica bajo QEMU.
- Actualizar el snapshot Ubuntu cuando existan correcciones para los hallazgos Medium/Low.
- Tailscale y proxy se incorporan en fases posteriores.
