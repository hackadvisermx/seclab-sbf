# Fase 6 — Proxy Lab v1

## Estado

La v1 de `pt-forward` y `pt-socks` está implementada para el usuario único `tester`. Ambos comandos escuchan únicamente en `127.0.0.1`, exigen una VPN activa y validan cada conexión contra `tun0`. `pt-web` permanece pendiente.

## Componentes

- `scripts/proxy-control.py`: helper Python sin dependencias externas para TCP loopback, SOCKS5, estado, arranque, parada y diagnóstico.
- `images/light/Dockerfile`: instala el helper como `/usr/local/bin/pt-forward` con permisos `0555`.
- `shell/pentest-lab/pentest-lab.plugin.zsh`: aliases `pt-forward` y `pt-socks`.
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
pt-forward status
pt-forward doctor [host port]
pt-forward stop
pt-forward clean
```

El puerto por defecto de `pt-forward` es `18080`; el de SOCKS5 es `1080`. No se publican puertos Docker.

Desde el host:

```bash
make compose proxy-status
make compose proxy-doctor
make compose proxy-stop
```

## Verificación realizada

- `make build-light` completa con el helper instalado.
- `make compose config ENV_FILE=.env.example` pasa.
- `pt-forward doctor` devuelve 78 sin VPN y no inicia listeners.
- Con `tryhackme.ovpn` activo, una dirección con ruta `tun0` es permitida y `127.0.0.1` es rechazado.
- `pt-forward` y `pt-socks` arrancan, muestran estado y respetan permisos `0700`/`0600`.
- Al ejecutar `vpn-disconnect`, el proxy se detiene automáticamente.
- `pt-tools` muestra `pt-forward`.

## Límites

- El usuario `tester` conserva shell y puede ejecutar herramientas de red directamente; la route guard es una interfaz controlada, no una frontera de seguridad contra ese usuario.
- La barrera de red definitiva para metadata, Tailscale, gateway Docker e interfaces del host queda en nftables/cloud.
- `pt-web`, el consumo externo mediante Tailscale y las pruebas VPS quedan pendientes.
- No se deben añadir listeners `0.0.0.0` ni forwarding SSH.
