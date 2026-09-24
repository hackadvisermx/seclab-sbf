# Instrucciones para agentes

## Estado del repositorio

- Este repositorio tiene completadas las fases 1, 2, 3, 4 y 5 v1; la Fase 6 está en curso con `pt-forward` TCP, `pt-socks` SOCKS5, `pt-web` HTTP/HTTPS/WebSocket y route guard; la seguridad de exposición está en curso con plantilla nftables y contrato Tailscale host-only. El flujo normal de VPN es `VPN_MODE=inside`: `vpn-up` prepara únicamente el daemon de control y el usuario `tester` solicita el túnel bajo demanda. En macOS se requiere que Docker Desktop exponga `/dev/net/tun`; TryHackMe ya fue validado en esa plataforma; en Linux se requiere un host con TUN. Ya existen `images/light/Dockerfile`, `ttyd`, OpenSSH, shell `tester`, `fzf`/`zoxide`, Oh My Zsh pinneado, plugins, banner, `pt-help`, `pt-tools`, `vpn-manager`, `vpn-control`, `pt-forward`, lockfiles, workflows y `docs/phase-3.md`/`docs/phase-4.md`/`docs/phase-5.md`/`docs/phase-6.md`/`docs/phase-7-security.md`. La política nftables no se carga automáticamente y el consumo externo del proxy, herramientas upstream, Terraform y pruebas de integración siguen pendientes. Ghidra y reversing quedan fuera de la iteración actual.
- Trata `plan.md` como la fuente de verdad del producto y del diseño, especialmente `plan.md:17-37` para decisiones y `plan.md:785-950` para fases, criterios de aceptación y riesgos.
- No afirmes que el toolkit upstream completo, Tailscale instalado, consumo externo del proxy o Terraform estén implementados. La VPN v1 usa `VPN_MODE=inside` y permite que el usuario `tester` solicite el túnel bajo demanda; `pt-forward`/`pt-socks`/`pt-web` v1 solo aceptan destinos con ruta `tun0`; `make compose up` prepara el daemon y `tun0` sin conectar un perfil; la aceptación requiere que Docker Desktop exponga TUN en macOS o usar un host Linux con TUN. `make verify` ejecuta Gitleaks, Hadolint y ShellCheck; `make compose config ENV_FILE=.env.example` valida Compose; `make build-light` construye la imagen; `docker scout cves local://seclab-sbf:light --only-severity critical,high --exit-code` valida el gate local; `make compose up` exige credenciales reales en `.env`; `make compose shell` abre Bash como `tester`; `make compose zsh` previsualiza Zsh; `make compose tmux` entra a la sesión activa; `make compose vpn-up` asegura el daemon VPN, `make compose vpn-tun-check` valida TUN y `make compose vpn-down` lo detiene; `make compose proxy-status`, `proxy-doctor` y `proxy-stop` gestionan el proxy; `make security-check` valida la política nftables en Linux; `make tailscale-check` valida el daemon Tailscale host-only; `go run github.com/rhysd/actionlint/cmd/actionlint@v1.7.12` valida los workflows.
- La identidad del proyecto es `hackadvisermx/seclab-sbf`; las imágenes se publicarán en `ghcr.io/hackadvisermx/seclab-sbf`.
- Antes de implementar, revisa los archivos reales y actualiza este archivo con comandos verificados y puntos de entrada reales.

## Restricciones de seguridad no negociables

- Nunca expongas públicamente el contenedor del laboratorio ni los puertos del VPS. El único acceso previsto es mediante Tailscale (`plan.md:69-78`, `plan.md:342-377`).
- No agregues `--privileged`, no montes `docker.sock`, no uses `network_mode: host` de forma predeterminada y no montes el home o el sistema de archivos raíz del host.
- Mantén `.env` y `deploy/.env` sin seguimiento, con permisos `600`, y fuera de imágenes, registros, planes/state de Terraform y `user-data`. Las claves privadas locales viven en `.secrets/ssh/`, también ignorado, y nunca se montan en el contenedor. Solo `.env.example` puede versionarse (`plan.md:284-323`).
- Usa claves de autenticación de Tailscale de un solo uso, etiquetadas, preaprobadas y con expiración corta; revoca la clave después de que el VPS se una. No uses claves reutilizables (`plan.md:351-370`).
- Tailscale es para acceso administrativo, no sustituye el aislamiento del contenedor. Mantén bloqueados desde el laboratorio la metadata de la nube, el gateway de Docker, las interfaces del host y los rangos de Tailscale.
- Usa versiones, digests, hashes y firmas fijados exactamente. No uses `latest`, `curl | bash` ni actualizaciones automáticas en tiempo de ejecución (`plan.md:179-232`).
- Los perfiles VPN no deben cambiar la ruta predeterminada ni el DNS global. Usa archivos `.ovpn` sanitizados y rutas VPN explícitas (`plan.md:439-496`).
- El proxy solo debe permitir destinos alcanzables mediante la tabla de rutas de la VPN activa; nunca lo conviertas en un proxy abierto. Con un único usuario `tester`, el route guard es una interfaz controlada y no una frontera contra ese usuario; el firewall/nftables debe reforzar la restricción (`plan.md:485-535`).

## Arquitectura y límites

- La arquitectura objetivo es una sola imagen Ubuntu 24.04 multiplataforma con objetivos `light` y `full`; `full` está pensado para una VM dedicada y desechable (`plan.md:124-177`).
- `make compose up` inicia automáticamente el servicio del laboratorio, el daemon VPN y `tun0` sin conectar un perfil; el usuario `tester` elige la VPN con `vpntry`, `vpnhtb` o `vpncli`.
- El servicio VPN conserva `cap_drop: ALL` y añade solo `NET_ADMIN` y `CHOWN`: `CHOWN` asigna el socket a `tester`; nunca se resuelve TUN con `--privileged`.
- Tailscale se ejecuta en el host, no dentro del contenedor del laboratorio. `ttyd`, SSH y el tráfico de la capacidad de proxy usan túneles privados del host.
- El montaje tipo bind `./workspace:/workspace` es el área de trabajo del usuario. Inicia vacío; no crees subdirectorios automáticamente sin cambiar el diseño documentado (`plan.md:316-340`).
- Compose local no debe publicar puertos en esta fase; el secret file se monta en `/run/secrets/lab.env` y el contenedor usa rootfs read-only, `cap_drop: ALL` y `no-new-privileges`.
- `light` ejecuta `sshd` como servicio root con capabilities mínimas y las sesiones como `tester`; no existen usuarios `transfer` ni `proxy`.
- El acceso SSH es únicamente con claves. El único usuario planeado es `tester` (shell con tmux); SFTP está desactivado y la capacidad de proxy será un comando controlado con frontera de red, no otra cuenta Unix (`plan.md:235-282`).
- `pt-forward`, `pt-socks` y `pt-web` se ejecutan como `tester`, escuchan solo en loopback y validan la tabla de rutas contra `tun0`; el consumo externo queda pendiente.
- La política `security/policies/nftables-lab.nft` es una plantilla de host Linux y no se carga automáticamente; `security/tailscale/README.md` define el contrato host-only.
- `vpntry`, `vpnhtb` y `vpncli` corresponden a `tryhackme.ovpn`, `hackthebox.ovpn` y `client.ovpn` respectivamente; el socket Unix solo permite esas acciones y el servicio root conserva las rutas. Mantén los perfiles aislados y limpia las rutas al desconectarse (`plan.md:430-483`).
- Oh My Zsh y los plugins externos están fijados a commits concretos; el plugin local `pentest-lab` contiene `pt-help`, `pt-tools`, `pt-banner`, `pentest-reset`, los alias VPN de la Fase 5 y `pt-forward`/`pt-socks`/`pt-web` de la Fase 6 (`plan.md:537-614`).

## Flujo de implementación

- Implementa por fases según `plan.md:798-894`; no saltes directamente a construir una imagen `full` grande.
- Comienza con las fuentes ejecutables reales: `Dockerfile`, `compose*.yaml`, `Makefile`, scripts de entrada, lockfiles y CI. Agrega documentación solo para comportamientos verificados.
- Al agregar una herramienta o un plugin de shell, actualiza su lockfile y escánalo; no instales binarios sin versión fijada de forma silenciosa.
- Mantén equivalentes las rutas local y de nube: local usa el workspace mediante bind mount; la nube usa un volumen del proveedor montado en la misma ruta del contenedor.
- Para Terraform, usa stacks específicos en `terraform/stacks/{oci,azure,digitalocean}` y state remoto nativo por proveedor. Nunca versiones state local (`plan.md:630-693`).
- El bootstrap de Terraform no debe recibir el `.env` de ejecución; cópialo después de que Tailscale esté disponible. Protege el state de Terraform porque puede conservar valores sensibles aunque estén marcados como `sensitive`.

## Flujo Git y Pull Requests

- Cada fase debe vivir en su propia rama `phase/<numero>-<slug>`, por ejemplo `phase/05-vpn`; no se modifica `main` directamente.
- Cada fase debe terminar en un Pull Request hacia `main` con alcance, archivos, pruebas, riesgos, CVEs y limitaciones conocidas.
- El agente puede actualizar la rama de fase y abrir el PR, pero no debe hacer push directo a `main`, mergear ni cerrar el PR sin aprobación explícita del owner.
- El owner debe aprobar el PR en GitHub antes de cualquier merge. Si no existe remote o no se puede configurar branch protection, informa la limitación y no simules un merge.
- No hagas force-push, no reescribas commits compartidos y no incluyas `.env`, `.ovpn`, certificados, claves privadas, state de Terraform ni secretos.
- Antes de solicitar aprobación, ejecuta `git status`, `make verify`, `make build-light`, `make compose config ENV_FILE=.env.example`, Actionlint y el gate de Scout; revisa el diff completo.
- Después de la aprobación, el merge se hace mediante el PR; la rama de fase se elimina solo cuando el merge esté confirmado.

## Commits e historial

- Cada commit debe representar un cambio logical y estar asociado a una fase; evita mezclar fases o refactors sin relación.
- Usa un subject breve e imperativo y un cuerpo con: fase, motivo, alcance, validación ejecutada, riesgos/CVEs y limitaciones o reversión.
- Registra en el commit las decisiones que no sean obvias del diff, especialmente cambios de seguridad, rutas, DNS, permisos o supply chain.
- No agregues comentarios de código para explicar el historial: el historial pertenece al mensaje del commit; los comentarios de código solo si son necesarios y fueron solicitados.
- Antes de cada commit revisa `git status`, `git diff`, `git log --oneline -10`, incluye solo archivos intencionales y comprueba que no haya `.env`, `.ovpn`, claves ni secretos.
- Usa mensajes en español o inglés de forma consistente dentro de la misma fase; recomienda `tipo(área): resumen`, por ejemplo `feat(vpn): añadir control autenticado`.

## Expectativas de verificación

- No existe una suite de pruebas ni typecheck; `make verify`, `make build-light`, `make compose config ENV_FILE=.env.example`, Actionlint, el gate de Scout para Critical/High, la validación sintáctica de `compose.vpn-inside.yaml`, `make security-check`, `make tailscale-check` y los smoke tests de `pt-forward` son las verificaciones locales disponibles. No inventes `npm test`, `make test` ni comandos similares; agrega y documenta el comando cuando exista la herramienta correspondiente.
- Las verificaciones futuras deben incluir sintaxis/lint de shell, lint de Dockerfile, escaneo de secretos, validación y políticas de Terraform, escaneo de vulnerabilidades de imagen/SBOM y pruebas de humo.
- Las imágenes de release deben construirse para `linux/amd64` y `linux/arm64`, y desplegarse por digest inmutable después de verificar firma y provenance (`plan.md:170-177`, `plan.md:695-735`).
- Prueba macOS Docker Desktop por separado de Linux y la nube: usa `VPN_MODE=inside` cuando Docker Desktop exponga `/dev/net/tun`; `make compose vpn-tun-check` debe mostrar el dispositivo y `NET_ADMIN`. Nunca resuelvas problemas de TUN con `--privileged` o `mknod` (`plan.md:471-483`).
- Antes de declarar que algo está terminado, revisa los criterios de aceptación de `plan.md:897-919`, especialmente la ausencia de puertos públicos, acceso solo por Tailscale, aislamiento de rutas VPN, ausencia de SFTP y no divulgación de secretos.
