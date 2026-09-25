locals {
  name_prefix     = "seclab-sbf-${var.env_name}"
  workspace_mount = "/opt/seclab-sbf/workspace"
  # Attachment paravirtualizado: sin iSCSI, ruta estable.
  workspace_device = "/dev/oracleoci/oraclevdb"
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
  shape                    = "VM.Standard.E5.Flex"
  sort_by                  = "TIMECREATED"
  sort_order               = "DESC"
}

resource "oci_core_vcn" "lab" {
  compartment_id = var.compartment_ocid
  cidr_blocks    = [var.vcn_cidr]
  display_name   = "${local.name_prefix}-vcn"
  dns_label      = "seclab${var.env_name}"
  freeform_tags  = local.freeform_tags
}

resource "oci_core_nat_gateway" "lab" {
  compartment_id = var.compartment_ocid
  vcn_id         = oci_core_vcn.lab.id
  display_name   = "${local.name_prefix}-nat"
  freeform_tags  = local.freeform_tags
}

resource "oci_core_route_table" "private" {
  compartment_id = var.compartment_ocid
  vcn_id         = oci_core_vcn.lab.id
  display_name   = "${local.name_prefix}-private-rt"
  freeform_tags  = local.freeform_tags

  route_rules {
    destination       = "0.0.0.0/0"
    destination_type  = "CIDR_BLOCK"
    network_entity_id = oci_core_nat_gateway.lab.id
  }
}

resource "oci_core_network_security_group" "lab" {
  compartment_id = var.compartment_ocid
  vcn_id         = oci_core_vcn.lab.id
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

resource "oci_core_network_security_group_security_rule" "egress_dns" {
  network_security_group_id = oci_core_network_security_group.lab.id
  direction                 = "EGRESS"
  protocol                  = "17"
  description               = "DNS del resolver VCN"
  destination               = var.vcn_cidr
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

resource "oci_core_subnet" "private" {
  compartment_id             = var.compartment_ocid
  vcn_id                     = oci_core_vcn.lab.id
  cidr_block                 = var.subnet_cidr
  display_name               = "${local.name_prefix}-private"
  dns_label                  = "privada"
  prohibit_public_ip_on_vnic = true
  prohibit_internet_ingress  = true
  route_table_id             = oci_core_route_table.private.id
  security_list_ids          = [oci_core_vcn.lab.default_security_list_id]
  freeform_tags              = local.freeform_tags
}

resource "oci_core_instance" "lab" {
  compartment_id      = var.compartment_ocid
  availability_domain = data.oci_identity_availability_domain.ad.name
  shape               = "VM.Standard.E5.Flex"
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
    subnet_id        = oci_core_subnet.private.id
    assign_public_ip = false
    nsg_ids          = [oci_core_network_security_group.lab.id]
  }

  metadata = {
    ssh_authorized_keys = var.ssh_public_key
    user_data = base64encode(templatefile("${path.module}/../../modules/lab-cloud-init/cloud.cfg.yaml", {
      admin_user       = var.admin_user
      admin_password   = var.admin_password
      ssh_public_key   = var.ssh_public_key
      workspace_device = local.workspace_device
      workspace_mount  = local.workspace_mount
    }))
  }
}

resource "oci_core_volume" "workspace" {
  compartment_id      = var.compartment_ocid
  availability_domain = data.oci_identity_availability_domain.ad.name
  display_name        = "${local.name_prefix}-workspace"
  size_in_gbs         = var.workspace_volume_gbs
  freeform_tags       = local.freeform_tags
}

resource "oci_core_volume_attachment" "workspace" {
  attachment_type = "paravirtualized"
  instance_id     = oci_core_instance.lab.id
  volume_id       = oci_core_volume.workspace.id
  device          = "/dev/oracleoci/oraclevdb"
}
