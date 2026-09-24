# Fase 5 — Gestión de VPN

## Estado

La Fase 5 v1 usa `VPN_MODE=inside` como flujo normal: el daemon de control prepara el socket, pero no conecta OpenVPN hasta que el usuario `tester` ejecuta `vpntry`, `vpnhtb` o `vpncli`. En macOS, Docker Desktop debe exponer `/dev/net/tun` al contenedor; no se usa `privileged` ni `mknod`. La conexión real de TryHackMe ya fue validada dentro del contenedor; la prueba nativa en Linux y los perfiles restantes siguen pendientes. `VPN_MODE=host` queda únicamente como compatibilidad explícita y nunca inicia una VPN.

## Componentes

- `scripts/vpn-manager.sh` valida perfiles, administra estado y ejecuta OpenVPN únicamente en un servicio opcional con privilegios mínimos.
- `scripts/vpn-control.py` precrea `tun0` y expone un socket Unix local que solo acepta acciones allowlistadas del usuario `tester`; el servicio root conserva el control de OpenVPN.
- `compose.vpn-inside.yaml` monta `/vpn` en solo lectura, comparte el namespace de red de `lab` y mantiene el daemon VPN en modo `serve`.
- El servicio opcional usa `CAP_NET_ADMIN` para TUN y `CAP_CHOWN` únicamente para asignar el socket al usuario `tester`; también usa `/dev/net/tun` y no usa `--privileged` ni `network_mode: host`.
- `shell/pentest-lab/pentest-lab.plugin.zsh` expone `vpntry`, `vpnhtb`, `vpncli`, `vpn-list`, `vpn-status`, `vpn-connect`, `vpn-disconnect`, `vpn-switch` y `vpn-doctor`.

## Seguridad de perfiles

Los archivos viven fuera de la imagen, en `/vpn` dentro del contenedor. El gestor rechaza:

- `redirect-gateway` y rutas por defecto se eliminan del perfil sanitizado y se ignoran cuando el servidor las empuja.
- Opciones DHCP de DNS, dominio, WINS, NTP o búsqueda se eliminan o ignoran.
- Directivas ejecutables como `up`, `down`, `route-up`, `client-connect`, `plugin`, `iproute` y `script-security`.
- Rutas hacia loopback, metadata cloud, gateway Docker o rangos de Tailscale, incluidas las variantes IPv6.
- Perfiles sin rutas explícitas.

El perfil sanitizado se genera con permisos `0600` en el volumen de estado. Los perfiles con rutas explícitas reciben `route-nopull`; los perfiles oficiales que dependen de rutas empujadas las conservan, pero el gestor agrega `pull-filter` para ignorar `redirect-gateway`, `route-gateway` y `dhcp-option`. El directorio del socket permanece en `root:root` con modo `0711`; el socket es `tester:tester` con modo `0660`. No se imprimen certificados, claves ni contenido del perfil.

## Modos

### Flujo normal: contenedor

`VPN_MODE=inside` es el valor predeterminado y el único flujo del tester. `make compose up` inicia el servicio del laboratorio y el daemon Unix de control, precrea `tun0` y no abre un túnel. El usuario `tester` solicita la VPN bajo demanda mediante `vpntry`, `vpnhtb` o `vpncli`, y el servicio root ejecuta OpenVPN dentro del contenedor.

En macOS, Docker Desktop debe permitir el mapeo de `/dev/net/tun`; en Linux, el host debe exponer el dispositivo de caracteres. La prueba de dispositivo e interfaz es `make compose vpn-tun-check` y debe mostrar `tun=present`, `tun_interface=tun0 present` y `net_admin=present`. Si el dispositivo no está disponible, el servicio falla de forma segura sin usar `--privileged` ni crear el nodo manualmente.

### Compatibilidad explícita

`VPN_MODE=host` solo se conserva para instalaciones que lo seleccionen explícitamente. No inicia un cliente VPN ni ejecuta OpenVPN fuera del contenedor; el flujo normal del tester no lo utiliza.

### Procedimiento de aceptación

1. Configurar `.env` con `VPN_MODE=inside` y `VPN_DIR=./vpn`; mantener el archivo en permisos `600`. Si ya existe, no sobrescribirlo: cambiar únicamente esas líneas.
2. Verificar que `vpn/` contiene únicamente el perfil autorizado. Los perfiles oficiales se pueden usar sin edición manual: el gestor genera la copia sanitizada.
3. Ejecutar `make verify` y `make build-light`.
4. Levantar el laboratorio con `make compose up`; este inicia el servicio `lab`, el daemon VPN y `tun0`, pero no conecta un túnel. `make compose vpn-up VPN_DIR=./vpn` queda como operación idempotente.
5. Ejecutar `make compose vpn-tun-check VPN_DIR=./vpn` y `make compose vpn-doctor VPN_DIR=./vpn`. El resultado debe incluir `tun=present`, `tun_interface=tun0 present` y `net_admin=present`.
6. Entrar al laboratorio con `make compose tmux` y ejecutar `vpn-status`; debe mostrar `active=none`.
7. Como usuario `tester`, ejecutar `vpntry` o `vpn-connect tryhackme`; este es el único paso que inicia OpenVPN.
8. Verificar el estado y las rutas desde el servicio VPN; después ejecutar `vpn-disconnect` y confirmar `active=none`.
9. Detener el daemon con `make compose vpn-down VPN_DIR=./vpn`.

El servicio opcional usa `compose.vpn-inside.yaml` y `make compose up` lo inicia automáticamente; `vpn-up` queda como operación idempotente para asegurar el daemon y `tun0`. Con el daemon activo, los aliases de `tester` hablan al socket y no reciben acceso root. `VPN_MODE=host` no se usa en este procedimiento.

## Comandos dentro de `lab`

```text
vpn-list
vpn-status
vpn-doctor
vpn-connect <perfil>
vpn-disconnect
vpn-switch <perfil>
vpntry
vpnhtb
vpncli
```

En `VPN_MODE=host`, `vpn-connect`, `vpn-switch` y los aliases devuelven una negativa sin tocar la tabla de rutas. En `VPN_MODE=inside`, después de `make compose vpn-up`, los aliases de `tester` envían la solicitud al socket controlado por el servicio root; no obtienen un shell root.

## Verificación realizada

- `vpn-manager list` y `vpn-manager status` funcionan en la imagen.
- Los aliases `vpn-list`, `vpn-status`, `vpntry`, `vpnhtb` y `vpncli` están disponibles en Zsh.
- El daemon root crea un socket `tester:tester` `0660`; la autenticación por UID, las acciones allowlistadas y la limpieza al detener el daemon fueron probadas en un contenedor Linux aislado.
- El directorio del socket permanece en `root:root` `0711`; solo `tester` puede usarlo y la conexión sin TUN se rechaza antes de ejecutar OpenVPN.
- El modo host rechaza conexiones y no modifica rutas.
- `vpn-tun-check` pasó en Docker Desktop macOS ARM64 con un entorno temporal: `tun=present`, `tun_interface=tun0 present` y `net_admin=present`.
- `make compose up` levantó `lab` y `vpn`, creó `tun0` antes de la solicitud y dejó `active=none`; no había OpenVPN activo.
- La conexión real autorizada de `tryhackme.ovpn` pasó sin editar el perfil descargado: `tun0` recibió la dirección del proveedor, solo se añadió su ruta VPN, la ruta por defecto y DNS no cambiaron, y `vpn-disconnect` restauró el estado.
- `hackthebox.ovpn` y `client.ovpn` pasan la sanitización, pero no se conectaron contra sus proveedores.
- Perfiles sintéticos con rutas explícitas fueron aceptados.
- `redirect-gateway` y las opciones DNS fueron filtradas; las rutas por defecto, `route-ipv6` link-local, gateway Docker, `iproute` y rutas Tailscale explícitas fueron rechazadas.
- `compose.vpn-inside.yaml` valida sintaxis Compose.

## Limitaciones de aceptación

- La conexión real de `tryhackme.ovpn` y su limpieza están verificadas en Docker Desktop macOS; faltan las pruebas reales de `hackthebox`/`client` y la prueba nativa en Linux.
- La validación de release debe confirmar nuevamente el bloqueo de Tailscale, metadata, gateway Docker e interfaces del host; la sanitización de rutas no sustituye esas reglas de firewall.
- El modo `host` solo conserva la compatibilidad explícita y no se usa para iniciar túneles.

## Siguiente fase

- Fase 6: `pt-forward` TCP, `pt-socks` SOCKS5 y `pt-web` HTTP/HTTPS/WebSocket para `tester`; consumo externo pendiente.
