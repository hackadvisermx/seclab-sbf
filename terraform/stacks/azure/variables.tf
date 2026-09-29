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
  description = "Tamaño de la VM (2 vCPU / 8 GB por defecto)."
  type        = string
  default     = "Standard_D2s_v5"
}

variable "os_disk_gbs" {
  description = "Disco del SO en GB."
  type        = number
  default     = 50
}

variable "workspace_disk_gbs" {
  description = "Disco de workspace en GB."
  type        = number
  default     = 64
}

variable "workspace_backup_retention_days" {
  description = <<-EOT
    Dias que se conservan los snapshots del disco de workspace.

    El workspace es el unico dato irrecuperable del laboratorio: la imagen
    se reconstruye desde el codigo, pero las notas y resultados de un
    escaneo no. Un 0 lo desactiva, para un entorno desechable donde no
    interese pagar por snapshots.

    OJO: esto solo crea el snapshot inicial. Las copias posteriores hay
    que hacerlas a mano segun docs/backups.md.
  EOT
  type        = number
  default     = 0
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
