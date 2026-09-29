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
    ├── oci/           # VCN + NAT + NSG + VM Flex + volumen PV
    ├── azure/         # VNet + NAT + NSG deny + VM + disco
    └── digitalocean/  # VPC + firewall deny + droplet + volumen
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

## Pendiente

- `apply` real por proveedor con credenciales del operador.
- Destrucción verificada y limpieza del nodo en el tailnet.
- `tflint`/`tfsec`/Checkov en CI y `terraform plan` en PRs.
