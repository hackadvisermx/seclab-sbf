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
    ssh_public_key   = var.ssh_public_key
    workspace_device = local.workspace_device
    workspace_mount  = local.workspace_mount
  })
}

resource "digitalocean_volume" "workspace" {
  name                    = local.volume_name
  region                  = var.region
  size                    = var.workspace_volume_gbs
  initial_filesystem_type = "ext4"
  description             = "Workspace de seclab-sbf (${var.env_name})"
}

resource "digitalocean_volume_attachment" "workspace" {
  droplet_id = digitalocean_droplet.lab.id
  volume_id  = digitalocean_volume.workspace.id
}
