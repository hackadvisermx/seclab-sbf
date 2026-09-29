# seclab-sbf

Laboratorio privado de pentesting en contenedores, con terminal interactiva, SSH, herramientas base y VPN bajo demanda.

El objetivo es que el usuario `tester` trabaje dentro del contenedor y solicite el túnel VPN que necesite sin convertir el laboratorio en un proxy abierto ni ejecutar una VPN en el host.

## Estado actual

| Fase | Estado | Alcance |
|---|---|---|
| 0 | Completada | Decisiones, threat model y matriz de compatibilidad |
| 1 | Completada | Supply chain, lockfiles, Gitleaks, escaneo de imagen y workflows |
| 2 | Completada | Compose, workspace, secretos y healthchecks |
| 3 | Completada v1 | Imagen Ubuntu `base`/`light`, build nativo arm64 y amd64 |
| 4 | Completada v1 | Zsh, Oh My Zsh, fzf, zoxide, banner, herramientas y tmux |
| 5 | Completada v1 | VPN inside, TUN, socket autenticado, aliases y sanitización |
| 6 | Completada v1 | `pt-forward` TCP, `pt-socks` SOCKS5, `pt-web` HTTP/WebSocket y route guard; puente host-only validado en VPS |
| 6.5 | Completada v1 | Política nftables y contrato Tailscale host-only; aplicada y persistente en el host OCI final |
| 7 | Completada v1 en arm64 | Imagen `full` con Metasploit, `nxc`, `john`, `hashcat`, `bettercap`, `s3scanner`, `wpscan` y forense; Ghidra/reversing quedan diferidos |
| 8 | Stacks validados | Terraform OCI/Azure/DO con `fmt`/`validate`; falta `apply` con credenciales reales |
| 9 | Parcial | nftables aplicado en el host OCI y jail de sshd con fail2ban; faltan ACL/MFA/approval de Tailscale y pruebas externas |
| 10 | Parcial | CI de seguridad y gate local de CVEs; faltan backups/snapshots, alertas, runbooks y disaster recovery |

La Fase 5 fue validada en Docker Desktop macOS arm64 con TUN y un perfil oficial de TryHackMe. Las pruebas reales de los otros perfiles y la matriz nativa Linux siguen pendientes. La imagen `full` supera 2 GB y solo está validada en arm64.

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
make compose-up
make compose-tmux
```

`make compose-up` levanta `tester`, el daemon VPN interno y `tun0`, pero no conecta ningún perfil. Dentro de la sesión tmux:

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
make compose-down
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
make compose-vpn-tun-check VPN_DIR=./vpn VPN_MODE=inside
make compose-vpn-doctor VPN_DIR=./vpn VPN_MODE=inside
make compose-vpn-status VPN_DIR=./vpn VPN_MODE=inside
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

`pt-forward`, `pt-socks` y `pt-web` ejecutan como `tester` y escuchan únicamente en `127.0.0.1`. Cada conexión exige una VPN activa y una ruta real mediante `tun0`; se bloquean loopback, metadata, Tailscale, gateways Docker y destinos fuera de la tabla VPN.

```text
pt-forward start tcp <host> <port> [listen_port]
pt-socks [listen_port]
pt-web start <http-or-https-origin> [listen_port]
pt-forward status
pt-forward doctor
pt-forward stop
```

Ejemplos: `pt-forward start tcp 192.168.192.1 80 18080`, `pt-socks 1080` y `pt-web start http://192.168.192.1:80 18081`. `pt-web` acepta un origen fijo, rechaza absolute-form y permite WebSocket; el proxy se detiene automáticamente cuando se desconecta la VPN.

Desde el host:

```bash
make compose-proxy-status
make compose-proxy-doctor
make compose-proxy-stop
```

La route guard es una interfaz de uso, no una frontera contra `tester`; nftables/cloud queda como refuerzo de seguridad.

En Linux, las comprobaciones de host se ejecutan sin aplicar cambios:

```bash
make security-check
make tailscale-check
```

La plantilla `security/policies/nftables-lab.nft` y el contrato host-only de Tailscale están en `security/`; Docker Desktop/macOS omite esos checks.

## Seguridad y límites

- No se publican puertos Docker.
- No se usa `privileged`, `docker.sock` ni `network_mode: host`.
- El acceso administrativo previsto es por Tailscale/SSH/ttyd privado.
- No se comparten claves privadas, `.env`, `.ovpn`, `workspace/` ni `tmp/`.
- La plantilla nftables y la ruta NAT gateway de OCI fueron validadas y aplicadas en el host final; el puente host-only del proxy (`scripts/host/pt-proxy-bridge.sh`) está validado en un VPS, pero todavía no habilitado en el host OCI final.
- El `sshd` del host está cubierto por una jail de fail2ban con `banaction = nftables-multiport` y bans por IP, nunca por subred del tailnet. No cubre el `sshd` del contenedor. Ver [`docs/phase-9.md`](docs/phase-9.md).
- Usa únicamente objetivos y perfiles VPN autorizados.
- Dentro del contenedor **no hay `sudo` ni `su`**: el rootfs es de solo lectura y `tester` no tiene password. Es deliberado, para que la imagen siga siendo auditable. Para añadir herramientas, ver [`docs/agregar-tools.md`](docs/agregar-tools.md).

## Verificación

```bash
make verify
make build-light
make build-full
make compose-config ENV_FILE=.env.example
go run github.com/rhysd/actionlint/cmd/actionlint@v1.7.12
make scan-image SCAN_IMAGE=seclab-sbf:light
make sbom
make tf-fmt
make tflint-check
make fail2ban-jail-check
make tf-render-check
make fail2ban-check
```

Resultados verificados actualmente:

- Builds nativos `linux/arm64` y `linux/amd64`, sin registry: cada máquina construye la suya.
- `make scan-image`: 0 vulnerabilidades Critical/High en las imágenes probadas.
- `make sbom`: emite el SBOM CycloneDX 1.7 en `tmp/sbom/`, con el nombre ligado a la imagen y a su hash de insumos. Verificado en `light` (1.390 componentes) y en `full` (1.969).
- TUN, `NET_ADMIN` y `tun0` presentes en Docker Desktop macOS.
- `vpntry` real validado con `tryhackme.ovpn`.
- Rutas por defecto y DNS sin cambios; `vpn-disconnect` limpia el túnel.
- `pt-forward`/`pt-socks`/`pt-web` bloquean destinos sin VPN, permiten rutas `tun0` y se detienen al desconectar la VPN.
- `pt-web` rechaza absolute-form y permanece loopback. El consumo externo se resuelve con el puente host-only más `ssh -L` sobre Tailscale, validado de extremo a extremo en un VPS el 2026-09-25; habilitarlo en el host OCI final queda como paso de despliegue. La sintaxis, el smoke `prerouting` y la persistencia systemd de nftables fueron validados en el host final.
- `make verify` (Gitleaks, Hadolint, ShellCheck y pines de Actions) pasa; ShellCheck solo informa SC2329 en `scripts/entrypoint/light-entrypoint.sh` por una función `cleanup` invocada de forma indirecta.
- `make tf-fmt` y `terraform -chdir=terraform/stacks/<stack> validate` pasan en OCI, Azure y DigitalOcean sin `apply`, y los tres corren igual en CI.
- `make tflint-check` pasa en los tres stacks con el ruleset `terraform` embebido, sin plugins del registro. Requiere `tflint` instalado; sin él sale `unavailable`.
- `make fail2ban-jail-check` valida la jail de sshd con el propio fail2ban, en un contenedor desechable, sin necesidad de un nodo. Verificado en local y en CI: la jail es válida y el filtro cuenta los cinco fallos de un ataque sin contar los logins correctos. **El ban efectivo en nftables sigue sin comprobarse** y necesita un host Linux; ver [`docs/phase-9.md`](docs/phase-9.md).
- `make tf-render-check` renderiza el cloud-init compartido y comprueba que sigue siendo YAML válido y que la jail de fail2ban llega al host idéntica al repo. Es la única verificación que cubre el render: `validate` pasa aunque la plantilla produzca YAML roto.

## Estructura principal

```text
images/                 Dockerfiles base/light/full
compose*.yaml           servicios lab y VPN
scripts/                entrypoints, healthchecks, VPN, proxy, host, nube y claves locales
shell/                  Zsh, tmux y pentest-lab
security/               nftables, fail2ban, unidades systemd, Tailscale, Trivy y SSH
supply-chain/           lockfiles de acciones, shell y herramientas
terraform/              stacks OCI, Azure y DigitalOcean
docs/                   decisiones por fase, acceso y como anadir herramientas
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

1. Rotar y revocar el material sensible expuesto en metadata previa.
2. Habilitar el puente host-only del proxy en el host OCI final.
3. Probar los perfiles `hackthebox` y `client` autorizados.
4. Ejecutar la matriz nativa Linux: TUN, `make security-check` y `make tailscale-check`.
5. Cerrar la Fase 9: ACL, MFA y device approval de Tailscale, fail2ban y pruebas externas controladas.
6. Cerrar la Fase 10: backups/snapshots, alertas, runbooks y disaster recovery.
7. Ejecutar `make tf-apply-*` con credenciales reales del operador y verificar la destrucción.
