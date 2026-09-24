# Fase 6.5 — Seguridad de exposición

## Estado

La política de host y el contrato Tailscale host-only están preparados y validados. El host final OCI tiene NAT, Tailscale, Docker y nftables persistente; el consumo externo del proxy todavía no está habilitado.

## Artefactos

- `security/policies/nftables-lab.nft`: reglas `prerouting` para Linux/cloud, con CIDR y gateway Docker parametrizados para revisión previa.
- `security/tailscale/README.md`: bootstrap manual, ACL, one-off auth key, restricciones de Funnel/Exit Node y consumo externo.
- `scripts/security/check-isolation.sh`: valida la CIDR/gateway Docker local, la sintaxis nftables en Linux y omite explícitamente macOS.
- `scripts/security/check-tailscale.sh`: valida el daemon y el estado de Serve en Linux sin imprimir datos del tailnet.
- `Makefile`: objetivos `security-check` y `tailscale-check`.

## Límites

- Tailscale no se instala dentro del contenedor.
- No se publican puertos Docker.
- No se habilita Funnel, Exit Node ni rutas DNS automáticas.
- `pt-forward`, `pt-socks` y `pt-web` permanecen loopback-only.
- La política debe ajustarse a la red Docker real antes de cargarse.

## Verificación local

```text
make security-check
```

En macOS con Docker Desktop el resultado esperado es `nftables_check=skipped`. En Linux como root, el comando ejecuta `nft -c -f security/policies/nftables-lab.nft`; la aplicación queda fuera del repositorio y requiere revisión del operador.

```text
make tailscale-check
```

El check de Tailscale no imprime el JSON de estado ni claves; en macOS se omite.

## Validación efímera OCI

El 2026-09-24 se validó en OCI `mx-monterrey-1` un host Ubuntu 24.04 AMD64, `VM.Standard.E5.Flex` de 2 OCPU/8 GB, nftables 1.0.9, Docker 29.1.3 y Tailscale 1.102.4. Antes de cargar la política, el contenedor de prueba alcanzaba metadata AWS, el host Tailscale y el gateway Docker. Con el hook `prerouting`, esos tres destinos y las metadata Azure/Oracle quedaron bloqueados; la salida pública siguió disponible.

El acceso de administración se probó por Tailscale después de retirar el ingress SSH público. En una segunda prueba, el mismo nodo se relanzó sin `public_ip` y con ruta por NAT gateway; `tailscale ping`, SSH overlay, `netcheck` UDP/IPv4 y egress funcionaron. Todos los recursos temporales fueron destruidos.

## Host final OCI

El host `seclab-cloud-20260924154553` quedó en `mx-monterrey-1` con `VM.Standard.E5.Flex` 2 OCPU/8 GB, Ubuntu 24.04 AMD64, Tailscale 1.102.4, Docker 29.1.3 y nftables 1.0.9. Su VNIC usa subnet privada, `public_ip=null`, ruta default por NAT gateway y security lists sin ingress. La unidad systemd `seclab-nftables.service` mantiene la política `prerouting`; el smoke final bloqueó metadata, Tailscale y gateway Docker y mantuvo egress público.

## Pendiente

- Rotar y revocar el material sensible que pudo quedar expuesto en metadata previa.
- Diseñar el transporte host-only para consumir `pt-web` sin `ports:`.
- Confirmar ACL, MFA y device approval del tailnet en el host final.
- Mantener Ghidra/reversing fuera de esta fase.
