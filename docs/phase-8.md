# Fase 8 — Terraform cloud

## Estado

Stacks declarativos para OCI, Azure y DigitalOcean con la topología
endurecida validada manualmente: red privada, sin SSH público, egress
mínimo y volumen de workspace. Sin `apply` real en esta fase: el código
está validado (`fmt`, `init`, `validate`) y el despliegue queda para el
operador con credenciales propias.

## Estructura

```text
terraform/
├── modules/lab-cloud-init/cloud.cfg.yaml   # cloud-init compartido, sin secretos
└── stacks/
    ├── oci/           # VCN + NAT + NSG + VM Flex
    ├── azure/         # VNet + NAT + NSG deny + VM + disco
    └── digitalocean/  # VPC + firewall deny + droplet
```

Cada stack fija Terraform `>= 1.16.0`, su provider por versión exacta y
genera `.terraform.lock.hcl` versionado. El state es remoto nativo por
proveedor (S3-compatible en OCI/Spaces, `azurerm` en Azure); las
credenciales van por entorno y el `backend.hcl` vive en `deploy/`
(ignorado, con `.example` por stack).

## Topología común

- Subnet privada sin IP pública en la VM (DO: el proveedor asigna IP
  pública sí o sí; el firewall bloquea todo lo entrante).
- Sin reglas de ingress; egress mínimo: 443/tcp, 41641/udp (Tailscale),
  53 y 123/udp.
- Volumen de workspace formateado y montado por cloud-init.
- cloud-init instala docker/socat/make/git/nftables, Tailscale preinstalado
  (paquete fijado `tailscale=1.102.4` + llave del repo fijada en el módulo)
  y endurece con unattended-upgrades. **No une Tailscale**: eso sigue
  siendo manual por consola con one-off key (ver `security/tailscale/README.md`).

## Flujo de despliegue

```bash
cp terraform/stacks/oci/backend.hcl.example deploy/backend-oci.hcl  # completar
make tf-plan-oci
make tf-apply-oci
# 1. consola del proveedor (sin SSH público) 2. Tailscale manual 3. revocar key
make env-copy-oci TF_HOST=<tailnet-host>
ssh <admin>@<tailnet-host>  # clonar repo y: docker compose up -d
```

`scripts/cloud/tf.sh` nunca recibe el `.env` de ejecución. El state
remoto puede conservar valores sensibles aunque sean `sensitive`.

## Verificación realizada

- `terraform fmt -check -recursive terraform/` pasa.
- `terraform init -backend=false` + `validate` pasan en los 3 stacks.
- `make verify` y `make compose config` sin cambios.

## Runbooks

El procedimiento de despliegue está arriba; los de operación y destrucción,
en [`runbooks.md`](runbooks.md). Para backups y
restauración del workspace, [`backups.md`](backups.md).

## Estado real de OCI (verificado 2026-09-29)

Hay un **nodo desplegado**: `seclab-sbf-prod-lab`, en `mx-monterrey-1`, creado
el 2026-09-25. El state remoto tiene 14 recursos y el provider se
autentica con `~/.oci`, sin variables `TF_VAR_`.

Su `tf-plan` pide **reemplazar la instancia** (`2 to add, 0 to change, 2 to
destroy`). La causa está aislada: `metadata.user_data` es un `map(string)` que
el provider de OCI trata como inmutable, y el nodo se creó con un
cloud-init anterior al actual (sin la jail de fail2ban, con el `mkdir` del
workspace fusionado en la línea de `iscsid`).

Lo que NO pasa, pese a lo que sugiere el plan:

- **No se asigna IP pública.** `assign_public_ip = false` está en
  `create_vnic_details` y no aparece entre los cambios. El `+ public_ip` del
  plan es un atributo calculado a nivel de instancia, no una petición.

Lo que sí se pierde si se aplica: la sesión de Tailscale, y hay que rehacer
el join. El volumen del workspace sobrevivia entonces porque era un recurso aparte; desde el 2026-09-29 ya no lo es.

`make tf-destroy-check` existe para que nadie lea esto por primera vez
justo después de un `terraform apply`.

## Estado del nodo OCI: CAIDO (2026-09-29)

**No hay instancia.** El recurso `oci_core_instance.lab` no existe, ni en el
state ni en OCI. Lo que sobrevive:

| Recurso | Estado |
|---|---|
| `oci_core_volume.workspace` (50 GB) | `AVAILABLE`. **Obsoleto**: ya no lo crea este stack, ver más abajo |
| VCN, subred, NAT gateway, NSG y sus reglas | intactos |
| `oci_core_instance.lab` | **no existe** |

### Qué pasó

Al reemplazar el nodo, cuyo `user_data` era anterior al cloud-init actual, la
creación falló cuatro veces seguidas, siempre por cuota de shape:

```text
Error: 400-InvalidParameter, Invalid ratio of memory in GB to OCPUs.
Current ratio: 4.0. Valid ratio range: 0 - 0
```

Bajar la memoria de 8 a 4 GB cambió la ratio a 2.0 y el error siguió siendo
`0 - 0`. Ese rango vacío no es un problema de ratio: significa que OCI no
encuentra ningún host donde calcularla.

Medido en el compartment durante los intentos:

```text
standard-e5-core-count     = 0     (0 OCPU disponibles)
standard-e5-memory-count   = 0
hermes-oci                 RUNNING  VM.Standard.E5.Flex, 2 OCPU / 4 GB
```

`hermes-oci` ocupa la cuota E5 del compartment. **El error no lo causa este
stack ni el `memory_gbs`**: es que no queda E5 disponible.

Con `VM.Standard.A1.Flex`, que sí tiene 2 OCPU y 12 GB libres, el error fue
otro y de otro tipo:

```text
Error: 500-InternalError, Out of host capacity.
```

Cuota sobrante pero sin hosts ARM libres en la región en ese momento. Es un
error transitorio, a diferencia del de E5.

### Vías para recuperarlo

1. **A1 Flex**: reintentar cuando haya hosts ARM libres. Obliga a construir la
   imagen del contenedor para arm64 en el host, no amd64.
2. **Subir el límite E5** desde Limits → *Request a service limit increase*.
   Necesita en total lo que ya consume `hermes-oci` más lo nuevo. Puede
   requerir cuenta de pago.
3. **`VM.Standard.E2.1.Micro`**: 1 GB de RAM, insuficiente para el laboratorio
   (`light` pesa 1,55 GB en disco y `full` 4,5 GB, y encima corre Docker).
   Descartado por rendimiento, no por cuota.

### El bug que casi lo evita

`make tf-destroy-check` avisaba de las destrucciones, pero cuando el nodo ya
no existe el plan sale `2 to add, 0 to destroy` y el check **no decía nada**.
Así que avisó de laInstance pero no del nodo perdido. Corregido en la misma
fase: ahora comprueba que el recurso principal exista en el state y sale con
código 1 si falta.

## Pendiente

- **Recuperar el nodo de OCI**, que ahora no existe. Requiere cuota de shape que hoy no hay; ver el apartado de arriba.
- Snapshot del workspace verificado en un apply real. Los tres stacks lo
  crean en el `apply` y validan, pero no se ha ejecutado ninguno.
- Backup programado en Azure y DigitalOcean; hoy son manuales. En OCI la
  retención la fija la política creada a mano. Ver `docs/backups.md`.
- Destrucción verificada y limpieza del nodo en el tailnet.
- `tflint`/`tfsec`/Checkov en CI y `terraform plan` en PRs.

## Cambio del 2026-09-29: el workspace es una carpeta

Los tres stacks dejaron de crear un volumen para el workspace. Ahora
`CLOUD_WORKSPACE_DIR` es una **carpeta del disco de arranque** de la VM, y
cloud-init solo hace `mkdir` más `chown`.

Qué cambia, sin rodeos:

| | Antes | Ahora |
|---|---|---|
| Recurso | `oci_core_volume` / `azurerm_managed_disk` / `digitalocean_volume` + su attach | ninguno |
| Snapshot en el apply | política + backup (OCI), snapshot (Azure, DO) | ninguno |
| Coste | disco de 50 GB facturado aunque la VM esté apagada | nada extra |
| Si se recrea la VM | el workspace sobrevive | **el workspace se pierde** |
| Backup | automático en OCI, manual en los demás | manual en todos, con `scp` |

El motivo de quitarlo: un disco de 50 GB se factura aunque apagues la VM, y
"apagar para no pagar" no era una opción. El precio es que **el workspace
depende de la vida de la VM**, así que el backup pasa a ser disciplina, no
infraestructura. El procedimiento está en `docs/backups.md`.

El `oci_core_volume.workspace` (50 GB) era un resto del diseño anterior. Se
borró desde la consola de OCI el 2026-09-30, así que ya no se paga ese disco.

## Limpieza total del stack de OCI (2026-10-01)

Con el volumen ya borrado a mano, se quitó del state la entrada huérfana y se
destruyó todo lo nuestro. El stack de OCI quedó **vacío**, sin recursos.

> Esto describe el stack **anterior**. El stack nuevo (VCN compartida, PR #66)
> creó 9 recursos de red el 2026-10-02 que también se destruyeron, el
> 2026-10-03. El estado que importa hoy está en *Estado final: sin recursos*,
> más abajo. Que una sección diga "vacío" no significa que el stack actual lo
> esté: por eso conviene leer esa antes de concluir nada.

Lo que se hizo, en este orden:

1. `terraform state rm oci_core_volume.workspace oci_core_instance.lab`.
   El volumen ya no existía en la nube (verificado con `oci bv volume list`,
   cero resultados) y el nodo tampoco. `state rm` no toca la nube: solo
   quita las entradas del state. **Estas dos entradas eran la causa de que
   `tf-destroy-check` saliera con 1**: el recurso del volumen ya no está en
   `main.tf`, así que el plan no lo contaba como destrucción, pero tampoco
   desaparecía solo.
2. `terraform plan -destroy` en seco: `0 to add, 0 to change, 9 to destroy`.
   Los 9 eran VCN, subnet, NAT, route table, NSG y sus 4 reglas de egress,
   todos con prefijo `seclab-sbf-prod`.
3. `terraform apply` del plan guardado: `Resources: 0 added, 0 changed, 9
   destroyed`.

Verificado en la nube después, no solo en el state:

| Recurso | Antes | Ahora |
|---|---|---|
| VCN `seclab-sbf-prod-vcn` | `AVAILABLE` | **no existe** |
| NAT `seclab-sbf-prod-nat` | `AVAILABLE` | **no existe** |
| Volúmenes del compartment | 0 | 0 |
| `terraform state list` | 12 entradas | **vacío** |

### Lo que NO se tocó, y por qué

El compartment de la tenancy **no es solo nuestro**. Hay recursos de otros
trabajos, y este repositorio no los gestiona:

| Recurso | Estado | Por qué no se toca |
|---|---|---|
| `hermes-oci` (instancia) | `RUNNING` | Consume la cuota `standard-e5-core-count` del compartment. Es la razón de que el nodo del laboratorio no se pudiera recrear |
| `hermes-clone-vcn` | `AVAILABLE` | Otro proyecto |
| `seclab-cloud-20260924154553` + su `-nat` | `AVAILABLE` | Nombre parecido al nuestro, pero no es de este repo: no está en el state y no usa el prefijo `seclab-sbf-prod` |

Que `hermes-oci` siga viva es la razón de que el despliegue siga bloqueado:
sin OCPU libre en el compartment, `oci_core_instance.lab` da `Out of host
capacity` aunque el stack esté entero y correcto.

### Estado del guard tras la limpieza

`STACK=oci make tf-destroy-check` **sigue saliendo con 1**, y es lo correcto:
el plan es `10 to add, 0 to change, 0 to destroy`, o sea que solo crearía, y
el aviso `SIN-NODO` aparece porque `oci_core_instance.lab` no está en el
state. Ese aviso nació para el 2026-09-29, cuando el nodo se perdió sin
avisar; ahora describe el estado que se ha pedido a propósito. **Que salga con
1 no significa que haya un problema**: significa que aún no se ha
desplegado.

El siguiente despliegue es un apply desde cero, y habrá que rehacer el join
de Tailscale del nodo nuevo.

## Topologia final: VCN compartida, IP publica efimera, cero ingress (2026-10-10)

La red cambio porque los limites del compartment no dejaron otra via. Los tres
que bloqueaban, medidos con la API de limits:

| Limite | Valor | Consecuencia |
|---|---|---|
| `nat-gateway-count` | **0** | No se puede crear NAT gateway |
| `internet-gateway-count` | **1** | Ya lo usa `hermes-clone-igw`; no hay para uno nuestro |
| `standard-e5-core-count` | **0** | La consume `hermes-oci`, que sigue `RUNNING`; solo hay ARM (A1 = 2 OCPU libres) |

La solucion tiene tres partes:

1. **VCN compartida.** El stack ya no crea `oci_core_vcn`, ni NAT, ni internet
   gateway. Usa `hermes-clone-vcn` por data source (`var.shared_vcn_id`,
   requerido y sin default: si falta, el plan para con un error claro en vez
   de adivinar). De esa VCN solo existe su bloque `10.30.0.0/24`, ocupado
   entero por la subnet de hermes, asi que el owner anadio a mano
   **`10.31.0.0/24`** y ahi va nuestra subnet.
2. **Salida por el IGW compartido.** Route table propia (no se reusa la de
   hermes, para que un destroy nuestro no toque su red) con `0.0.0.0/0`
   apuntando a `hermes-clone-igw`, que se busca por data source en vez de
   hardcodear el OCID.
3. **IP publica efimera con cero ingress.** `assign_public_ip = true` en la
   VNIC, que es lo unico que permite salir con `nat-gateway-count = 0`. No
   consume `reserved-public-ip-count` porque es efimera. En compensacion hay
   TRES capas sin ingress:
   - el NSG del stack solo tiene 4 reglas de **egress** (443, UDP 41641, DNS, NTP),
   - la security list de la subnet se creo nueva y solo con egress: la default
     de la VCN compartida permite ingress desde su propia subnet, que es la de
     hermes, no la nuestra, asi que no sirve,
   - y `security/policies/nftables-lab.nft` anade `table inet seclab_host` con
     `chain input` en **`policy drop`**, que el cloud-init despliega y
     `seclab-nftables.service` mantiene persistente.

Ninguna depende de las otras dos: aunque alguien anadiera una regla de ingress
por error en el NSG, el `input` del host sigue sin dejar entrar nada. La IP
publica es scaneable, pero no responde a nada. El acceso real es **solo por
Tailscale**, como antes.

### Estado final: sin recursos, por decision del owner

El `apply` del 2026-10-02 creo 9 recursos en `hermes-clone-vcn` (subnet,
route table, security list, NSG y 5 reglas de seguridad: 2 DNS por
`for_each`, HTTPS, NTP y Tailscale) pero **no** creo instancia, porque A1.Flex
devuelve `Out of host capacity` en `mx-monterrey-1`. Esos 9 se destruyeron el
**2026-10-03** con `terraform destroy`, por decision del owner: el proyecto se
usa **solo en local** y no habra despliegue en nube.

`terraform state list` devuelve **0 entradas**.

Verificado en la nube despues del destroy, no solo en el state:

| Recurso | Estado tras el destroy |
|---|---|
| subnet `10.31.0.0/24` nuestra | no existe |
| route table `egress` nuestra | no existe (quedan las de hermes) |
| security list `egress` nuestra | no existe (quedan las de hermes) |
| network security group `lab` | no existe (no queda ningun NSG) |
| NSG security rules | no existen |
| `oci_core_instance.lab` | nunca existio |

Lo que **no** se toco, verificado en el mismo compartment:

| Recurso | Estado | Por que sigue |
|---|---|---|
| `hermes-oci` (instancia) | `RUNNING` | otro proyecto, consume la cuota del compartment |
| `hermes-clone-vcn` | `AVAILABLE` | otro proyecto; es data source, no recurso gestionado |
| `hermes-clone-rt`, `hermes-clone-egress-only` | `AVAILABLE` | de hermes: se leen, no se gestionan |
| `seclab-cloud-20260924154553` + su NAT | `AVAILABLE` | nombre parecido al nuestro, no es de este repo |

### Dos avisos para quien intente desplegar despues

1. **El compartment no tiene `standard-e5-core-count`**: 0 OCPU, consumidos
   por la instancia `hermes-oci`, que es de otro proyecto y sigue `RUNNING`.
   A1 Flex tampoco hosts: da `Out of host capacity`. El despliegue esta
   bloqueado por cuota, no por el stack.
2. **El CIDR `10.31.0.0/24` ya no esta en la VCN compartida.** El owner lo
   habia anadido a mano y hoy `oci network vcn get` responde `ip-v4-cidr-blocks`
   vacio. Nuestro stack nunca lo gestiona (no hay recurso de CIDR secundario en
   el codigo y el plan de destruccion solo listaba los 9 recursos nuestros),
   asi que lo quito quien administra esa VCN. Habria que volver a anadirlo
   antes de un apply.

Consecuencia asumida: la politica nftables y el cloud-init **nunca llegaron a
desplegarse en ningun nodo**. `security/policies/nftables-lab.nft` esta escrito
y validado en local, pero que su `chain input` en `policy drop` bloquee de
verdad el trafico sigue **sin comprobarse**: hace falta una instancia, y no la
hay.

### Lo que este stack NO gestiona

`hermes-clone-vcn`, su IGW y su route table son de otro proyecto. Se leen, no
se tocan: no hay recurso de Terraform que los gestione. Si se borran desde el
otro proyecto, el laboratorio pierde salida a internet, y con ella Tailscale.
Es una dependencia externa aceptada, documentada y sin aislar.

### DNS

Con dos bloques CIDR en la VCN hay dos resolvers, asi que la regla
`egress_dns` se genera con `for_each` sobre `cidr_blocks` en lugar de apuntar a
uno fijo. Apunta al `.2` de cada bloque, no a `0.0.0.0/0`: abrir DNS a todo
permitiria exfiltrar datos por consultas.

## Estado real de Azure (desplegado y verificado 2026-10-04)

Hay un **nodo desplegado y verificado**: `seclab-sbf-prod-lab`, en `mexicocentral` (Resource Group `seclab-sbf-prod`), creado en la rama `phase/55-azure-cost-optimized`.

### Topología y Optimización de Costos

- **Shape de la VM**: `Standard_D2as_v4` (AMD EPYC™ 7742, 2 vCPU, 8 GB RAM, 50 GB SSD). La opción ARM `Standard_B2ps_v2` se descartó porque Azure aún no dispone de la serie B2ps en la región `mexicocentral`.
- **Arquitectura de Costo Optimizado**: Se eliminó el recurso `azurerm_nat_gateway` y su asociación pública (ahorro directo de ~$32.40 USD/mes). La VM utiliza una IP pública estándar (`158.23.145.139`) asociada directamente a la interfaz de red para salida a internet (**egress-only**).
- **Zero Ingress Enforced**: El acceso público está completamente cerrado a través del NSG (`deny-all-inbound` con prioridad 4096) y del firewall nftables en el host (`table inet seclab_host` con `policy drop`).
- **State remoto**: Backend Azure Blob Storage configurado en `seclab-tfstate-rg/seclabtfstate96fb/tfstate` con permisos `600` en `deploy/backend-azure.hcl`.

### Conectividad y Endurecimiento

- **Tailscale**: Conectado a la tailnet con hostname `seclab-sbf-prod` y dirección IPv4 `100.111.178.40`.
- **Firewall nftables**: Servicio `seclab-nftables.service` activo y verificado en el host; solo permite tráfico en `lo` y `tailscale0`.
- **Fail2ban**: Servicio `fail2ban.service` activo protegiendo sshd en el host.
- **Docker & Compose**: Docker 29.1.3 y plugin Compose v5.5.1 instalado con checksum SHA-256 verificado.

### Corrección en Cloud-Init (Fase 55)

Durante el arranque inicial se detectó que `cloud.cfg.yaml` fallaba al procesar `runcmd` (`TypeError: Unable to shellify type 'dict'`) debido a que la regla `echo 'ATENCION: ...'` incluía dos puntos seguidos de espacio, interpretado por el parser YAML como un diccionario.
- Se entrecomilló el comando en `terraform/modules/lab-cloud-init/cloud.cfg.yaml`.
- Se incorporó validación estricta de tipos (`str` o `list`) en `scripts/verify/check-tf-render.sh`.

### Laboratorio y Publicación de Imagen

- La imagen del laboratorio `seclab-sbf:full` se construyó de forma nativa en la VM (`linux/amd64`) en ~6 minutos.
- Se publicó en Docker Hub bajo `hackadvisermx/sec-lab`:
  - Base: `hackadvisermx/sec-lab:base-amd64-a5a032f1d5cda709`
  - Full: `hackadvisermx/sec-lab:26.04-amd64-a5a032f1d5cda709` (Digest: `sha256:12eaf8d5717d65d26bccf550d26a101260c632104b8186b57f9f01e1cbc9536e`).
- Se ejecutó `docker logout` y eliminación inmediata del archivo de credenciales en la VM.
- Puentes Tailscale (`seclab-ssh-tailnet` en puerto 2222 y `seclab-ttyd-tailnet` en puerto 7681) activos y probados exitosamente.

### Control de Energía

- Para ahorro de costos, la VM se gestiona con `make vm-stop-az` (ejecuta `az vm deallocate`, liberando vCPU y memoria para llevar el cobro a $0.00 USD/h), `make vm-start-az` y `make vm-status-az`.
