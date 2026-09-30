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

variable "admin_password" {
  description = "Contraseña del admin solo para consola serie (SSH sigue con llave). Vacío la desactiva."
  type        = string
  sensitive   = true
  default     = ""
}

variable "shape" {
  description = <<-EOT
    Shape de la VM del laboratorio.

    Was variable porque hardcodearla fue lo que rompio el nodo: el
    2026-09-29 el apply de reemplazo fallo con "Invalid ratio of
    memory in GB to OCPUs" porque el HCL pedia VM.Standard.E5.Flex y
    ese tenancy no lo tiene. El limite del compartment es
    standard-e5-core-count = 0 y standard-a1-core-count = 2, asi que
    aqui solo hay ARM.

    VM.Standard.A1.Flex es ARM y obliga a construir la imagen del
    contenedor para arm64 en el host. Se probó el 2026-09-29 y el
    apply falló con "Out of host capacity": el limite del compartment
    es standard-a1-core-count = 2 pero no habia hosts ARM libres en
    mx-monterrey-1. E5.Flex (x86) es la que usa el resto del stack.
  EOT
  type        = string
  default     = "VM.Standard.E5.Flex"
}

variable "ocpus" {
  description = "OCPUs de la VM Flex."
  type        = number
  default     = 2
}

variable "memory_gbs" {
  description = <<-EOT
    RAM en GB de la VM Flex.

    Bajada a 8 -> 4 el 2026-09-29. Motivo: al reemplazar el nodo, el
    apply fallo con "Invalid ratio of memory in GB to OCPUs" y los
    limites del compartment dan standard-e5-core-count = 0. En el mismo
    compartment corre hermes-oci con 2 OCPU / 4 GB, asi que 4 GB es lo
    que cabe junto a ella.

    Consecuencia: la imagen `full` del laboratorio (4.5 GB de imagen,
    Metasploit y SecLists) NO entra con 4 GB. Para `full` hace falta mas
    RAM y mas capacidad, o un tenancy con credito.
  EOT
  type        = number
  default     = 4
}

variable "boot_volume_gbs" {
  description = "Tamaño del boot volume en GB."
  type        = number
  default     = 50
}

variable "workspace_backup_retention_days" {
  description = <<-EOT
    Dias que se conservan los backups del volumen de workspace.

    El workspace es el unico dato irrecuperable del laboratorio: la imagen
    se reconstruye desde el codigo, pero las notas y resultados de un
    escaneo no. Un 0 lo desactiva, para un entorno desechable donde no
    interese pagar por backups.

    OJO: la politica que se crea aqui cubre solo el backup inicial que
    dispara el apply. Las copias posteriores hay que hacerlas a mano segun
    docs/backups.md, o configurar una politica de backup recurrent fuera
    de este stack.
  EOT
  type        = number
  default     = 0
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
