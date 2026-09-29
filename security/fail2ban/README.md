# fail2ban en el host

fail2ban frena ataques de autenticación repetidos contra el `sshd` del
**host**. No se instala ni se ejecuta dentro del contenedor del
laboratorio: el rootfs es de solo lectura, `tester` no es root y el
contenedor no administra el firewall del host.

## Artefactos

- `jail.d/seclab-sshd.conf`: la jail. Es la fuente de verdad; cloud-init
  la copia a `/etc/fail2ban/jail.d/seclab-sshd.conf` en el primer
  arranque. No se edita en el host a mano: el host es desechable.
- `../../scripts/security/check-fail2ban.sh`: verificación local en el
  host, expuesta como `make fail2ban-check`.

## Qué protege y qué no

Protege el `sshd` del host, que es por donde entra el operador al nodo.
El `sshd` del contenedor **no** está cubierto: sus logs viven en el journal
del contenedor y el host no los ve. Cubrirlo exigiría reenviar el journal
o exponer el log, y no compensa: el contenedor solo acepta llaves, tiene
`MaxAuthTries 3` y no se publica ningún puerto.

Tampoco cubre `ttyd` del contenedor, que va por el puente host-only.

## Por qué no se ignora el tailnet

La jail solo ve tráfico que llega por Tailscale. Poner
`100.64.0.0/10` en `ignoreip` la dejaría sin efecto sobre todo lo que
puede alcanzar el `sshd`, así que no se hace. El riesgo real es que un
nodo se banee a sí mismo tras cinco fallos en diez minutos. Las barreras:

- `ignoreself` viene activo por defecto en `jail.conf`, así que la IP
  propia del host nunca se banea.
- Ban por IP, nunca por subred: un nodo que falle no expulsa al resto.
- Si aun así hay lockout, el `sshd` del contenedor sigue escuchando y
  `ttyd` también, así que siempre hay una segunda vía dentro del tailnet.

## Recuperación ante lockout

Por consola serie del proveedor, o desde el `ttyd` del contenedor:

```text
fail2ban-client status sshd
fail2ban-client set sshd unbanip 100.x.y.z
```

Si no hay consola serie, `fail2ban-client -i` permite la interacción
directa. Con eso el operador recupera el acceso sin recrear el nodo.

## Interacción con nftables

Son tablas distintas y no se pisan:

- `inet seclab_security` de `security/policies/nftables-lab.nft`, que
  filtra en `prerouting` el tráfico que sale del contenedor hacia
  metadata, Tailscale o los bridges de Docker.
- `f2b-table` de fail2ban, que banea en `input`.

`make security-check`, `make fail2ban-check` y `make fail2ban-jail-check`
son independientes y ninguno aplica nada: solo validan.

## Verificación

En cualquier máquina con Docker, sin nodo:

```text
make fail2ban-jail-check
```

Levanta un contenedor desechable con la imagen base por digest, el mismo
snapshot de Ubuntu que los Dockerfiles (`20260925T000000Z`) y fail2ban
fijado a `1.0.2-3ubuntu0.1`, y comprueba dos cosas: que `fail2ban-client
-t` acepta la jail, y que el filtro de sshd cuenta los cinco fallos del
log de ataque sin contar los logins correctos. No levanta ninguna jail ni
toca nftables, así que no sustituye a la prueba real en el host.

Cubre el parseo y el conteo, no el bloqueo. El ban en nftables lo aplica
fail2ban con sus propias acciones y hay que verlo en un nodo.

En el host Linux:

```text
make fail2ban-check
```

Devuelve `skipped` fuera de Linux, igual que `make security-check` y
`make tailscale-check`. Comprueba que el paquete está instalado, que la
jail del repo coincide con la desplegada, que `fail2ban-client -t`
acepta la configuración y que el servicio está activo con la jail
`sshd` armada. No imprime IPs baneadas ni datos del tailnet.
