variable "resource_group_name" {
  description = "Resource group donde se crea todo."
  type        = string
  default     = "seclab-sbf-prod"
}

variable "location" {
  description = "Región Azure."
  type        = string
  default     = "mexicocentral"
}

variable "ssh_public_key" {
  description = "Clave pública SSH del operador (no es secreto)."
  type        = string
}

variable "env_name" {
  description = "Sufijo de entorno para nombres y tags."
  type        = string
  default     = "prod"
}

variable "admin_user" {
  description = "Usuario administrador creado por cloud-init."
  type        = string
  default     = "azureuser"
}

variable "admin_password" {
  description = "Contraseña del admin solo para consola serie (SSH sigue con llave). Vacío la desactiva."
  type        = string
  sensitive   = true
  default     = ""
}

variable "vm_size" {
  description = "Tamaño de la VM (ARM Ampere Altra 2 vCPU / 8 GB por defecto)."
  type        = string
  default     = "Standard_B2ps_v2"
}

variable "image_sku" {
  description = "SKU de la imagen de Ubuntu (server-arm64 para ARM, server para x64)."
  type        = string
  default     = "server-arm64"
}

variable "os_disk_gbs" {
  description = "Disco del SO en GB."
  type        = number
  default     = 50
}



variable "image_version" {
  description = "Versión de la imagen Ubuntu 24.04 (latest = última publicada)."
  type        = string
  default     = "latest"
}

variable "vnet_cidr" {
  description = "CIDR de la VNet."
  type        = string
  default     = "10.0.0.0/16"
}

variable "subnet_cidr" {
  description = "CIDR de la subnet privada."
  type        = string
  default     = "10.0.1.0/24"
}

provider "azurerm" {
  resource_provider_registrations = "none"
  features {}
}
