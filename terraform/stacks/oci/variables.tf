variable "tenancy_ocid" {
  description = "OCID del tenancy OCI."
  type        = string
}

variable "user_ocid" {
  description = "OCID del usuario IAM que ejecuta Terraform."
  type        = string
}

variable "fingerprint" {
  description = "Huella de la clave API del usuario IAM."
  type        = string
}

variable "private_key_path" {
  description = "Ruta a la clave privada API (nunca su contenido)."
  type        = string
}

variable "region" {
  description = "Región OCI."
  type        = string
  default     = "mx-monterrey-1"
}

variable "compartment_ocid" {
  description = "OCID del compartment donde se crea todo."
  type        = string
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
  default     = "ubuntu"
}

variable "ocpus" {
  description = "OCPUs de la VM Flex."
  type        = number
  default     = 2
}

variable "memory_gbs" {
  description = "RAM en GB de la VM Flex."
  type        = number
  default     = 8
}

variable "boot_volume_gbs" {
  description = "Tamaño del boot volume en GB."
  type        = number
  default     = 50
}

variable "workspace_volume_gbs" {
  description = "Tamaño del volumen de workspace en GB."
  type        = number
  default     = 50
}

variable "vcn_cidr" {
  description = "CIDR de la VCN."
  type        = string
  default     = "10.0.0.0/16"
}

variable "subnet_cidr" {
  description = "CIDR de la subnet privada."
  type        = string
  default     = "10.0.1.0/24"
}

provider "oci" {
  tenancy_ocid     = var.tenancy_ocid
  user_ocid        = var.user_ocid
  fingerprint      = var.fingerprint
  private_key_path = var.private_key_path
  region           = var.region
}
