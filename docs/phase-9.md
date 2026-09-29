# Fase 9 — Seguridad cloud

## Estado

Parcial. El `sshd` del host queda cubierto por fail2ban con una jail
revisable en el repo y verificable en el host. Siguen pendientes las ACL,
el MFA y el device approval del tailnet, la aplicación del puente
host-only del proxy en el host OCI final y las pruebas externas
controladas.

## Componentes

- `security/fail2ban/jail.d/seclab-sshd.conf`: la jail. Fuente de verdad;
  cada stack se la pasa a cloud-init como `seclab_sshd_jail`, así que el
  host nace con ella y la copia se puede comparar contra el repo.
- `security/fail2ban/README.md`: qué protege, qué no, el riesgo de lockout
  y cómo recuperar el acceso.
- `scripts/security/check-fail2ban.sh`: verificación en el host, expuesta
  como `make fail2ban-check`.
- `security/policies/nftables-lab.nft` y `security/systemd/`: política de
  firewall del host, aplicada y persistente en el host OCI final.

## Jail de sshd

Decisiones que no son obvias en el archivo:

- `backend = systemd` sin `logpath`. El host no corre rsyslog, así que
  `/var/log/auth.log` no existe; fail2ban declara inválido combinar este
  backend con un `logpath`.
- `banaction = nftables-multiport`. El default de `jail.conf` es
  `iptables-multiport`, que en Ubuntu 24.04 acaba delegando en nftables
  por la capa iptables-nft. Fijarlo evita depender de esa traducción.
  fail2ban usa su propia tabla `f2b-table`, separada de
  `inet seclab_security` del laboratorio: borrar o recargar una no
  afecta a la otra.
- `ignoreip = 127.0.0.1/8 ::1`. La jail solo ve tráfico que llega por
  Tailscale, pero **no** se ignora `100.64.0.0/10`: hacerlo la dejaría sin
  efecto sobre el único tráfico que alcanza el `sshd`. El riesgo
  contrario, que un nodo se banee a sí mismo, se acota banning por IP
  (nunca por subred) y con `ignoreself`, que viene activo por defecto.
- `bantime` incremental x2 hasta una semana, con `rndtime` de 10 min.
  Tras cinco fallos en diez minutos el ban es de una hora.

## Límites

- fail2ban protege el `sshd` del **host**, no el del contenedor: los logs
  del contenedor no salen de él. Cubrirlo exigiría reenviar el journal o
  exponer el log, y no compensa: el contenedor es solo con llaves, tiene
  `MaxAuthTries 3` y no publica puertos.
- Tampoco cubre `ttyd` del contenedor, que va por el puente host-only.
- fail2ban no sustituye a las ACL, al MFA ni al device approval de
  Tailscale. Es la tercera línea, no la primera.
- No se aplica nada automáticamente desde el repositorio: cloud-init
  instala y habilita el servicio, y la comprobación es de solo lectura.

## Verificación

En el host Linux:

```text
make fail2ban-check
```

Devuelve `skipped` fuera de Linux, igual que `make security-check` y
`make tailscale-check`. Comprueba que el paquete está instalado, que la
jail desplegada es idéntica a la del repo, que `fail2ban-client -t`
acepta la configuración y que el servicio está activo con la jail
`sshd` armada. No imprime IPs baneadas ni datos del tailnet.

En esta fase se ejecutó además el renderizado del cloud-init de los tres
stacks y se comprobó que la jail resultante es idéntica byte a byte a
`security/fail2ban/jail.d/seclab-sshd.conf`.

## Pendiente

- ACL del tailnet en modo deny por defecto, MFA y device approval.
- Habilitar el puente host-only del proxy en el host OCI final.
- Pruebas externas controladas desde fuera del tailnet.
- `tflint`/`tfsec`/Checkov en CI para los stacks.
