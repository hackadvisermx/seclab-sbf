# Runbooks de operación

Procedimientos para los fallos que tienen arreglo conocido. Cada uno dice
primero **cómo saber que es ese problema**, porque casi todos se
manifiestan igual: el laboratorio no responde.

Solo se documenta lo que está implementado y comprobado. Donde el
procedimiento no se ha ejecutado nunca, se dice.

## Índice

- [Acceso perdido](#acceso-perdido)
- [fail2ban ha baneado tu nodo](#fail2ban-ha-baneado-tu-nodo)
- [Tailscale no conecta](#tailscale-no-conecta)
- [El laboratorio no arranca](#el-laboratorio-no-arranca)
- [TUN no disponible](#tun-no-disponible)
- [El proxy no conecta](#el-proxy-no-conecta)
- [El nodo de OCI no existe](#el-nodo-de-oci-no-existe)
- [El plan de Terraform quiere destruir algo](#el-plan-de-terraform-quiere-destruir-algo)
- [Destruir el nodo y limpiar el tailnet](#destruir-el-nodo-y-limpiar-el-tailnet)
- [Rotar la llave one-off de Tailscale](#rotar-la-llave-one-off-de-tailscale)
- [Verificaciones de rutina](#verificaciones-de-rutina)

---

## Acceso perdido

**Síntoma:** no llegas al host por SSH ni por `ttyd`.

El nodo no tiene `public_ip` y no publica puertos Docker, así que el único
acceso es por Tailscale. Si el tailnet no responde, no hay puerta
delantera: hay que entrar por la **consola serie** del proveedor.

Por consola serie, en el host:

```bash
systemctl status tailscaled
sudo tailscale status
sudo tailscale ip -4
```

Si `tailscaled` está caído, mira el log y levántalo:

```bash
journalctl -u tailscaled -n 50 --no-pager
sudo systemctl restart tailscaled
```

Si el nodo está vivo pero `ttyd` y SSH del contenedor no responden, mira las
unidades que los exponen:

```bash
systemctl status seclab-ssh-tailnet seclab-ttyd-tailnet
docker compose -f compose.yaml -f compose.local.yaml ps
```

Las unidades son `BindsTo=tailscaled.service`: si Tailscale cae, el puente
se para con ella, a propósito. Por eso la primera pregunta siempre es si
Tailscale está arriba.

**Siempre hay una segunda vía dentro del tailnet:** si te baneó fail2ban el
SSH del host, el `ttyd` del contenedor sigue siendo una entrada
independiente. Ver el runbook siguiente.

## fail2ban ha baneado tu nodo

**Síntoma:** SSH al host dice `Connection refused` o se queda colgado, pero
el nodo está vivo y otros nodos del tailnet entran bien. Suele ocurrir tras
cinco autenticaciones fallidas en diez minutos: una llave equivocada, un
`scp` con la ruta mal puesta o un agente que reintenta.

Por consola serie, o desde el `ttyd` del contenedor:

```bash
sudo fail2ban-client status sshd
sudo fail2ban-client set sshd unbanip 100.x.y.z
```

Unbanear una IP concreta **no reinicia el contador de reincidencia**: si el
nodo sigue fallando, vuelve a ser baneado, y con un ban más largo. Arregla
la causa antes de desbloquear.

Para diagnóstico interactivo, si el cliente no basta:

```bash
sudo fail2ban-client -i
```

La jail no incluye `100.64.0.0/10` en `ignoreip` a propósito: ignorarla la
dejaría sin efecto sobre el único tráfico que alcanza el `sshd`. Ver
[`../security/fail2ban/README.md`](../security/fail2ban/README.md) para por
qué y para los límites del diseño.

**Pendiente de probar:** el ban real en nftables no está verificado
end-to-end. La jail se valida con `make fail2ban-jail-check`, pero que la IP
acabe efectivamente en `nft list ruleset` solo se comprueba provocando cinco
fallos de autenticación contra un nodo real. Hazlo la primera vez que puedas.

## Tailscale no conecta

**Síntoma:** el nodo no aparece en el tailnet tras crearlo.

La unión es **manual a propósito**. El cloud-init preinstala Tailscale con
la llave del repositorio fijada, pero no lo une: la auth key se revoca
después, así que hornearla en la instancia la dejaría en el plan.

```bash
sudo tailscale up --authkey=<one-off-key> --accept-dns=false \
  --advertise-exit-node=false --hostname=seclab-sbf-<env>
```

Y acto seguido, **revoca la key** en la consola de Tailscale. La regla del
proyecto es usar keys de un solo uso, etiquetadas, preaprobadas y con
expiración corta.

Nunca actives Funnel, Exit Node, subnet routes ni rutas DNS automáticas.
Para comprobar que el estado es el esperado:

```bash
make tailscale-check
```

## El laboratorio no arranca

**Síntoma:** `make compose-up` falla o el contenedor no pasa a healthy.

```bash
docker compose -f compose.yaml -f compose.local.yaml ps
docker compose -f compose.yaml -f compose.local.yaml logs --tail 100 lab
```

Causas frecuentes:

**Falta `.env` o no tiene credenciales reales.** `make compose-up` lo exige y
falla a propósito si no está. `make env-init` lo crea desde `.env.example`
sin sobrescribir el que ya exista, y genera las llaves SSH.

**La imagen local no corresponde al código.** Cada máquina construye en
caliente y compara un hash de insumos: si el código cambió desde el último
build, la imagen está obsoleta y hay que reconstruir. Lo dice el propio
salida de `ensure-image`; se fuerza con:

```bash
make rebuild-image LAB_IMAGE=full
```

**Confirma qué imagen está en uso** antes de seguir diagnosticando:

```bash
docker compose -f compose.yaml -f compose.local.yaml ps
docker image inspect -f '{{index .Config.Labels "seclab.build-inputs"}}' seclab-sbf:full
```

## TUN no disponible

**Síntoma:** `vpntry` falla y el servicio VPN no levanta `tun0`.

```bash
make vpn-tun-check
```

Debe mostrar `tun=present`, `tun_interface=tun0 present` y
`net_admin=present`. En macOS, Docker Desktop tiene que exponer
`/dev/net/tun` al contenedor.

**No lo resuelvas con `--privileged` ni con `mknod`.** El servicio VPN lleva
`cap_drop: ALL` más solo `NET_ADMIN` y `CHOWN`, y existe precisamente para
no necesitar privilegios. Si TUN no está disponible, la respuesta es usar un
host Linux con TUN, no relajar el aislamiento.

## El proxy no conecta

**Síntoma:** `pt-forward` arranca pero ninguna conexión sale, o se detiene
solo a los pocos segundos.

```bash
make proxy-doctor
make proxy-status
make vpn-status
```

La causa casi siempre es que **no hay VPN activa**. Los tres proxies exigen
una sesión con `tun0` y validan cada conexión contra la tabla de rutas: sin
túnel, rechazan el destino. Es el comportamiento correcto, no un fallo.

Si la VPN está activa y aún así falla, mira qué ruta ve el host:

```bash
ip route get <destino>
```

Solo vale una ruta por `tun0`. Un destino público, la metadata de la nube o
el rango del tailnet se rechazan siempre, y eso tampoco es un fallo.

Para consumo desde fuera del nodo, el puente host-only:

```bash
make proxy-bridge SERVICE=tcp     # SSH del contenedor, 2222
make proxy-bridge SERVICE=socks   # SOCKS5
make proxy-bridge SERVICE=web     # HTTP/HTTPS/WebSocket
```

En el portátil, el túnel:

```bash
ssh -L 1080:127.0.0.1:1080 usuario@<tailnet-host>
```

Esto se validó de extremo a extremo en un VPS el 2026-09-25. En el host OCI
final el puente **todavía no está habilitado**: es un paso de despliegue
pendiente, no algo que funcione por sí solo.

## El nodo de OCI no existe

**Síntoma:** `STACK=oci make tf-destroy-check` dice `SIN-NODO`, o
`terraform state list` no muestra `oci_core_instance.lab`.

Significa que **no hay instancia**, y el plan va a **crear una de cero**, no
a actualizar la que había. No es una actualización: es un arranque desde
cero.

Qué sobrevive y qué no:

- **El workspace se pierde con la VM.** Es una carpeta del disco de
  arranque, no un volumen aparte. Si la VM no existe, su contenido tampoco.
- **La red sobrevive**: VCN, subred, NAT gateway y security groups.
- **La sesión de Tailscale no está, porque no hay nodo.** Cuando se cree,
  hay que hacer el join con una key one-off nueva y revocarla.

Si la creación falla con `Invalid ratio of memory in GB to OCPUs` y un
`Valid ratio range: 0 - 0`, **no es un problema de memoria**: ese rango
vacío significa que OCI no encuentra hosts libres. Baja la RAM si quieres,
pero no arregla nada. El detalle está en `docs/phase-8.md`.

## El plan de Terraform quiere destruir algo

**Síntoma:** `make tf-plan-oci` termina con `Plan: N to add, N to change, N to destroy`.

Esto **no** es un cambio menor. En el stack de OCI, la instancia lleva
`metadata` con el `user_data` del cloud-init, y el provider de OCI trata ese
`map(string)` como **inmutable**: cualquier cambio en el cloud-init, en la
jail de fail2ban o en las variables que entran, hace que la instancia entre
en el plan como `must be replaced`. Es un reemplazo completo, no un refresh.

Antes de aplicar:

```bash
STACK=oci make tf-destroy-check
```

Ese target imprime el plan y **sale con código 1 si va a destruir algo**.
No aplica nada ni toma decisiones: solo avisa.

Qué se conserva y qué no, según `tf-destroy-check`:

- **El workspace se pierde.** Es una carpeta del disco de arranque, así que
  se va con la VM. **Cópialo antes de aplicar** con el procedimiento de
  `backups.md`. Esto es lo más importante de este runbook.
- **Se pierde la sesión de Tailscale.** Tras el apply hay que rehacer el
  `tailscale up` con una key one-off nueva y revocarla. Ver el runbook de
  Tailscale más abajo.

Si el nodo ya te sirve y solo quieres que el código lo describa, la vía es
`terraform import` en lugar de reemplazar, no un `apply` a ciegas.

## Destruir el nodo y limpiar el tailnet

El objetivo del diseño es que el nodo se pueda tirar sin dejar rastro de
acceso.

1. **Copia el workspace.** Es una carpeta del disco de arranque y `tf-destroy`
   se la lleva. El procedimiento está en [`backups.md`](backups.md).

2. **Destruye por Terraform**, nunca desde la consola del proveedor: así el
   state remoto y los recursos quedan consistentes entre sí. Recuerda que
   el workspace es una carpeta del disco: se va con la VM.

   ```bash
   make tf-destroy-oci
   ```

3. **Limpia el tailnet.** El nodo desaparece del tailnet por sí solo, pero
   conviene comprobarlo y eliminar cualquier dispositivo que quedara
   registrado:

   ```bash
   tailscale status
   ```

4. **Revoca la auth key**, si usaste una.

**Pendiente de probar:** la destrucción nunca se ha ejecutado con
credenciales reales. El único camino para comprobarla es un `apply` y un
`destroy` con un nodo de verdad.

## Rotar la llave one-off de Tailscale

La llave no se guarda en ningún sitio del repo, en `.env`, ni en el state de
Terraform. Si crees que ha quedado expuesta, el procedimiento es:

1. Revócala en la consola de Tailscale. Es lo primero y lo más importante:
   revocar es inmediato.
2. Genera otra, con las mismas condiciones: un solo uso, etiquetada,
   preaprobada y con expiración corta.
3. Única en el nodo afectado, con `tailscale up --authkey=...`.
4. Revócala otra vez.

## Verificaciones de rutina

Antes de dar por bueno un cambio, o cuando sospeches que algo se rompió:

```bash
make verify                  # secretos, Dockerfiles, shell y pines de Actions
make scan-image              # gate de CVEs de la imagen local
make sbom                    # SBOM CycloneDX ligado al hash de insumos
make fail2ban-jail-check     # jail válida y filtro contando fallos
make tf-render-check         # el cloud-init sigue siendo YAML válido
make tflint-check            # los tres stacks (requiere tflint)
```

Los dos últimos en Linux también aplican a un nodo real, con este orden:

```bash
make security-check          # sintaxis nftables (solo Linux)
make tailscale-check         # daemon Tailscale (solo Linux)
make fail2ban-check          # jail desplegada == la del repo, servicio activo
```

`security-check`, `tailscale-check` y `fail2ban-check` devuelven
`skipped` fuera de Linux, y `78` si falta la herramienta. No es un fallo: es
la señal de que el check pertenece a un nodo.
