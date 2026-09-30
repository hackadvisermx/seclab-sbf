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

El `oci_core_volume.workspace` que queda en el state de OCI (50 GB,
`AVAILABLE`) es un resto del diseño anterior: este stack ya no lo gestiona.
Se puede borrar desde la consola cuando se limpie la cuenta.
