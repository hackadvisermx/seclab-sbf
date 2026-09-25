# Fase 6 — Proxy Lab v1

## Estado

La v1 de `pt-forward`, `pt-socks` y `pt-web` está implementada para el usuario único `tester`. Todos escuchan únicamente en `127.0.0.1`, exigen una VPN activa y validan cada conexión contra `tun0`.

## Componentes

- `scripts/proxy-control.py`: helper Python sin dependencias externas para TCP loopback, SOCKS5, HTTP/HTTPS/WebSocket loopback, estado, arranque, parada y diagnóstico.
- `images/light/Dockerfile`: instala el helper como `/usr/local/bin/pt-forward` con permisos `0555`.
- `shell/pentest-lab/pentest-lab.plugin.zsh`: aliases `pt-forward`, `pt-socks` y `pt-web`.
- `Makefile`: objetivos `proxy-status`, `proxy-doctor` y `proxy-stop`.
- `shell/tools.json`: registra `pt-forward` como herramienta de red.

## Route guard

El helper ejecuta `vpn-control client status` y exige una sesión activa con `tun0`. Para cada destino:

1. Rechaza loopback, unspecified, link-local, multicast, metadata, Tailscale y gateways Docker.
2. Resuelve nombres sin confiar en el resultado de DNS.
3. Ejecuta `ip route get` y exige que la interfaz sea `tun0`.
4. Conecta a la IP validada, no a una segunda resolución uncontrolled.

El monitor interno detiene el proxy cuando la VPN deja de estar activa. El estado se guarda en `/var/lib/seclab/tester/proxy` con permisos privados.

## Uso

```text
pt-forward start tcp <host> <port> [listen_port]
pt-socks [listen_port]
pt-web start <http-or-https-origin> [listen_port]
pt-forward status
pt-forward doctor [host port]
pt-forward stop
pt-forward clean
```

El puerto por defecto de `pt-forward` es `18080`; el de SOCKS5 es `1080`; el de `pt-web` es `18081`. `pt-web` acepta solo un origen sin ruta, query, fragmento o credenciales, rechaza absolute-form HTTP y permite WebSocket sobre el mismo relay. No se publican puertos Docker.

Desde el host:

```bash
make compose proxy-status
make compose proxy-doctor
make compose proxy-stop
```

## Consumo externo host-only

El proxy sigue sin `ports:` y sin listeners fuera de `127.0.0.1` del
contenedor. El transporte externo es un puente que se ejecuta en el host:

```bash
./scripts/host/pt-proxy-bridge.sh tcp 18080 18080
./scripts/host/pt-proxy-bridge.sh socks 1080 1080
./scripts/host/pt-proxy-bridge.sh web 18081 18081
# o: make proxy-bridge SERVICE=tcp HOST_PORT=18080 CONTAINER_PORT=18080
```

El puente escucha solo en `127.0.0.1` del host y reenvía cada conexión al
loopback del contenedor mediante `docker compose exec`; no usa
`network_mode: host` ni publica puertos Docker. Desde el laptop, el consumo
es un `ssh -L` sobre el tailnet hacia ese loopback del host:

```bash
ssh -L 18080:127.0.0.1:18080 usuario@<tailnet-host>
ssh -L 1080:127.0.0.1:1080 usuario@<tailnet-host>
ssh -L 18081:127.0.0.1:18081 usuario@<tailnet-host>
```

El route guard no cambia: el puente solo transporta bytes hasta el listener
existente, que sigue exigiendo VPN activa y ruta `tun0`, y se detiene al
desconectar la VPN.

## Validación en VPS con Tailscale

El 2026-09-25 se validó en el host final `seclab-cloud-20260924154553`
(`mx-monterrey-1`, Ubuntu 24.04 AMD64) con el árbol en `06380b2`:

- En el host se instalaron `socat` 1.8.0.0 y `make` 4.3 desde Ubuntu, y
  `docker-compose-plugin` 5.5.1 desde el repo oficial de Docker; el usuario
  `ubuntu` se añadió al grupo `docker`. Tailscale y nftables no se tocaron.
- `make build-light` construyó `seclab-sbf:base` y `seclab-sbf:light`;
  `make compose up` levantó `lab` y `vpn`; `vpn-tun-check` mostró `tun0` y
  `NET_ADMIN` presentes sin perfil conectado.
- `vpn-connect tryhackme` conectó. La única ruta por `tun0` era
  `192.168.192.0/18`; el rango 10.x de THM no tenía ruta VPN (sin sala
  activa). El route guard rechazó `10.10.10.10` (exit 78), la IP local de
  `tun0` (sale por `lo`, correcto) y `169.254.169.254` (metadata).
- Destino vivo vía VPN: `192.168.192.1:443` acepta TCP (habla protocolo
  OpenVPN, no TLS ni HTTP).
- `pt-forward start tcp 192.168.192.1 443 18080` + puente
  `127.0.0.1:18080` en el host + `ssh -L 18099:127.0.0.1:18080` desde la
  Mac: el TCP se estableció de extremo a extremo (el servidor cerró al
  recibir HTTP plano, comportamiento esperado del servicio).
- `pt-socks` en `1080` + puente `127.0.0.1:11080` + `ssh -L` + handshake
  SOCKS5 desde la Mac: `CONNECT 192.168.192.1:443` devolvió `0x00` (éxito,
  bytes de ida y vuelta por toda la cadena) y
  `CONNECT 169.254.169.254:80` devolvió `0x01` (guard enforced).
- `vpn-disconnect` detuvo el proxy automáticamente (`pt-forward=inactive`).
- Limpieza: puentes y túneles cerrados, stack con `down`, VPN
  desconectada. En el host quedan las imágenes y `~/seclab-sbf` con `.env`
  (600) y perfiles `.ovpn`, como despliegue normal.

Observaciones no bloqueantes: compose avisa que la red
`seclab-sbf_default` ya existe y no la creó él; cada invocación de `make`
reconstruye las imágenes aunque no haya cambios.

## Verificación realizada

- `make build-light` completa con el helper instalado.
- `make compose config ENV_FILE=.env.example` pasa.
- `pt-forward doctor` devuelve 78 sin VPN y no inicia listeners.
- Con `tryhackme.ovpn` activo, una dirección con ruta `tun0` es permitida y `127.0.0.1` es rechazado.
- `pt-forward` y `pt-socks` arrancan, muestran estado y respetan permisos `0700`/`0600`.
- `pt-web` acepta un origen HTTP/HTTPS, rechaza absolute-form HTTP y permite el relay WebSocket; el listener permanece en loopback.
- Al ejecutar `vpn-disconnect`, el proxy se detiene automáticamente.
- `pt-tools` muestra `pt-forward`.

## Límites

- El usuario `tester` conserva shell y puede ejecutar herramientas de red directamente; la route guard es una interfaz controlada, no una frontera de seguridad contra ese usuario.
- La barrera de red definitiva para metadata, Tailscale, gateway Docker e interfaces del host queda en nftables/cloud.
- El consumo externo se hace solo mediante el puente host-only
  `scripts/host/pt-proxy-bridge.sh` más `ssh -L` sobre Tailscale, validado
  en VPS el 2026-09-25 (ver sección de validación).
- `pt-web` no implementa Caddy, terminating TLS local ni publicación de puertos; solo valida y reenvía HTTP/HTTPS/WebSocket a un origen fijo.
- No se deben añadir listeners `0.0.0.0` ni forwarding SSH.
