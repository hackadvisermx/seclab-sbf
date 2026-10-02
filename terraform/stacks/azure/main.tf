locals {
  name_prefix     = "seclab-sbf-${var.env_name}"
  workspace_mount = "/opt/seclab-sbf/workspace"
  # Ruta estable de Azure para el disco de datos LUN 0.
  tags = {
    Project     = "seclab-sbf"
    Environment = var.env_name
    ManagedBy   = "terraform"
  }
}

resource "azurerm_resource_group" "lab" {
  name     = var.resource_group_name
  location = var.location
  tags     = local.tags
}

resource "azurerm_virtual_network" "lab" {
  name                = "${local.name_prefix}-vnet"
  resource_group_name = azurerm_resource_group.lab.name
  location            = azurerm_resource_group.lab.location
  address_space       = [var.vnet_cidr]
  tags                = local.tags
}

resource "azurerm_subnet" "private" {
  name                 = "${local.name_prefix}-private"
  resource_group_name  = azurerm_resource_group.lab.name
  virtual_network_name = azurerm_virtual_network.lab.name
  address_prefixes     = [var.subnet_cidr]
}

resource "azurerm_public_ip" "nat" {
  name                = "${local.name_prefix}-nat-pip"
  resource_group_name = azurerm_resource_group.lab.name
  location            = azurerm_resource_group.lab.location
  allocation_method   = "Static"
  sku                 = "Standard"
  tags                = local.tags
}

resource "azurerm_nat_gateway" "lab" {
  name                = "${local.name_prefix}-nat"
  resource_group_name = azurerm_resource_group.lab.name
  location            = azurerm_resource_group.lab.location
  sku_name            = "Standard"
  tags                = local.tags
}

resource "azurerm_nat_gateway_public_ip_association" "lab" {
  nat_gateway_id       = azurerm_nat_gateway.lab.id
  public_ip_address_id = azurerm_public_ip.nat.id
}

resource "azurerm_subnet_nat_gateway_association" "lab" {
  subnet_id      = azurerm_subnet.private.id
  nat_gateway_id = azurerm_nat_gateway.lab.id
}

# Sin reglas allow de ingress: la VM no tiene IP pública y el NSG
# niega todo lo entrante de forma explícita.
resource "azurerm_network_security_group" "lab" {
  name                = "${local.name_prefix}-nsg"
  resource_group_name = azurerm_resource_group.lab.name
  location            = azurerm_resource_group.lab.location
  tags                = local.tags

  security_rule {
    name                       = "deny-all-inbound"
    priority                   = 4096
    direction                  = "Inbound"
    access                     = "Deny"
    protocol                   = "*"
    source_port_range          = "*"
    destination_port_range     = "*"
    source_address_prefix      = "*"
    destination_address_prefix = "*"
  }
}

resource "azurerm_network_interface" "lab" {
  name                = "${local.name_prefix}-nic"
  resource_group_name = azurerm_resource_group.lab.name
  location            = azurerm_resource_group.lab.location
  tags                = local.tags

  ip_configuration {
    name                          = "interna"
    subnet_id                     = azurerm_subnet.private.id
    private_ip_address_allocation = "Dynamic"
  }
}

resource "azurerm_network_interface_security_group_association" "lab" {
  network_interface_id      = azurerm_network_interface.lab.id
  network_security_group_id = azurerm_network_security_group.lab.id
}

resource "azurerm_linux_virtual_machine" "lab" {
  name                = "${local.name_prefix}-lab"
  resource_group_name = azurerm_resource_group.lab.name
  location            = azurerm_resource_group.lab.location
  size                = var.vm_size
  admin_username      = var.admin_user
  tags                = local.tags

  disable_password_authentication = true

  admin_ssh_key {
    username   = var.admin_user
    public_key = var.ssh_public_key
  }

  network_interface_ids = [azurerm_network_interface.lab.id]

  os_disk {
    caching              = "ReadWrite"
    storage_account_type = "StandardSSD_LRS"
    disk_size_gb         = var.os_disk_gbs
  }

  source_image_reference {
    publisher = "Canonical"
    offer     = "ubuntu-24_04-lts"
    sku       = "server"
    version   = var.image_version
  }

  custom_data = base64encode(templatefile("${path.module}/../../modules/lab-cloud-init/cloud.cfg.yaml", {
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

