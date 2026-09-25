locals {
  name_prefix     = "seclab-sbf-${var.env_name}"
  workspace_mount = "/opt/seclab-sbf/workspace"
  # Ruta estable de Azure para el disco de datos LUN 0.
  workspace_device = "/dev/disk/azure/scsi1/lun0"
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
    admin_user       = var.admin_user
    ssh_public_key   = var.ssh_public_key
    workspace_device = local.workspace_device
    workspace_mount  = local.workspace_mount
  }))
}

resource "azurerm_managed_disk" "workspace" {
  name                 = "${local.name_prefix}-workspace"
  resource_group_name  = azurerm_resource_group.lab.name
  location             = azurerm_resource_group.lab.location
  storage_account_type = "StandardSSD_LRS"
  create_option        = "Empty"
  disk_size_gb         = var.workspace_disk_gbs
  tags                 = local.tags
}

resource "azurerm_virtual_machine_data_disk_attachment" "workspace" {
  managed_disk_id    = azurerm_managed_disk.workspace.id
  virtual_machine_id = azurerm_linux_virtual_machine.lab.id
  lun                = 0
  caching            = "None"
}
