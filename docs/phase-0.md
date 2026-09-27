# Fase 0 — Decisiones, compatibilidad y threat model

## Estado

La fase 0 de diseño está completada. Esta fase no construye todavía una imagen ejecutable; deja cerradas las decisiones que guiarán el código de las siguientes fases.

## Decisiones cerradas

- Imagen base: Ubuntu 24.04 minimal, sin Kali ni Parrot.
- Perfiles: `light` y `full`.
- `full` se ejecuta en una VM dedicada y desechable.
- Acceso administrativo: Tailscale privado; sin puertos públicos.
- Terminal: `ttyd` y SSH con un único usuario `tester`, reutilizando una sesión tmux.
- SFTP: desactivado; no se crea una cuenta de transferencia separada.
- Workspace: `./workspace:/workspace`, inicialmente vacío.
- VPN: `vpntry`, `vpnhtb` y `vpncli`.
- Proxy: capacidad de `pt-forward` para `tester`, con TCP explícito, SOCKS5 y reverse proxy web solo sobre destinos de la VPN activa; no existe un usuario `proxy`.
- Despliegue cloud: VM + Docker mediante Terraform para OCI, Azure y DigitalOcean.
- Identidad: repositorio `hackadvisermx/seclab-sbf`. Sin registry: cada máquina construye en caliente la imagen que usa y la revisa con `make scan-image`.

## Matriz de compatibilidad

| Entorno | Arquitectura de imagen | Workspace | VPN dentro del contenedor | Acceso |
|---|---|---|---|---|
| macOS + Docker Desktop | Nativa ARM/AMD cuando esté disponible | Bind mount local | `VPN_MODE=inside` cuando Docker Desktop expone `/dev/net/tun` | Tailscale + SSH/ttyd |
| Linux local | Nativa `amd64` o `arm64` | Bind mount local | `VPN_MODE=inside` después de validar TUN | Tailscale + SSH/ttyd |
| OCI | ARM Ampere preferente | Volumen cifrado | `VPN_MODE=inside` | Tailscale |
| Azure | `amd64` | Managed disk/cifrado | `VPN_MODE=inside` | Tailscale |
| DigitalOcean | `amd64` | Volume cifrado | `VPN_MODE=inside` | Tailscale |

Docker Desktop para macOS puede ejecutar el cliente OpenVPN dentro de un contenedor cuando expone `/dev/net/tun` y `NET_ADMIN`; si el dispositivo no está disponible, el flujo falla de forma segura y se usa un host Linux con TUN. No se usará `privileged` ni `mknod` como solución.

## Threat model

### Confiables

- Código y configuración versionados del repositorio.
- Imágenes construidas en local y verificadas con `make scan-image`; la trazabilidad es la etiqueta `seclab.build-inputs`.
- Host cloud administrado por el operador.
- Tailnet personal con MFA, device approval y ACL deny-by-default.

### No confiables

- Binarios, exploits, scripts y repositorios descargados durante una sesión.
- Archivos recibidos de CTF o engagements.
- Salida de herramientas de escaneo.
- Contenido web y respuestas de targets.
- Credenciales o archivos generados por herramientas.

### Límites de confianza

- El contenedor no monta el filesystem del host ni `docker.sock`.
- Tailscale corre en el host y no en el contenedor.
- El acceso web y SSH no se expone fuera del tailnet; la capacidad de proxy tampoco.
- Las rutas VPN no sustituyen el firewall del host.
- El proxy no puede alcanzar Tailscale, metadata cloud, gateway Docker ni destinos fuera de la tabla VPN activa.
- El workspace es la única superficie de escritura para el usuario.

## Layout de secretos

- `.env`: credenciales de ttyd, SSH, rutas VPN y configuración de ejecución.
- `.secrets/ssh/`: par Ed25519 local ignorado por Git; la clave privada nunca se monta en el contenedor.
- `deploy/.env`: auth key de Tailscale y credenciales de bootstrap/Terraform.
- Ambos archivos deben tener permisos `600` y no versionarse.
- `.env.example` contiene únicamente nombres de variables y valores vacíos.
- No se usan claves privadas de SSH en el servidor.
- Las claves de autenticación de Tailscale son one-off, etiquetadas, preaprobadas y de expiración corta.

## Entregables de la fase 0

- [x] Identidad del repositorio y registro de imágenes definida.
- [x] Variables de entorno documentadas en `.env.example`.
- [x] `.gitignore` para secretos, workspace, VPN y state de Terraform.
- [x] Matriz de compatibilidad local/cloud definida.
- [x] Threat model y límites de confianza documentados.
- [x] Criterios de seguridad de fase 0 registrados en `AGENTS.md`.

## Revisión local

La revisión de esta fase es documental; todavía no existe una imagen para ejecutar.

```text
open plan.md
open docs/phase-0.md
git status --short
git diff --check
```

En macOS, `open` abre los archivos en la aplicación predeterminada. Los comandos de Git solo verifican el estado y formato del cambio; no hay pruebas de runtime hasta que exista el `Dockerfile` y `compose.yaml`.
