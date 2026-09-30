variable "do_token" {
  description = "Token API de DigitalOcean (sensible: por entorno TF_VAR_do_token)."
  type        = string
  sensitive   = true
}

variable "region" {
  description = "Región del datacenter."
  type        = string
  default     = "sfo3"
}

variable "ssh_key_name" {
  description = "Nombre de la clave SSH ya subida a DigitalOcean."
  type        = string
}

variable "ssh_public_key" {
  description = "Clave pública SSH del operador para cloud-init (no es secreto)."
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
  default     = "root"
}

variable "admin_password" {
  description = "Contraseña del admin solo para consola serie (SSH sigue con llave). Vacío la desactiva."
  type        = string
  sensitive   = true
  default     = ""
}

variable "droplet_size" {
  description = "Tamaño del droplet (2 vCPU / 8 GB por defecto)."
  type        = string
  default     = "s-2vcpu-8gb"
}



variable "vpc_cidr" {
  description = "CIDR de la VPC."
  type        = string
  default     = "10.10.0.0/20"
}

provider "digitalocean" {
  token = var.do_token
}
