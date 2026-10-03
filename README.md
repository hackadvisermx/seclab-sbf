# seclab-sbf

Laboratorio privado de pentesting en contenedores, con terminal interactiva, SSH, herramientas base y VPN bajo demanda.

El objetivo es que el usuario `tester` trabaje dentro del contenedor y solicite el túnel VPN que necesite sin convertir el laboratorio en un proxy abierto ni ejecutar una VPN en el host.

## Estado actual

| Fase | Estado | Alcance |
|---|---|---|
| 0 | Completada | Decisiones, threat model y matriz de compatibilidad |
| 1 | Completada | Supply chain, lockfiles, Gitleaks, escaneo de imagen y workflows |
| 2 | Completada | Compose, workspace, secretos y healthchecks |
| 3 | Completada v1 | Imagen Ubuntu `base` y la del laboratorio, build nativo arm64 y amd64 |
| 4 | Completada v1 | Zsh, Oh My Zsh, fzf, zoxide, banner, herramientas y tmux |
| 5 | Completada v1 | VPN inside, TUN, socket autenticado, aliases y sanitización |
| 6 | Completada v1 | `pt-forward` TCP, `pt-socks` SOCKS5, `pt-web` HTTP/WebSocket y route guard; puente host-only validado en VPS |
| 6.5 | Completada v1 | Política nftables y contrato Tailscale host-only; aplicada y persistente en el host OCI final |
| 7 | Completada v1 en arm64 | Imagen `full` con Metasploit, `nxc`, `john`, `hashcat`, `bettercap`, `s3scanner`, `wpscan` y forense; Ghidra/reversing quedan diferidos |
| 8 | Stacks validados | Terraform OCI/Azure/DO con `fmt`/`validate`; falta `apply` con credenciales reales |
| 9 | Parcial | nftables aplicado en el host OCI y jail de sshd con fail2ban; faltan ACL/MFA/approval de Tailscale y pruebas externas |
| 10 | Parcial | CI de seguridad, gate local de CVEs y runbooks; falta backup automático, alertas y disaster recovery |

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

### Atajo `lab` (opcional)

`scripts/lab` es un ejecutable que delega en `make -C`, así que sirve para no
recordar la ruta del repo. Se instala con enlaces simbólicos en un directorio
del `PATH` y no necesita tocar el `.zshrc`:

```bash
mkdir -p ~/bin
ln -s "$PWD/scripts/lab" ~/bin/lab
ln -s "$PWD/scripts/lab" ~/bin/labsh      # atajos opcionales
ln -s "$PWD/scripts/lab" ~/bin/labtmux
ln -s "$PWD/scripts/lab" ~/bin/labws
```

A partir de ahí, y desde cualquier carpeta:

```bash
lab compose-up          # equivalente a make compose-up
lab workspace-list
labsh                   # equivalente a lab compose-shell
labtmux
labws
lab                     # sin argumentos, muestra la ayuda
```

El repo se resuelve siguiendo el enlace simbólico en sí mismo, así que el
atajo sobreviva a que muevas el repo; si lo mueves, rehaz el `ln -s`.
`SECLAB_DIR` tiene prioridad si necesitas fijarlo a mano.

### El workspace sigue a la carpeta desde la que lanzas `lab`

El workspace es la carpeta en la que trabajas, y con `lab` es la desde la que
lo invoques, no la del repo:

```bash
cd ~/proyectos/mi-engagement
lab up            # crea ~/proyectos/mi-engagement si no existe y lo monta
lab               # más tarde, desde esa misma carpeta
```

- Si la carpeta ya existe, se monta tal cual y no se toca su contenido.
- Si no existe, se crea y se siembra con la estructura inicial
  (`README.md`, `engagements/_plantilla.md`, `retos/_plantilla.md`).

Esto se decide en `scripts/lab`, que pasa el workspace ya como ruta absoluta.
Hace falta porque cada receta del Makefile hace `cd` a la raíz del repo antes
de correr: sin absolutizar, un workspace relativo acabaría siempre dentro del
repo y `lab up` desde otra carpeta montaría el workspace equivocado sin
avisar.

Dos consecuencias prácticas:

- Si lanzas `lab` desde dos carpetas distintas tienes **dos workspaces**, no
  uno. Es lo que hace que el material se quede donde trabajas, pero conviene
  saberlo antes de extrañar algo.
- `lab` no crea la carpeta por su cuenta. Lo hace `make workspace-dir`, que
  además es quien la siembra. Por eso `lab` sin argumentos, que solo muestra la
  ayuda, no deja directorios sueltos.

Para fijar el workspace a mano, en vez de seguir la carpeta de invocación:

```bash
SECLAB_WORKSPACE_DIR=~/material lab up
```

Con `make` directamente el comportamiento no cambia: `WORKSPACE_DIR` sigue
siendo `./workspace` dentro del repo.

## Imagen publicada en Docker Hub

La imagen del laboratorio se publica en `hackadvisermx/seclab-sbf`, **pública**,
para que el host de la nube no tenga que compilar 4.9 GB en un VPS de 4 GB.

```bash
# En tu máquina, después de build-full:
make scan-image              # el gate de CVEs, siempre antes de publicar
make image-publish           # publica la base y la final, y muestra el digest
```

El `docker login` se hace **solo en tu máquina**. El host de la nube nunca tiene
credenciales de escritura: si lo compromisingen, no pueden publicar una imagen
manipulada.

En el host, la imagen se baja **por digest**, nunca por tag:

```bash
make image-pull DOCKER_DIGEST=sha256:...
make scan-image              # el gate se corre AQUÍ, en el host
```

Un tag se puede republicar con otro contenido; un digest no cambia nunca. Por eso
el host no hace pull de `latest`: así sigue viendo exactamente la imagen que
publicaste aunque alguien mueva el tag.

En el host, además, `IMAGE_SOURCE=remote` en su `.env` hace que `ensure-image`
**falle con instrucciones** en vez de compilar. Es la garantía de que el host no
vuelve a compilar por su cuenta.

Para el día a día en el portátil no cambia nada: `make build-full` compila local y
`make scan-image` revisa lo que vas a usar.

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
make vpn-tun-check VPN_DIR=./vpn VPN_MODE=inside
make vpn-doctor VPN_DIR=./vpn VPN_MODE=inside
make vpn-status VPN_DIR=./vpn VPN_MODE=inside
```

`vpn-up` es idempotente y deja preparado el daemon/TUN; no inicia una VPN por sí solo. `VPN_MODE=host` queda únicamente como compatibilidad explícita y no se usa en el flujo normal.

## SSH y tmux

`make keys` genera un par Ed25519 local para `tester`:

```text
.secrets/ssh/seclab_ed25519       # privado, 0600, ignorado
.secrets/ssh/seclab_ed25519.pub   # público
```

El archivo privado nunca se monta en el contenedor. La clave se configura mediante `SSH_PUBLIC_KEY`; SFTP está desactivado y no existe una cuenta SFTP separada. El acceso SSH usa únicamente claves y shell con Zsh/tmux.

`.tmux.conf` se copia a `/home/tester/.tmux.conf` durante el build con permisos `0444` y propietario `root`. El estado de plugins de TPM vive en `/tmp/tmux-plugins`, porque el rootfs es read-only.

## Proxy controlado

`pt-forward`, `pt-socks` y `pt-web` ejecutan como `tester` y escuchan únicamente en `127.0.0.1`. Cada conexión exige una VPN activa y una ruta real mediante `tun0`; se bloquean loopback, metadata, Tailscale, gateways Docker y destinos fuera de la tabla VPN. No existe un usuario `proxy` independiente: es una interfaz controlada, no una frontera contra el propio `tester`, y el refuerzo de red es nftables en el host.

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
make proxy-status
make proxy-doctor
make proxy-stop
```

En Linux, las comprobaciones de host se ejecutan sin aplicar nada:

```bash
make security-check
make tailscale-check
make fail2ban-check
```

La plantilla `security/policies/nftables-lab.nft` y el contrato host-only de
Tailscale están en `security/`; Docker Desktop/macOS omite esos checks y
devuelve `skipped`.

## Seguridad y límites

- No se publican puertos Docker.
- No se usa `privileged`, `docker.sock` ni `network_mode: host`.
- El acceso administrativo previsto es por Tailscale/SSH/ttyd privado.
- No se comparten claves privadas, `.env`, `.ovpn`, `salida/` ni `tmp/`.
- La plantilla nftables y la ruta NAT gateway de OCI fueron validadas y aplicadas en el host final; el puente host-only del proxy (`scripts/host/pt-proxy-bridge.sh`) está validado en un VPS, pero todavía no habilitado en el host OCI final.
- El `sshd` del host está cubierto por una jail de fail2ban con `banaction = nftables-multiport` y bans por IP, nunca por subred del tailnet. No cubre el `sshd` del contenedor. Ver [`docs/phase-9.md`](docs/phase-9.md).
- Usa únicamente objetivos y perfiles VPN autorizados.
- Dentro del contenedor **no hay `sudo` ni `su`**: el rootfs es de solo lectura y `tester` no tiene password. Es deliberado, para que la imagen siga siendo auditable. Para añadir herramientas, ver [`docs/agregar-tools.md`](docs/agregar-tools.md).

## Verificación

```bash
make verify
make smoke-test
make build-full
make compose-config ENV_FILE=.env.example
go run github.com/rhysd/actionlint/cmd/actionlint@v1.7.12
make sbom
make tf-fmt
make tflint-check
make fail2ban-jail-check
make tf-render-check
make fail2ban-check
```

Resultados verificados actualmente:

- Builds nativos `linux/arm64` y `linux/amd64`, sin registry: cada máquina construye la suya. El de amd64 se comprobó desde el portátil arm64 con `make build-full BUILD_PLATFORM=linux/amd64 BUILD_TAG=-amd64`: 0 Critical/High y hashes de `ttyd` y `dalfox` idénticos a los del lockfile.
- `make scan-image`: 0 vulnerabilidades Critical/High en las imágenes probadas.
- `make sbom`: emite el SBOM CycloneDX 1.7 en `tmp/sbom/`, con el nombre ligado a la imagen y a su hash de insumos. Verificado en `light` (1.390 componentes) y en `full` (1.969).
- `make smoke-test`: valida en contenedor efímero los permisos de `/workspace` para `tester`, la carga limpia de Zsh interactivo con `pt-help`, runtimes de Python/Ruby/Perl, respuesta de herramientas ofensivas clave y el estado del proxy `pt-forward`.
- TUN, `NET_ADMIN` y `tun0` presentes en Docker Desktop macOS.
- `vpntry` real validado con `tryhackme.ovpn`.
- Rutas por defecto y DNS sin cambios; `vpn-disconnect` limpia el túnel.
- `pt-forward`/`pt-socks`/`pt-web` bloquean destinos sin VPN, permiten rutas `tun0` y se detienen al desconectar la VPN.
- `pt-web` rechaza absolute-form y permanece loopback. El consumo externo se resuelve con el puente host-only más `ssh -L` sobre Tailscale, validado de extremo a extremo en un VPS el 2026-09-25; habilitarlo en el host OCI final queda como paso de despliegue. La sintaxis, el smoke `prerouting` y la persistencia systemd de nftables fueron validados en el host final.
- `make verify` (Gitleaks, Hadolint, ShellCheck y pines de Actions) pasa con 0 errores y 0 avisos.
- `make tf-fmt` y `terraform -chdir=terraform/stacks/<stack> validate` pasan en OCI, Azure y DigitalOcean sin `apply`, y los tres corren igual en CI.
- `make tflint-check` pasa en los tres stacks con el ruleset `terraform` embebido, sin plugins del registro. Requiere `tflint` instalado; sin él sale `unavailable`.
- `STACK=oci make tf-destroy-check` imprime el plan del stack y sale con código 1 si va a destruir algo **o si el nodo ya no existe**. No aplica nada. El nodo de OCI no existe desde 2026-09-29: se destruyó al reemplazarlo y no se pudo recrear por falta de cuota de shape. La red sigue intacta; el workspace es ahora una carpeta del disco, no un volumen; ver [`docs/phase-8.md`](docs/phase-8.md). Existe porque el nodo de OCI lleva `metadata.user_data`, que el provider trata como inmutable: un cambio en el cloud-init lo reemplaza entero.
- `make fail2ban-jail-check` valida la jail de sshd con el propio fail2ban, en un contenedor desechable, sin necesidad de un nodo. Verificado en local y en CI: la jail es válida y el filtro cuenta los cinco fallos de un ataque sin contar los logins correctos. **El ban efectivo en nftables sigue sin comprobarse** y necesita un host Linux; ver [`docs/phase-9.md`](docs/phase-9.md).
- `make tf-render-check` renderiza el cloud-init compartido y comprueba que sigue siendo YAML válido y que la jail de fail2ban llega al host idéntica al repo. Es la única verificación que cubre el render: `validate` pasa aunque la plantilla produzca YAML roto.

## Estructura principal

```text
images/                 Dockerfiles base y full
compose*.yaml           servicios lab y VPN
scripts/                entrypoints, healthchecks, VPN, proxy, host, nube y claves locales
shell/                  Zsh, tmux y pentest-lab
security/               nftables, fail2ban, unidades systemd, Tailscale, Trivy y SSH
supply-chain/           lockfiles de acciones, shell y herramientas
terraform/              stacks OCI, Azure y DigitalOcean
docs/                   decisiones por fase, runbooks, backups, acceso y tools
plan.md                 fuente de verdad del producto
vpn/                    perfiles locales ignorados
workspace-seed/         estructura inicial del workspace (la siembra make)
salida/                 material exportado con make workspace-export (ignorado)
```

## Flujo Git

El repositorio sigue una rama por fase:

```text
phase/<numero>-<slug>
```

No se modifica `main` directamente. Cada fase debe terminar en un Pull Request con pruebas, riesgos, CVEs y limitaciones conocidas. El baseline actual está en `bootstrap/baseline`; no se hizo merge directo a `main`.

## Runbooks

Si algo falla, `docs/runbooks.md` tiene el procedimiento por síntoma, no por
componente: acceso perdido, Tailscale caído, TUN ausente, proxy que no
conecta, fail2ban que te baneó, y destrucción del nodo. Los backups del
workspace están en `docs/backups.md`, incluida su restauración.

## Siguientes pasos

1. Rotar y revocar el material sensible expuesto en metadata previa.
2. Habilitar el puente host-only del proxy en el host OCI final.
3. Probar los perfiles `hackthebox` y `client` autorizados.
4. Ejecutar la matriz nativa Linux: TUN, `make security-check` y `make tailscale-check`.
5. Cerrar la Fase 9: ACL, MFA y device approval de Tailscale, fail2ban y pruebas externas controladas.
6. Cerrar la Fase 10: backup del workspace, alertas y disaster recovery.
7. Ejecutar `make tf-apply-*` con credenciales reales del operador y verificar la destrucción.
