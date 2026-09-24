# seclab-sbf

Laboratorio privado de pentesting en contenedores, con terminal interactiva, SSH, herramientas base y VPN bajo demanda.

El objetivo es que el usuario `tester` trabaje dentro del contenedor y solicite el túnel VPN que necesite sin convertir el laboratorio en un proxy abierto ni ejecutar una VPN en el host.

## Estado actual

| Fase | Estado | Alcance |
|---|---|---|
| 0 | Completada | Decisiones, threat model y matriz de compatibilidad |
| 1 | Completada | Supply chain, lockfiles, Gitleaks, SBOM/provenance y workflows |
| 2 | Completada | Compose, workspace, secretos y healthchecks |
| 3 | Completada v1 | Imagen Ubuntu `base`/`light`, ARM64 y build AMD64 |
| 4 | Completada v1 | Zsh, Oh My Zsh, fzf, zoxide, banner, herramientas y tmux |
| 5 | Completada v1 | VPN inside, TUN, socket autenticado, aliases y sanitización |
| 6 | En curso v1 | `pt-forward` TCP, `pt-socks` SOCKS5 y route guard; `pt-web` pendiente |
| 7 | Pendiente | Imagen `full`; Ghidra/reversing quedan diferidos |
| 8–10 | Pendiente | Terraform/cloud, nftables, Tailscale, fail2ban y operación |

La Fase 5 fue validada en Docker Desktop macOS ARM64 con TUN y un perfil oficial de TryHackMe. Las pruebas reales de los otros perfiles y la matriz nativa Linux siguen pendientes.

## Inicio rápido

### Requisitos

- Docker Desktop en macOS con `/dev/net/tun` expuesto al contenedor, o Docker Engine en Linux con TUN.
- GNU Make y Git.
- Al menos un perfil VPN autorizado en `vpn/`. Los archivos `.ovpn` no se versionan.

### Preparación local

```bash
make env-init                 # solo si .env no existe
make keys                     # genera .secrets/ssh/ y completa la clave pública
```

Edita `.env` y establece al menos `TTYD_PASSWORD` y `SSH_PUBLIC_KEY` si el generador no las completó. `.env` debe conservar permisos `600` y nunca se sube a Git.

### Levantar el laboratorio

```bash
make compose up
make compose tmux
```

`make compose up` levanta `tester`, el daemon VPN interno y `tun0`, pero no conecta ningún perfil. Dentro de la sesión tmux:

```text
pt-help
pt-tools
vpn-status
vpn-list
vpntry
```

`vpntry` conecta `tryhackme.ovpn`; también existen `vpnhtb` y `vpncli`. Después de trabajar:

```text
vpn-disconnect
```

Desde el host:

```bash
make compose down
```

## VPN

El flujo normal usa `VPN_MODE=inside`:

- `tester` contiene la sesión del usuario y comparte el namespace de red con el servicio root `vpn`.
- El servicio `vpn` precrea `tun0` y expone un socket Unix allowlistado.
- `vpntry`, `vpnhtb` y `vpncli` solicitan el túnel bajo demanda.
- El gestor genera una copia sanitizada en el volumen de estado; los perfiles originales permanecen fuera de la imagen.
- Se filtran `redirect-gateway`, `route-gateway` y opciones DNS; no se permite cambiar la ruta por defecto.
- El usuario `tester` no recibe root ni `NET_ADMIN`; OpenVPN se ejecuta en el servicio controlado.

Comandos adicionales:

```bash
make compose vpn-tun-check VPN_DIR=./vpn VPN_MODE=inside
make compose vpn-doctor VPN_DIR=./vpn VPN_MODE=inside
make compose vpn-status VPN_DIR=./vpn VPN_MODE=inside
```

`vpn-up` es idempotente y deja preparado el daemon/TUN; no inicia una VPN por sí solo. `VPN_MODE=host` queda únicamente como compatibilidad explícita y no se usa en el flujo normal.

## SSH, tmux y proxy controlado

`make keys` genera un par Ed25519 local para `tester`:

```text
.secrets/ssh/seclab_ed25519       # privado, 0600, ignorado
.secrets/ssh/seclab_ed25519.pub   # público
```

El archivo privado nunca se monta en el contenedor. La clave se configura mediante `SSH_PUBLIC_KEY`; SFTP está desactivado y no existe una cuenta SFTP separada. El acceso SSH usa únicamente claves y shell con Zsh/tmux.

La capacidad de proxy se expone para `tester` mediante `pt-forward` y un route guard; no existe un usuario `proxy` independiente. Es una interfaz controlada, no una frontera contra el propio `tester`: el firewall/nftables de la fase cloud será la barrera adicional para impedir destinos fuera de la VPN activa.

`.tmux.conf` se copia a `/home/tester/.tmux.conf` durante el build con permisos `0444` y propietario `root`. El estado de plugins de TPM vive en `/tmp/tmux-plugins`, porque el rootfs es read-only.

## Proxy controlado

`pt-forward` y `pt-socks` ejecutan como `tester` y escuchan únicamente en `127.0.0.1`. Cada conexión exige una VPN activa y una ruta real mediante `tun0`; se bloquean loopback, metadata, Tailscale, gateways Docker y destinos fuera de la tabla VPN.

```text
pt-forward start tcp <host> <port> [listen_port]
pt-socks [listen_port]
pt-forward status
pt-forward doctor
pt-forward stop
```

Ejemplos: `pt-forward start tcp 192.168.192.1 80 18080` y `pt-socks 1080`. El proxy se detiene automáticamente cuando se desconecta la VPN. `pt-web` todavía no está implementado.

Desde el host:

```bash
make compose proxy-status
make compose proxy-doctor
make compose proxy-stop
```

La route guard es una interfaz de uso, no una frontera contra `tester`; nftables/cloud queda como refuerzo de seguridad.

## Seguridad y límites

- No se publican puertos Docker.
- No se usa `privileged`, `docker.sock` ni `network_mode: host`.
- El acceso administrativo previsto es por Tailscale/SSH/ttyd privado.
- No se comparten claves privadas, `.env`, `.ovpn`, `workspace/` ni `tmp/`.
- Las rutas VPN se validan, pero el bloqueo de metadata, Tailscale, gateway Docker e interfaces del host requiere las reglas de firewall/nftables de las fases cloud.
- Usa únicamente objetivos y perfiles VPN autorizados.

## Verificación

```bash
make verify
make build-light
make compose config ENV_FILE=.env.example
go run github.com/rhysd/actionlint/cmd/actionlint@v1.7.12
docker scout cves local://seclab-sbf:light --only-severity critical,high --exit-code
```

Resultados verificados actualmente:

- Builds `linux/arm64` y `linux/amd64`.
- Scout: 0 vulnerabilidades Critical/High en las imágenes probadas.
- TUN, `NET_ADMIN` y `tun0` presentes en Docker Desktop macOS.
- `vpntry` real validado con `tryhackme.ovpn`.
- Rutas por defecto y DNS sin cambios; `vpn-disconnect` limpia el túnel.
- `pt-forward`/`pt-socks` bloquean destinos sin VPN, permiten rutas `tun0` y se detienen al desconectar la VPN.
- `pt-web` reverse proxy permanece pendiente.

## Estructura principal

```text
images/                 Dockerfiles base/light
compose*.yaml           servicios lab y VPN
scripts/                entrypoints, healthchecks, VPN, proxy y claves locales
shell/                  Zsh, tmux y pentest-lab
security/               configuración SSH
supply-chain/           lockfiles de acciones, shell y herramientas
docs/                   estado y decisiones por fase
plan.md                 fuente de verdad del producto
vpn/                    perfiles locales ignorados
workspace/              workspace local ignorado
```

## Flujo Git

El repositorio sigue una rama por fase:

```text
phase/<numero>-<slug>
```

No se modifica `main` directamente. Cada fase debe terminar en un Pull Request con pruebas, riesgos, CVEs y limitaciones conocidas. El baseline actual está en `bootstrap/baseline`; no se hizo merge directo a `main`.

## Siguientes pasos

1. Probar `pt-web` y endurecer la route guard con firewall/nftables.
2. Probar los perfiles `hackthebox` y `client` autorizados.
3. Ejecutar la matriz nativa Linux.
4. Retomar `full`, Terraform/cloud y Tailscale en fases posteriores.
