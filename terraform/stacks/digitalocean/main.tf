locals {
  name_prefix     = "seclab-sbf-${var.env_name}"
  workspace_mount = "/opt/seclab-sbf/workspace"
  tags            = ["seclab-sbf", var.env_name, "terraform"]
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
    admin_user      = var.admin_user
    admin_password  = var.admin_password
    ssh_public_key  = var.ssh_public_key
    workspace_mount = local.workspace_mount
    # La jail de fail2ban vive en el repo, no aqui: se edita en
    # security/fail2ban/ y `make fail2ban-check` compara la copia
    # del host contra esa.
    seclab_sshd_jail = indent(6, join("", ["\n", file("${path.module}/../../../security/fail2ban/jail.d/seclab-sshd.conf")]))
      # El firewall del host tambien vive en el repo, por el mismo motivo.
      # Se pasa indentado y con un "\n" inicial porque indent() no indenta la
      # primera linea: sin el, la linea "define" de la politica queda en la
      # columna 0 y el YAML no seria valido.
      seclab_nftables_policy = indent(6, join("", ["\n", file("${path.module}/../../../security/policies/nftables-lab.nft")]))
      seclab_nftables_unit   = indent(6, join("", ["\n", file("${path.module}/../../../security/systemd/seclab-nftables.service")]))
  })
}
