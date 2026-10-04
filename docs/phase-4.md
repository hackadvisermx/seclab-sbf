# Fase 4 — Terminal, Zsh y banner

## Estado

La fase 4 v1 está implementada y verificada en Docker Desktop ARM64, con build y comprobación básica en AMD64. La shell de `tester` es Zsh y las sesiones SSH/ttyd comparten la sesión tmux `pentest-lab`.

## Componentes

- Oh My Zsh instalado desde el commit `74965c96098134b192f00084f966b4b02438a739`.
- Plugins externos clonados por commit: `zsh-autosuggestions`, `zsh-syntax-highlighting`, `zsh-completions` y `zoxide`.
- Plugins nativos habilitados: `git`, `tmux`, `ssh`, `extract`, `history`, `aliases` y `jsontools`; la finalización la inicializa el núcleo de Oh My Zsh.
- `fzf` 0.74.4 y `zoxide` 0.10.0 verificados por lockfile y hash.
- `shell/tools.json` es el manifiesto estático de herramientas; no se ejecutan herramientas de red para generar el resumen.
- `shell/pentest-lab/pentest-lab.plugin.zsh` proporciona `pt-banner`, `pt-help`, `pt-tools`, `pentest-reset`, aliases VPN de la Fase 5 y los helpers de pentest (`pt-extractports`, `pt-nmp`, `pt-serv-web`, `pt-serv-smb`, `pt-s3-ls`, `pt-recon`) con sus aliases ergonómicos (`nmp`, `extractports`, `webserverhere`, `smbserverhere`, `awsl`).
- `images/light/Dockerfile` copia `.tmux.conf` a `/home/tester/.tmux.conf` como `root:root` con modo `0444`; los cambios requieren `make build-light` y recrear el contenedor.

## Banner y estado

- Banner menor de 80 columnas, con perfil, número de herramientas, categorías y estado de seguridad.
- Respeta `NO_COLOR`, `TERM=dumb` y la ausencia de TTY.
- Se marca una vez por sesión mediante la opción tmux `@seclab_banner_shown`.
- `pt-help` muestra workspace, SSH, ttyd, seguridad y comandos de uso; SFTP aparece como desactivado.
- `pt-tools` consulta el manifiesto y muestra el estado local sin ejecutar `nmap --version` ni realizar red.
- Historial, cache de Zsh y datos de zoxide viven en `/var/lib/seclab/tester`, dentro del volumen persistente `lab-state`.

## Integración de acceso

- `tester` usa `/usr/bin/zsh` como shell de SSH.
- Las sesiones SSH interactivas con `SSH_CONNECTION` y ttyd ejecutan `tmux new-session -A -s pentest-lab`.
- `make compose shell` conserva su comando Bash para depuración local y no inicia sshd/ttyd.
- `make compose zsh` abre una sesión Zsh efímera para previsualización.
- `make compose tmux` entra a la sesión tmux real; requiere `make compose up`.
- El contenedor usa la copia read-only de `.tmux.conf`; el usuario `tester` no puede modificarla.
- `TMUX_PLUGIN_MANAGER_PATH=/tmp/tmux-plugins` mantiene el estado efímero de TPM en el tmpfs, sin escrituras sobre el rootfs read-only.
- `TERM` toma `xterm-256color` como valor por defecto únicamente cuando el cliente no lo proporciona.

## Comandos

Construir:

```text
make build-light
```

Abrir una shell de depuración:

```text
make compose shell
```

Previsualizar Zsh sin iniciar los daemons:

```text
make compose zsh
```

Entrar a la sesión del servicio activo:

```text
make compose tmux
```

En una sesión interactiva de `tester`:

```text
pt-help
pt-tools
pt-banner
pentest-reset
```

### Helpers de Pentest y Ergonomía

- `pt-extractports [archivo.gnmap]`: Parsea la salida grepeable de nmap (`-oG`), extrayendo los puertos abiertos en formato separado por comas (ej. `22,80,443`) y la IP objetivo. Si `xclip` o `pbcopy` están presentes, los copia al portapapeles. Alias: `extractports`.
- `pt-nmp <IP/Host> [prefijo]`: Flujo de escaneo inteligente en dos fases. Fase 1 ejecuta un SYN scan rápido de los 65535 puertos (`-sS -p- --min-rate 5000 -Pn -n -vvv -oG <prefijo>_allports.gnmap`). Fase 2 extrae los puertos descubiertos y ejecuta escaneo exhaustivo de scripts y versiones (`-sC -sV -oN <prefijo>_targeted.nmap`) únicamente sobre dichos puertos. Alias: `nmp`.
- `pt-serv-web [puerto]`: Inicia un servidor web HTTP de staging (`python3 -m http.server`) en el directorio actual (por defecto puerto 8000, apto para usuario `tester` sin requerir privilegios de enlace a puertos bajos). Alias: `webserverhere`.
- `pt-serv-smb [recurso] [ruta] [usuario] [contraseña]`: Inicia un servidor SMB de staging mediante `smbserver.py` de Impacket con soporte SMB2 para captura de hashes o transferencia con hosts Windows. Alias: `smbserverhere`.
- `pt-s3-ls <bucket>`: Consulta el contenido público de buckets AWS S3 sin firma (`--no-sign-request` vía `aws`, `s3scanner` o endpoint S3). Alias: `awsl`.
- `pt-recon <dominio>`: Pipeline básico de reconocimiento que integra `subfinder` (descubrimiento de subdominios), `httpx` (detección de hosts activos) y `waybackurls` / `anew` (recolección de URLs históricas únicas).

## Verificación realizada

- Carga de Zsh y Oh My Zsh sin warnings en modo no interactivo.
- Plugins nativos y externos disponibles en la imagen ARM64 y AMD64.
- `zoxide --version` devuelve `0.10.0`; `fzf --version` devuelve `0.74.4`.
- Banner debajo de 80 columnas y opción tmux establecida en `1` tras el primer inicio.
- `pt-help`, `pt-tools` y aliases VPN están disponibles.
- `.tmux.conf` coincide por hash con el host y conserva permisos `0444` dentro del contenedor.
- Historial y datos de zoxide se escriben en el volumen persistente.
- SSH con clave funciona para `tester`; SFTP está desactivado; ttyd conserva autenticación.
- `nmap -sT`, rootfs read-only, `CapDrop=ALL` y `no-new-privileges` siguen verificados.
- Scout no reporta vulnerabilidades Critical/High en ARM64 ni AMD64.
- Arranque local de referencia: aproximadamente 0.33 s para `zsh -ic exit` en ARM64.

## Pendiente

- Pruebas de interacción nativas en hardware AMD64.
- La VPN, Tailscale, el proxy y las herramientas upstream ya tienen fase
  propia y su estado está en sus documentos: `phase-5.md`, `phase-6.md`,
  `phase-7-security.md` y `phase-7.md`. Aquí no se siguen.
- `pentest-reset` solo limpia el historial de tmux y no modifica el workspace,
  que es un límite del comando, no un pendiente.
