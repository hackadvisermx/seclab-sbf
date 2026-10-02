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

    Es VM.Standard.A1.Flex (ARM) desde el 2026-10-10, no VM.Standard.E5.Flex.
    El motivo no es preferencia: el limite del compartment es
    standard-e5-core-count = 0 y standard-a1-core-count = 2. La cuota E5 la
    consume la instancia hermes-oci, que es de otro proyecto y sigue
    RUNNING, asi que un E5 no se puede ni pedir. Con A1 sale.

    ARM ademas es lo que hace funcionar la imagen. La del laboratorio se
    construye en arm64 y con A1 el host la usa nativa. Con un shape x86
    habria que construir en amd64, y eso no se puede desde el portatil
    (ver docs/agregar-tools.md 5.12).

    La ratio de memoria: A1.Flex exige entre 1 y 64 GB por OCPU. Con los
    valores de abajo, 2 OCPU y 4 GB, la ratio es 2 GB por OCPU y cumple. El
    apply de reemplazo del 2026-09-29 fallo con "Invalid ratio of memory in
    GB to OCPUs" porque el HCL pedia E5.Flex con esos numeros, que en E5 no
    son validos. Con A1 si lo son.

    Lo que NO se pudo comprobar antes de fijar esto: si hay hosts ARM
    libres en mx-monterrey-1. El apply del 2026-09-29 fallo con "Out of
    host capacity" con la cuota A1 ya en 2, lo que apunta a falta de
    capacidad en la REGION y no a la cuota del compartment. Son dos cosas
    distintas y la API de baremetals no expone los hosts, asi que solo un
    apply lo diria.
  EOT
  type        = string
  default     = "VM.Standard.A1.Flex"
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



variable "shared_vcn_id" {
  description = <<-EOT
    OCID de la VCN compartida donde vive el laboratorio.

    Es una VCN AJENA, la de hermes-oci, y este stack no la gestiona: solo la
    lee con un data source. No hay recurso oci_core_vcn en el stack a
    proposito, para que un destroy nuestro no pueda tocar su red y para que
    el estado de Terraform nosea el dueno de infra de otro proyecto.

    Se referencia por OCID y no por nombre: un rename en la consola no
    rompe el plan ni puede hacer que apunte a otra VCN por error.

    El 10.31.0.0/24 de nuestra subnet lo anadio el owner a mano en la
    consola el 2026-10-10, porque el 10.30.0.0/24 que ya tenia hermes estaba
    ocupado entero por su subnet y no quedaba ni una IP libre.
  EOT
  type        = string
}

variable "subnet_cidr" {
  description = <<-EOT
    CIDR de nuestra subnet dentro de la VCN compartida.

    10.31.0.0/24 es el bloque secundario que el owner anadio a mano a
    hermes-clone-vcn. El 10.30.0.0/24 principal lo ocupa entero la subnet de
    hermes-oci (10.30.0.89), asi que no cabia otra subnet ahi.
  EOT
  type        = string
  default     = "10.31.0.0/24"
}

provider "oci" {
  tenancy_ocid     = var.tenancy_ocid
  user_ocid        = var.user_ocid
  fingerprint      = var.fingerprint
  private_key_path = var.private_key_path
  region           = var.region
}
