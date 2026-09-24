# Pentest Lab Container — Plan de diseño e implementación

## 1. Objetivo

Construir un laboratorio reutilizable para:

- Pentesting autorizado y bug bounty.
- CTFs de CTFtime, picoCTF y plataformas similares.
- TryHackMe y Hack The Box mediante VPN.
- Engagements con clientes mediante VPN.
- Terminal web y SSH para un único usuario `tester`.
- Ejecución local y despliegue en OCI, Azure y DigitalOcean.
- Arquitecturas `linux/amd64` y `linux/arm64`.

El contenedor no será una distribución basada en Kali ni Parrot. Las herramientas se instalarán directamente desde sus fuentes upstream, con versiones controladas.

## 2. Decisiones confirmadas

- Base: Ubuntu 24.04 minimal.
- Perfiles: `light` y `full`.
- `full` se ejecuta en una VM dedicada desechable.
- Terminal web: `ttyd`.
- Acceso remoto: Tailscale.
- SSH dentro del contenedor mediante OpenSSH, con un único usuario Unix `tester`.
- SFTP desactivado; no existe una cuenta separada de transferencia.
- Workspace local: `./workspace` montado en `/workspace`.
- El workspace comienza vacío y no se crean subcarpetas automáticamente.
- Credenciales de ejecución: `.env` local no versionado.
- Credenciales de bootstrap/cloud: `deploy/.env` separado.
- Oh My Zsh con plugins seleccionados y pinneados.
- VPN: tres perfiles gestionados.
- Proxy: capacidad controlada de `tester` con forwarding TCP, SOCKS5 y reverse proxy web; no existe una cuenta Unix `proxy`.
- Terraform: VM + Docker, sin Kubernetes.
- Estado Terraform: backend nativo por proveedor.
- Política de CVEs: basada en riesgo.
- Repositorio: `hackadvisermx/seclab-sbf` en GitHub.
- Imágenes: `ghcr.io/hackadvisermx/seclab-sbf`.
- Full: VM desechable, sin otros servicios ni credenciales.

## 3. Arquitectura

```text
Host local o VPS
├── Tailscale
├── Firewall del host
├── Docker
├── Estado persistente
│   ├── SSH host keys
│   ├── Estado de Tailscale
│   └── Logs/estado internos
├── Bind mount
│   └── ./workspace -> /workspace
├── .env de ejecución
│   └── Montado en modo lectura, fuera del workspace
└── /vpn
    ├── tryhackme.ovpn
    ├── hackthebox.ovpn
    └── client.ovpn

Contenedor
├── entrypoint
├── OpenSSH
├── ttyd
├── OpenVPN bajo demanda
├── Fail2ban opcional para el sshd interno
├── Proxy Lab
└── tmux -> Zsh + Oh My Zsh + pentest-lab
```

### Reglas de exposición

- Ningún puerto del contenedor se publica en Internet.
- No se utiliza `network_mode: host` por defecto.
- No se monta `docker.sock`.
- No se montan el home, `/`, claves SSH ni credenciales del host.
- Tailscale se ejecuta en el host, no dentro del contenedor.
- `ttyd` se enlaza a loopback o a un proxy privado del host.
- SSH y la capacidad de proxy se consumen mediante Tailscale y túneles privados del host.
- Los puertos de proxy no se publican mediante `ports:`.

## 4. Estructura del repositorio

```text
.
├── compose.yaml
├── compose.local.yaml
├── compose.cloud.yaml
├── Dockerfile
├── Makefile
├── .env.example
├── .gitignore
├── images/
│   ├── base/
│   ├── light/
│   └── full/
├── scripts/
│   ├── entrypoint/
│   ├── vpn/
│   ├── proxy/
│   ├── health/
│   └── cloud/
├── shell/
│   ├── zsh/
│   ├── oh-my-zsh/
│   └── plugins/
├── supply-chain/
│   ├── tools.lock.yaml
│   ├── shell.lock.yaml
│   └── sbom/
├── security/
│   ├── vuln-exceptions.yaml
│   ├── ssh/
│   ├── tailscale/
│   └── policies/
├── terraform/
│   ├── modules/
│   └── stacks/
│       ├── oci/
│       ├── azure/
│       └── digitalocean/
└── .github/
    └── workflows/
```

## 5. Imágenes

### `base`

Incluye solamente:

- Ubuntu 24.04.
- `zsh`, `git`, `curl`, `jq`, `ca-certificates`.
- `tmux`, `tini`, `less`, `vim`/`nvim` si está disponible.
- `ripgrep`, `fd`, `fzf`.
- Runtime de Python, Go y Rust solo si es necesario para las herramientas.
- OpenSSH server.
- `ttyd`.
- Utilidades de sistema.

No incluye herramientas ofensivas grandes ni exploits.

### `light`

Herramientas de:

- Reconocimiento: `nmap`, `naabu`, `subfinder`, `httpx`, `katana`.
- Web: `ffuf`, `feroxbuster`, `gobuster`, `sqlmap`, `dalfox`.
- CTF: pwntools, herramientas forenses básicas y utilidades de encoding.
- Nuclei con plantillas versionadas y controladas.
- OpenVPN y utilidades de VPN.
- Wordlists pequeñas o descargadas bajo demanda.

No incluye Metasploit, Ghidra, John jumbo, hashcat GPU, wordlists gigantes ni exploit frameworks pesados.

### `full`

Se construye desde `light` y añade:

- Metasploit Framework.
- Ghidra headless.
- Rizin.
- John.
- Hashcat CPU.
- Wordlists grandes.
- Nuclei templates completos.
- Repositorios de exploit y payloads.
- Herramientas de reversing adicionales.

El perfil `full` no debe ejecutarse en un host compartido. Se ejecutará en una VM dedicada y desechable.

### ARM y AMD

Se publicarán manifests y pruebas para:

- `linux/amd64`.
- `linux/arm64`.

El build se verificará en hardware ARM nativo, no solo mediante compilación emulada. Si alguna herramienta no soporta ARM, se publicará una variante explícita en lugar de eliminarla silenciosamente.

## 6. Cadena de suministro y CVEs

No se utilizará `latest` como versión de producción.

### Lockfiles

- `tools.lock.yaml`: nombre, versión, fuente, hash, firma, licencia y arquitectura.
- `shell.lock.yaml`: Oh My Zsh y plugins con commit exacto.
- Versiones de Terraform y providers bloqueadas con `terraform.lock.hcl`.
- Imágenes base fijadas por digest.

### Instalación segura

- No se usará `curl | bash`.
- No se instalarán scripts de terceros sin revisión.
- Las releases se verificarán mediante SHA-256 y firma cuando estén disponibles.
- Las herramientas sin firma se compilarán desde commit exacto o se documentará la excepción.
- No se harán actualizaciones automáticas dentro del contenedor.
- Las actualizaciones llegarán mediante PR de Renovate o Dependabot.

### Gates de publicación

- Bloqueo de CVEs críticos.
- Bloqueo de CVEs altas explotables o expuestas.
- Excepciones solo con responsable, justificación, control compensatorio y expiración.
- No se permite un archivo de ignorancia global sin vencimiento.
- Escaneo del código fuente, lockfiles, SBOM, imagen final, scripts, Dockerfiles, Terraform y GitHub Actions.

Herramientas de escaneo:

- `trivy`
- `grype`
- `osv-scanner`
- `syft`
- `gitleaks`
- `hadolint`
- `shellcheck`
- `actionlint`
- `tflint`
- `tfsec` o Checkov
- `govulncheck`
- `cargo audit`
- `pip-audit`

### Evidencia de publicación

- SBOM CycloneDX/SPDX.
- Provenance BuildKit.
- Imagen firmada con Cosign.
- Digest inmutable en GHCR.
- Deploy únicamente por digest.
- Verificación de firma y attestation antes de iniciar el contenedor.

No se puede garantizar ausencia absoluta de CVEs. La garantía será que no existan vulnerabilidades críticas o altas explotables sin una excepción aprobada y vigente.

## 7. Acceso web, SSH y capacidad de proxy

### ttyd

- Terminal web privada.
- Tailscale como autenticación principal.
- ACL de Tailscale predeterminada en modo deny.
- MFA y device approval activos.
- Credencial adicional desde `.env` como defensa en profundidad.
- Sin exposición pública.
- Límite de clientes y sesiones.
- Sin historial de comandos sensible.
- `NO_COLOR` y fallback sin ANSI.

### SSH

Usuario previsto:

```text
tester     -> shell + tmux + capacidad controlada de proxy
```

No existen usuarios Unix `transfer` ni `proxy`. SFTP está desactivado y el acceso al workspace se realiza desde la shell.

Configuración:

- `PermitRootLogin no`.
- `PasswordAuthentication no`.
- `AuthenticationMethods publickey`.
- `AllowUsers tester`.
- `MaxAuthTries 3`.
- `MaxSessions` limitado.
- Sin X11.
- Sin agent forwarding.
- Sin túneles SSH arbitrarios ni reenvío TCP.
- Host keys persistentes.
- Claves públicas desde `.env`.
- Sin claves privadas en el servidor.

El usuario `tester` inicia en `/workspace` y reutiliza la misma sesión tmux que ttyd.

## 8. `.env` y secretos

Existirán dos archivos con propósitos separados:

```text
.env
```

Contiene credenciales de ejecución:

- Usuario y contraseña de ttyd.
- Usuario y clave pública SSH de `tester`.
- Rutas de perfiles VPN.
- Configuración de workspace.

```text
deploy/.env
```

Contiene solamente secretos de bootstrap e infraestructura:

- Auth key de Tailscale.
- Credenciales de Terraform.
- Configuración de backend remoto, si no se usan OIDC.

Reglas:

- Ambos archivos están fuera de Git.
- Permisos `600`.
- Solo `.env.example` se versiona.
- `gitleaks` y GitHub secret scanning son obligatorios.
- No usar `source .env` ni `eval`.
- Las claves autorizadas se escriben temporalmente en `/run/ssh`.
- El runtime no conserva secretos en archivos de imagen.
- Las claves privadas permanecen en el cliente.
- El `.env` de ejecución se copia a la VM después del `terraform apply` mediante Tailscale.
- El contenido de `.env` no se incluye en Terraform state, cloud-init ni planes.

La contraseña de ttyd no sustituye Tailscale ACL/MFA.

## 9. Workspace

El workspace local será:

```text
./workspace:/workspace
```

Reglas:

- `WORKDIR /workspace`.
- El directorio debe existir antes del despliegue.
- No se crea automáticamente una estructura de subcarpetas.
- No se monta el directorio actual completo.
- El workspace es el único lugar de trabajo del usuario.
- Las herramientas pueden escribir aquí, por lo que se recomienda no usarlo como repositorio de producción.
- Las flags, reports, wordlists y evidencias deben tratarse como datos sensibles.

En cloud se montará un volumen cifrado del proveedor:

```text
/srv/pentest/workspace:/workspace
```

El volumen será independiente del disco del sistema y tendrá snapshots o backups.

## 10. Tailscale

Tailscale será la única vía de acceso al contenedor del VPS.

### Bootstrap

Para cada VPS:

1. Generar una auth key one-off.
2. Aplicar tag `tag:pentest-lab`.
3. Configurarla como pre-approved.
4. Asignar expiración corta.
5. Usarla una sola vez.
6. Verificar el nodo en el tailnet.
7. Revocar la auth key.
8. Eliminar manualmente el nodo al destruir la VM.

No se usarán claves de autenticación reutilizables.

La key se almacenará en `deploy/.env`, no en la imagen ni en el `.env` del contenedor.

### Estado

- Estado de Tailscale persistente en el host.
- El contenedor no ejecuta Tailscale.
- No se habilita Funnel.
- No se habilitan Exit Node ni subnet routes del VPS.
- El nombre del nodo incluye proveedor y entorno.
- La ACL solo permite acceso desde los dispositivos autorizados.

Para la VPS:

- No se asignará IP pública si el proveedor lo permite.
- Se permitirá la salida necesaria para Tailscale.
- No se abrirán puertos entrantes públicos.
- El acceso web y SSH se realiza desde el tailnet.

## 11. Firewall y protección del VPS

La protección principal es no exponer puertos.

### Capas

- Oracle Security List.
- Azure NSG.
- DigitalOcean Cloud Firewall.
- `nftables` en el host.
- Reglas `DOCKER-USER` para Docker.
- Tailscale ACL.
- MFA y device approval.
- SSH key-only.
- `fail2ban`.

No se permitirá como única protección:

```text
0.0.0.0/0 -> 22
0.0.0.0/0 -> 2222
0.0.0.0/0 -> 7681
0.0.0.0/0 -> proxy
```

### Fail2ban

Fail2ban se instalará como control secundario:

- Host: jail para SSH administrativo.
- Contenedor: jail para SSH interno.
- Backend journald.
- Baneo incremental.
- `maxretry` bajo.
- Alertas por journald.
- Sin bloqueo de tráfico saliente de las pruebas.

Fail2ban no se utilizará como sustituto del firewall ni como detector genérico de escaneo de puertos.

### SSH hardening

- Root deshabilitado.
- Contraseñas deshabilitadas.
- `MaxAuthTries 3`.
- `LoginGraceTime` reducido.
- `AllowUsers` explícito.
- Forwarding SSH deshabilitado; la capacidad de proxy usa un comando controlado y privado.
- Servicios innecesarios deshabilitados.
- Metadata cloud bloqueada.
- Gateway Docker bloqueado desde el contenedor.

## 12. VPN

Los perfiles se almacenarán fuera de la imagen:

```text
/vpn/tryhackme.ovpn
/vpn/hackthebox.ovpn
/vpn/client.ovpn
```

### Alias

```text
vpntry -> tryhackme.ovpn
vpnhtb -> hackthebox.ovpn
vpncli -> client.ovpn
```

Comandos comunes:

```text
vpn-connect <perfil>
vpn-status
vpn-disconnect
vpn-list
vpn-switch
```

### Seguridad VPN

- Montar `.ovpn` en modo lectura.
- No incluir certificados ni claves en la imagen.
- Eliminar o ignorar `redirect-gateway` no autorizado.
- No cambiar la ruta por defecto.
- No cambiar DNS global.
- Usar `route-nopull` o configuración sanitizada.
- Añadir solo rutas documentadas por cada proveedor.
- Mantener Tailscale y la terminal web operativos.
- Impedir conexiones simultáneas ambiguas.
- Limpiar rutas al desconectar.

### macOS, Linux y cloud

El flujo normal del tester será:

```text
VPN_MODE=inside
```

El daemon de control se inicia antes de la sesión, precrea `tun0` y no conecta OpenVPN hasta que el usuario `tester` ejecuta `vpntry`, `vpnhtb` o `vpncli`. En macOS, Docker Desktop debe exponer `/dev/net/tun` al contenedor; en Linux, el host debe exponer el dispositivo de caracteres. La prueba de prerrequisitos es `make compose vpn-tun-check`.

`VPN_MODE=host` queda como compatibilidad explícita, no como flujo normal, y no inicia un cliente VPN fuera del contenedor.

No se usará `--privileged` ni `mknod` como solución al problema de TUN.

## 13. Proxy Lab

El proxy solo permitirá destinos alcanzables a través de la tabla de rutas de la VPN activa. “Cualquier destino” significa cualquier destino de la VPN, no Internet público ni metadata cloud.

### Modos

```text
pt-forward   -> TCP explícito
pt-socks     -> SOCKS5
pt-web       -> HTTP/HTTPS/WebSocket reverse proxy
```

### Consumo local

En macOS y laptop:

```text
Mac -> Tailscale -> SSH -> contenedor -> VPN -> target
```

No se publicarán puertos Docker.

La capacidad de proxy se implementará como comandos controlados para `tester`, con sockets privados o listeners loopback autorizados y un route guard. No se usará forwarding SSH ni una cuenta Unix `proxy`; el firewall/nftables de la fase cloud reforzará la frontera de destinos. Con un único usuario, el route guard es una interfaz controlada y no una frontera contra `tester`, que conserva acceso de shell.

El reverse proxy utilizará Caddy dentro del contenedor y se consumirá mediante túnel SSH local.

### Control de destinos

Se rechazará:

- Conexiones sin VPN activa.
- Destinos fuera de la tabla VPN.
- Loopback.
- Tailscale.
- Host del contenedor.
- Gateway Docker.
- Metadata cloud.
- Destinos no autorizados por el perfil.

El cliente puede seleccionar cualquier destino de la red VPN, pero no puede convertir el proxy en un open proxy hacia Internet.

### Gestión

```text
pt-forward status
pt-forward stop
pt-forward clean
pt-forward doctor
```

Al desconectar una VPN se cancelarán sus forwards.

## 14. Oh My Zsh y experiencia de terminal

Oh My Zsh se instala desde commit exacto, nunca con `curl | sh`.

### Plugins nativos

```text
completion (integrado por el núcleo de Oh My Zsh)
git
tmux
ssh
extract
history
aliases
jsontools
```

### Plugins externos pinneados

```text
zsh-autosuggestions
zsh-syntax-highlighting
zsh-completions
zoxide
fzf
```

No se incluirán por defecto:

```text
web-search
pass
sudo
direnv
emoji
randemoji
command-not-found
plugins cloud
```

El plugin local `pentest-lab` proporcionará:

- `pt-help`.
- `pt-tools`.
- `pt-banner`.
- `pentest-reset`.
- Aliases VPN.
- Integración con tmux.
- Resumen de herramientas.

### Banner

- Banner ASCII colorido.
- Perfil `light` o `full`.
- Número de herramientas.
- Categorías resumidas.
- Alias VPN.
- Comando `pt-help`.
- Menos de 80 columnas.
- Respeta `NO_COLOR`, `TERM=dumb` y la ausencia de TTY.
- Se muestra una vez por sesión tmux.
- No se ejecuta ninguna herramienta de red durante el arranque.

### `pt-help`

Mostrará:

- Perfil activo.
- Herramientas disponibles.
- Categorías.
- Comandos de uso.
- VPN.
- SSH y ttyd; SFTP permanece desactivado.
- Workspace.
- Ejemplos de herramientas.
- Estado de seguridad.

El resumen se generará desde `tools.json`, no ejecutando `nmap --version` o consultas de red al iniciar.

## 15. Terraform

### Stacks

```text
terraform/stacks/oci
terraform/stacks/azure
terraform/stacks/digitalocean
```

Cada stack gestionará:

- VM.
- Red privada.
- Firewall.
- Volumen de workspace.
- Cloud-init.
- Docker.
- Tailscale.
- IAM mínimo.
- Tags.
- Outputs de conexión.

No se utilizará Kubernetes.

### Backends

- OCI: Object Storage nativo, versionado, locking y KMS.
- Azure: Blob Storage mediante backend `azurerm`, privado y cifrado.
- DigitalOcean: Spaces mediante backend S3-compatible, con lockfile.

Cada proveedor y entorno tendrá un state separado.

### Bootstrap

El despliegue se realizará en dos fases:

```text
terraform plan
terraform apply
```

Terraform no incluirá el `.env` de ejecución.

Después:

```text
scp .env usuario@<tailnet-host>:/opt/pentest-lab/.env
ssh usuario@<tailnet-host>
cd /opt/pentest-lab
docker compose up -d
```

La key Tailscale se usará solamente durante el bootstrap. El modo manual por consola será el método preferido para no introducir secretos en user-data o state.

### Protección del estado

- State remoto privado.
- Cifrado en reposo.
- Versionado.
- Locking.
- Sin state en Git.
- `sensitive` no se considera sustituto de protección del state.
- Credenciales de backend mediante environment/secret seguro.

## 16. CI/CD

### Pull request

- Secret scanning.
- `gitleaks`.
- `hadolint`.
- `shellcheck`.
- `actionlint`.
- `tflint`.
- `tfsec`/Checkov.
- `trivy fs`.
- `osv-scanner`.
- Build de prueba.
- Tests de shell.
- Terraform validate/plan.

### Main o tag

1. Build de imagen.
2. Build matrix AMD/ARM.
3. Smoke tests.
4. SBOM.
5. Escaneo de imagen.
6. Firmas.
7. Provenance.
8. Push a GHCR por digest.
9. Verificación de firma.
10. Deploy por digest.

### GitHub

- Actions fijadas por SHA.
- Permisos mínimos.
- OIDC para GHCR cuando sea posible.
- Sin secretos en PRs de forks.
- Branch protection.
- CODEOWNERS.
- No force-push.
- Tags de release firmadas.
- Rebuild journal para CVEs nuevas.

## 17. Comandos de operación

```text
make local-up
make local-down
make local-shell
make build
make scan
make doctor
make cloud-up-oci
make cloud-up-azure
make cloud-up-do
make tf-plan-oci
make tf-apply-oci
make env-copy-oci
make tf-destroy-oci
```

Dentro del contenedor:

```text
pt-help
pt-tools
pt-banner
pentest-health
pentest-doctor
pentest-reset
vpntry
vpnhtb
vpncli
vpn-status
vpn-disconnect
pt-forward
pt-socks
pt-web
pt-forward status
pt-forward stop
pt-forward doctor
```

## 18. Health checks

`pentest-doctor` verificará:

- Arquitectura.
- Digest de imagen.
- Permisos del workspace.
- Estado de `.env`.
- Tailscale.
- Ttyd.
- SSH.
- SFTP desactivado.
- Fail2ban.
- TUN disponible o modo host.
- Rutas VPN.
- DNS.
- Espacio en disco.
- Sesión tmux.
- Reglas de firewall.
- Ausencia de puertos públicos inesperados.
- Acceso a metadata cloud bloqueado.

## 19. Fases de implementación

### Fase 0 — Decisiones y documentación (completada)

- Cerrar nombres de perfiles.
- Definir `.env.example`.
- Definir matriz AMD/ARM.
- Documentar límites de macOS.
- Documentar threat model y registrar la matriz/estado en `docs/phase-0.md`.

### Fase 1 — Repositorio y supply chain (completada)

- Crear estructura del repositorio y registrar `docs/phase-1.md`.
- Crear lockfiles.
- Fijar imagen base por digest.
- Configurar GitHub Actions con Actions fijadas por SHA.
- Activar secret scanning mediante Gitleaks.
- Configurar SBOM, provenance y firma Cosign en el release.

### Fase 2 — Compose local y workspace (completada)

- Crear `compose.yaml` y `compose.local.yaml`.
- Montar `./workspace` sin crear subdirectorios automáticamente.
- Configurar `.env` como archivo de secretos de solo lectura.
- Crear `entrypoint` y healthcheck verificables.
- Añadir health checks.
- Validar el servicio local en Docker Desktop macOS.

### Fase 3 — Imagen `base` y `light` (v1 completada en ARM64; build AMD64 verificado)

- Construir `base` y `light` con snapshot de Ubuntu.
- Añadir ttyd, SSH y shell de `tester` sin SFTP.
- Añadir herramientas light oficiales de Ubuntu; compilar `fzf` desde commit fijo y registrar las upstream pendientes.
- Configurar no-root y capabilities.
- Ejecutar escaneo y smoke tests: Scout no reporta Critical/High en ARM64 ni AMD64; el escaneo completo conserva Medium/Low del snapshot Ubuntu pendientes de actualización.

### Fase 4 — Terminal, Zsh y banner (v1 completada en ARM64; build AMD64 verificado)

- Instalar Zsh y Oh My Zsh pinneado.
- Añadir plugins curated.
- Crear `pentest-lab`.
- Crear banner, `pt-help` y `pt-tools`.
- Integrar ttyd, SSH y tmux.
- Medir tiempo de arranque: smoke local de Zsh no interactivo menor a 0.4 s en ARM64.
- El banner respeta TTY, `NO_COLOR`, `TERM=dumb` y se marca una vez por sesión tmux.
- VPN y aliases funcionales quedan para Fase 5.

### Fase 5 — VPN (v1 completada; validación Linux/firewall pendiente)

- Crear gestor de perfiles.
- Añadir `vpntry`, `vpnhtb`, `vpncli`.
- Implementar validación de rutas.
- Validar TUN y la conexión real en macOS Docker Desktop cuando el dispositivo esté expuesto, y en Linux con TUN antes de release.
- Mantener `VPN_MODE=host` solo como compatibilidad explícita; no forma parte del flujo del tester.
- El modo inside usa un servicio opcional con `NET_ADMIN`, `CHOWN` para asignar el socket a `tester` y `/dev/net/tun`, nunca `--privileged`; un socket Unix autenticado permite que los aliases de `tester` soliciten solo acciones allowlistadas. `tryhackme.ovpn` fue validado en macOS Docker Desktop; la prueba nativa en Linux queda pendiente.

### Fase 6 — Proxy Lab

- Añadir `pt-forward`.
- Añadir SOCKS5.
- Añadir reverse proxy web.
- Añadir route guard para la capacidad de proxy de `tester`.
- Probar túneles desde macOS y VPS.

### Fase 7 — Imagen `full`

- Añadir Metasploit.
- Ghidra y reversing quedan diferidos; no forman parte de la iteración actual.
- Añadir herramientas pesadas.
- Crear matriz ARM/AMD.
- Ejecutar en VM desechable.

### Fase 8 — Terraform cloud

- Crear stacks OCI, Azure y DigitalOcean.
- Configurar states remotos.
- Crear firewalls.
- Crear volúmenes.
- Configurar cloud-init.
- Integrar Tailscale.
- Añadir scripts de bootstrap y destroy.

### Fase 9 — Seguridad cloud

- Instalar nftables.
- Configurar DOCKER-USER.
- Añadir fail2ban.
- Bloquear metadata.
- Deshabilitar IP pública cuando sea posible.
- Ejecutar pruebas externas controladas.

### Fase 10 — CI/CD y operación

- Activar gates de CVEs.
- Firmar y publicar imágenes.
- Crear releases por digest.
- Añadir backups y snapshots.
- Añadir alertas y runbooks.
- Ejecutar disaster recovery.

## 20. Criterios de aceptación

- Local funciona en macOS Docker Desktop.
- Linux y ARM tienen tests nativos.
- Cloud funciona en OCI, Azure y DigitalOcean.
- El contenedor no tiene puertos públicos.
- Solo Tailscale puede acceder a ttyd y SSH.
- SSH utiliza únicamente claves públicas.
- SFTP permanece desactivado.
- El workspace conserva archivos entre reinicios.
- ttyd y SSH reutilizan tmux.
- El banner aparece una vez por sesión.
- `pt-help` lista herramientas y aliases.
- `vpntry`, `vpnhtb` y `vpncli` son independientes.
- Las VPN no cambian la ruta por defecto.
- Los proxies solo alcanzan destinos de la VPN activa.
- Los proxies no alcanzan Tailscale, metadata o Docker.
- Fail2ban bloquea ataques de autenticación repetidos.
- Las imágenes tienen SBOM, provenance y firma.
- CVEs críticos no pueden publicarse.
- Terraform state está protegido y versionado.
- El `.env` nunca aparece en Git, imagen o logs.
- La VM puede destruirse sin dejar rastros de acceso.

## 21. Riesgos conocidos

- Docker Desktop en macOS requiere que `/dev/net/tun` esté expuesto al contenedor; si no está disponible, se usa un host Linux con TUN. No se resuelve con `privileged` ni `mknod`.
- Algunas herramientas full pueden no soportar ARM.
- Ghidra/Metasploit pueden tener alto consumo de memoria.
- Ghidra headless requiere Java y recursos adecuados.
- Hashcat será CPU-only inicialmente.
- Las VPN pueden cambiar rutas si no se sanitizan.
- Las claves de autenticación de Tailscale en Terraform state son un riesgo; se preferirán claves one-off o el bootstrap manual.
- El estado de Terraform contiene datos sensibles aunque use `sensitive`.
- Un contenedor no es un sandbox seguro frente a exploits de kernel.
- Los targets deben estar correctamente autorizados.
- El workspace contiene datos que requieren backup y limpieza.

## 22. Resultado esperado

El resultado será un contenedor portable, multi-arquitectura y reproducible que pueda ejecutarse con un comando local o desplegarse mediante Terraform en una VM privada. La interfaz principal será la terminal dentro de tmux, accesible por ttyd o SSH mediante Tailscale. Las herramientas se gestionarán mediante manifiestos fijados, los secretos mediante archivos `.env` protegidos, la VPN mediante perfiles nombrados y el acceso de red mediante reglas explícitas de firewall y Tailscale.
