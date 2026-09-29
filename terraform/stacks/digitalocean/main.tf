locals {
  name_prefix     = "seclab-sbf-${var.env_name}"
  volume_name     = "${local.name_prefix}-workspace"
  workspace_mount = "/opt/seclab-sbf/workspace"
  # Ruta estable de DigitalOcean para el volumen por nombre.
  workspace_device = "/dev/disk/by-id/scsi-0DO_Volume_${local.volume_name}"
  tags             = ["seclab-sbf", var.env_name, "terraform"]
}

data "digitalocean_ssh_key" "operator" {
  name = var.ssh_key_name
}

resource "digitalocean_vpc" "lab" {
  name     = "${local.name_prefix}-vpc"
  region   = var.region
  ip_range = var.vpc_cidr
}

# El droplet conserva IP pública (limitación del proveedor); el firewall
# bloquea TODO lo entrante. Sin reglas inbound = deny total.
resource "digitalocean_firewall" "lab" {
  name = "${local.name_prefix}-fw"
  tags = local.tags

  droplet_ids = [digitalocean_droplet.lab.id]

  outbound_rule {
    protocol              = "tcp"
    port_range            = "443"
    destination_addresses = ["0.0.0.0/0", "::/0"]
  }

  outbound_rule {
    protocol              = "udp"
    port_range            = "41641"
    destination_addresses = ["0.0.0.0/0", "::/0"]
  }

  outbound_rule {
    protocol              = "udp"
    port_range            = "53"
    destination_addresses = ["0.0.0.0/0", "::/0"]
  }

  outbound_rule {
    protocol              = "udp"
    port_range            = "123"
    destination_addresses = ["0.0.0.0/0", "::/0"]
  }
}

resource "digitalocean_droplet" "lab" {
  name     = "${local.name_prefix}-lab"
  region   = var.region
  size     = var.droplet_size
  image    = "ubuntu-24-04-x64"
  vpc_uuid = digitalocean_vpc.lab.id
  ssh_keys = [data.digitalocean_ssh_key.operator.id]
  tags     = local.tags

  user_data = templatefile("${path.module}/../../modules/lab-cloud-init/cloud.cfg.yaml", {
    admin_user       = var.admin_user
    admin_password   = var.admin_password
    ssh_public_key   = var.ssh_public_key
    workspace_device = local.workspace_device
    workspace_mount  = local.workspace_mount
    # La jail de fail2ban vive en el repo, no aqui: se edita en
    # security/fail2ban/ y `make fail2ban-check` compara la copia
    # del host contra esa.
    seclab_sshd_jail = indent(6, join("", ["\n", file("${path.module}/../../../security/fail2ban/jail.d/seclab-sshd.conf")]))
  })
}

resource "digitalocean_volume" "workspace" {
  name                    = local.volume_name
  region                  = var.region
  size                    = var.workspace_volume_gbs
  initial_filesystem_type = "ext4"
  description             = "Workspace de seclab-sbf (${var.env_name})"
}

# Snapshot del volumen de workspace. El workspace es el unico dato del
# laboratorio que no se puede reconstruir: la imagen se vuelve a compilar
# desde el codigo, pero las notas y resultados de un escaneo no.
#
# DigitalOcean no ofrece backup programado para volumenes, asi que esto
# solo cubre el estado inicial en el momento del apply. Las copias
# posteriores hay que hacerlas a mano, con el procedimiento de
# docs/backups.md. Con retention 0 no se crea nada.
resource "digitalocean_volume_snapshot" "workspace" {
  count = var.workspace_backup_retention_days > 0 ? 1 : 0

  # Sin region: la hereda del volumen. Pasarla aqui es un error, el
  # snapshot se crea siempre junto al volumen original.
  name      = "${local.name_prefix}-workspace-snapshot"
  volume_id = digitalocean_volume.workspace.id

  tags = [
    local.name_prefix,
    "workspace",
    "backup",
  ]
}
