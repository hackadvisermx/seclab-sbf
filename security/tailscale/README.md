# Tailscale host-only

Tailscale se instala y ejecuta únicamente en el host. No se instala en la imagen del laboratorio, no se monta en el contenedor y no se usa `network_mode: host`.

## Requisitos

- Una auth key one-off, etiquetada, preaprobada y con expiración corta.
- ACL del tailnet en modo deny por defecto.
- MFA y device approval activos para los dispositivos administrativos.
- El contenedor y sus puertos Docker siguen sin publicación pública.

## Bootstrap manual

Ejecutar en el host, nunca dentro del contenedor:

```text
tailscale up --authkey=<one-off-key> --accept-dns=false --advertise-exit-node=false --hostname=seclab-sbf-<env>
```

Después:

```text
tailscale status
tailscale ip -4
tailscale serve status
```

La auth key se revoca manualmente después de verificar la unión. No se guarda en Git, `.env`, `deploy/.env`, user-data, logs ni planes de Terraform.

## Límites

- No habilitar Funnel, Exit Node, subnet routes ni rutas DNS automáticas.
- No abrir puertos Docker para consumir `ttyd`, SSH o el proxy.
- `pt-forward`, `pt-socks` y `pt-web` escuchan en loopback dentro del contenedor; su consumo externo se hace solo con el puente host-only `scripts/host/pt-proxy-bridge.sh` más `ssh -L` sobre el tailnet, sin `ports:`.
- En OCI, desde el 2026-10-10 el nodo lleva **IP pública efímera** y **cero ingress**, en lugar de `sin public_ip` + NAT. La razón son los límites del compartment: `nat-gateway-count = 0` e `internet-gateway-count = 1` ya ocupado, así que sin IP pública no había forma de salir a internet. Tener IP no significa accesible: el NSG y la security list de la subnet solo tienen reglas de **egress**, y `security/policies/nftables-lab.nft` cierra el `input` del host con `policy drop`. El acceso sigue siendo **solo por Tailscale**; entrar por la IP pública no funciona y no debe intentararse.
- La salida a internet usa el **internet gateway compartido** (`hermes-clone-igw`), en la VCN compartida `hermes-clone-vcn`. Este stack no crea ni gestiona esa VCN ni ese IGW: los lee con data sources. Si se borran desde el otro proyecto, el laboratorio pierde salida a internet (y con ella Tailscale).

## Verificación de firewall

En Linux, revisar primero la sintaxis y el contexto de Docker:

```text
sudo nft -c -f security/policies/nftables-lab.nft
sudo nft list table inet seclab_security
```

La política se evalúa en `prerouting` antes de la decisión local/forward y bloquea desde la red Docker hacia metadata cloud, Azure/Oracle metadata, Tailscale, loopback, gateways Docker y bridges Docker. La CIDR y el gateway deben ajustarse al deployment real antes de cargarla.

En macOS con Docker Desktop, `scripts/security/check-isolation.sh` informa `skipped`; no simula nftables ni modifica el host.
