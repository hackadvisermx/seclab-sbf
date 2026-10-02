locals {
  name_prefix     = "seclab-sbf-${var.env_name}"
  workspace_mount = "/opt/seclab-sbf/workspace"
  freeform_tags = {
    Project     = "seclab-sbf"
    Environment = var.env_name
    ManagedBy   = "terraform"
  }
}

data "oci_identity_availability_domain" "ad" {
  compartment_id = var.tenancy_ocid
  ad_number      = 1
}

data "oci_core_images" "ubuntu" {
  compartment_id           = var.compartment_ocid
  operating_system         = "Canonical Ubuntu"
  operating_system_version = "24.04"
  # El shape va en la variable, no fijo: hardcodearlo fue lo que rompio
  # el nodo el 2026-09-29, cuando el limite del compartment dejo de dar
  # E5 y el apply fallo con "Invalid ratio of memory in GB to OCPUs".
  shape      = var.shape
  sort_by    = "TIMECREATED"
  sort_order = "DESC"
}

# La VCN es AJENA: es la de hermes-oci, y no la gestiona este stack. Solo se
# lee. Se referencia por OCID en una variable, nunca por nombre, para que un
# cambio de nombre en la consola no rompe el plan ni apunta a otra VCN.
data "oci_core_vcn" "shared" {
  vcn_id = var.shared_vcn_id
}

# El internet gateway tambien es ajeno (lo creo hermes) y esta en el limite
# de 1 del compartment, asi que no se puede crear otro. Se busca el que
# pertenece a la VCN compartida en vez de hardcodear su OCID: si alguien lo
# cambia, el plan lo encuentra igual.
data "oci_core_internet_gateways" "shared" {
  compartment_id = var.compartment_ocid
  vcn_id         = data.oci_core_vcn.shared.id
}

# Route table propia dentro de la VCN ajena, en vez de reusar la de hermes.
# Reusarla significaria que nuestro stack depende de reglas que otro puede
# cambiar sin avisar, y que un destroy nuestro podria tocar su red.
resource "oci_core_route_table" "egress" {
  compartment_id = var.compartment_ocid
  vcn_id         = data.oci_core_vcn.shared.id
  display_name   = "${local.name_prefix}-egress-rt"
  freeform_tags  = local.freeform_tags

  route_rules {
    destination       = "0.0.0.0/0"
    destination_type  = "CIDR_BLOCK"
    network_entity_id = data.oci_core_internet_gateways.shared.gateways[0].id
  }
}

# Security list propia y SOLO con egress. La default de la VCN compartida
# permite ingress desde su propia subnet, y su subnet es la de hermes, no la
# nuestra: no sirve. Ademas, con ingress vacio aqui, la garantia de "cero
# puertos de entrada" no depende solo del NSG.
resource "oci_core_security_list" "egress" {
  compartment_id = var.compartment_ocid
  vcn_id         = data.oci_core_vcn.shared.id
  display_name   = "${local.name_prefix}-egress-sl"

  # Ingress: NADNI UNA REGLA. Ni source CIDR 0.0.0.0/0, ni por tag, ni por
  # seguridad. Si alguien anade una aqui, rompe la premisa del diseno.
  egress_security_rules {
    stateless        = false
    protocol         = "all"
    destination      = "0.0.0.0/0"
    destination_type = "CIDR_BLOCK"
  }
}

resource "oci_core_network_security_group" "lab" {
  compartment_id = var.compartment_ocid
  vcn_id         = data.oci_core_vcn.shared.id
  display_name   = "${local.name_prefix}-nsg"
  freeform_tags  = local.freeform_tags
}

# Sin reglas de ingress: nada público. Solo egress mínimo operativo.
resource "oci_core_network_security_group_security_rule" "egress_https" {
  network_security_group_id = oci_core_network_security_group.lab.id
  direction                 = "EGRESS"
  protocol                  = "6"
  description               = "HTTPS: APT, Tailscale, PyPI, Go proxy"
  destination               = "0.0.0.0/0"
  destination_type          = "CIDR_BLOCK"
  tcp_options {
    destination_port_range {
      min = 443
      max = 443
    }
  }
}

resource "oci_core_network_security_group_security_rule" "egress_tailscale_udp" {
  network_security_group_id = oci_core_network_security_group.lab.id
  direction                 = "EGRESS"
  protocol                  = "17"
  description               = "Tailscale WireGuard"
  destination               = "0.0.0.0/0"
  destination_type          = "CIDR_BLOCK"
  udp_options {
    destination_port_range {
      min = 41641
      max = 41641
    }
  }
}

# El resolver de OCI es la .2 del rango, y con la VCN compartida hay DOS
# bloques CIDR (10.30.0.0/24 de hermes y 10.31.0.0/24 nuestro). OCI crea un
# resolver por bloque, asi que se permite DNS a los dos, y solo al .2 de cada
# uno: no se abre a 0.0.0.0/0 porque eso permitiria exfiltrar por DNS.
#
# Se itera sobre cidr_blocks en vez de quedarse con el primero: el orden que
# devuelve la API no esta garantizado y un dia podria venir al reves, lo que
# dejaria el DNS apuntando al bloque equivocado sin que nada lo dijera.
resource "oci_core_network_security_group_security_rule" "egress_dns" {
  for_each = toset(data.oci_core_vcn.shared.cidr_blocks)

  network_security_group_id = oci_core_network_security_group.lab.id
  direction                 = "EGRESS"
  protocol                  = "17"
  description               = "DNS del resolver de la VCN (${each.key})"
  destination               = "${cidrhost(each.key, 2)}/32"
  destination_type          = "CIDR_BLOCK"
  udp_options {
    destination_port_range {
      min = 53
      max = 53
    }
  }
}

resource "oci_core_network_security_group_security_rule" "egress_ntp" {
  network_security_group_id = oci_core_network_security_group.lab.id
  direction                 = "EGRESS"
  protocol                  = "17"
  description               = "NTP"
  destination               = "0.0.0.0/0"
  destination_type          = "CIDR_BLOCK"
  udp_options {
    destination_port_range {
      min = 123
      max = 123
    }
  }
}

# La subnet vive en la VCN compartida. El bloque 10.31.0.0/24 lo anadio el
# owner a mano en la consola el 2026-10-10: el 10.30.0.0/24 que ya tenia
# hermes estaba ocupado entero por su subnet, sin una IP libre para nosotros.
# Por eso este stack no crea la VCN ni su bloque: los lee.
resource "oci_core_subnet" "private" {
  compartment_id = var.compartment_ocid
  vcn_id         = data.oci_core_vcn.shared.id
  cidr_block     = var.subnet_cidr
  display_name   = "${local.name_prefix}-private"
  dns_label      = "seclab"

  # Los dos a false. La IP publica la lleva la VNIC (assign_public_ip) y el
  # NSG y la security list de abajo son solo-egress, de modo que tener IP
  # publica no implica que entre nada. La razon de que esten en false es que
  # en true OCI rechazaria la VNIC.
  prohibit_public_ip_on_vnic = false
  prohibit_internet_ingress  = false

  route_table_id    = oci_core_route_table.egress.id
  security_list_ids = [oci_core_security_list.egress.id]
  freeform_tags     = local.freeform_tags
}

resource "oci_core_instance" "lab" {
  compartment_id      = var.compartment_ocid
  availability_domain = data.oci_identity_availability_domain.ad.name
  shape               = var.shape
  display_name        = "${local.name_prefix}-lab"
  freeform_tags       = local.freeform_tags

  shape_config {
    ocpus         = var.ocpus
    memory_in_gbs = var.memory_gbs
  }

  source_details {
    source_type             = "image"
    source_id               = data.oci_core_images.ubuntu.images[0].id
    boot_volume_size_in_gbs = var.boot_volume_gbs
  }

  create_vnic_details {
    subnet_id = oci_core_subnet.private.id
    # IP publica EFIMERA (la asigna OCI en la VNIC, no se reserva: el limite
    # reserved-public-ip-count del compartment es 1 y lo puede gastar otro).
    # Es lo unico que permite salir a internet con los limites que hay:
    # nat-gateway-count = 0 e internet-gateway-count = 1 ya ocupado.
    #
    # Tener IP publica NO significa estar accesible. El NSG y la security
    # list de la subnet no tienen ninguna regla de ingress, asi que todo lo
    # que llegue se filtra; el firewall del host (nftables, chain input con
    # policy drop) cierra el resto. El acceso real es solo por Tailscale.
    assign_public_ip = true
    nsg_ids          = [oci_core_network_security_group.lab.id]
  }

  # OJO: metadata es un map(string) y el provider lo trata como inmutable.
  # Cualquier cambio en el cloud-init, en la jail de fail2ban o en el
  # user_data hace que este recurso entre en plan como "must be replaced":
  # se destruye la instancia y se crea otra. NO es un refresh y NO toca el
  # volumen del workspace, que es un recurso aparte y sobrevive; lo que se
  # pierde es la sesion de Tailscale y hay que volver a unirlo.
  #
  # Antes de aplicar un plan que diga "must be replaced" en esta instancia:
  #   1. tf-plan y leer si es solo metadata o hay algo mas.
  #   2. Si el workspace importa, el snapshot del stack lo cubre; si no,
  #      el procedimiento manual de docs/backups.md.
  #   3. Tras el apply, rehacer el join de Tailscale con una key one-off y
  #      revocarla. Ver security/tailscale/README.md.
  metadata = {
    ssh_authorized_keys = var.ssh_public_key
    user_data = base64encode(templatefile("${path.module}/../../modules/lab-cloud-init/cloud.cfg.yaml", {
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
    }))
  }
}

