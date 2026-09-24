# Fase 6.5 — Seguridad de exposición

## Estado

La política de host y el contrato Tailscale host-only están preparados. La política nftables no se carga automáticamente y el consumo externo del proxy todavía no está habilitado.

## Artefactos

- `security/policies/nftables-lab.nft`: reglas de forward para Linux/cloud, con CIDR y gateway Docker parametrizados para revisión previa.
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

## Pendiente

- Aplicar la política en un host Linux/cloud real y verificar metadata, Tailscale, gateway Docker e interfaces del host.
- Diseñar el transporte host-only para consumir `pt-web` sin `ports:`.
- Probar Tailscale en una VM/VPS con ACL y auth key one-off.
- Mantener Ghidra/reversing fuera de esta fase.
