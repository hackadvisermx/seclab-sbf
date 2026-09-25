output "instance_ocid" {
  description = "OCID de la instancia del laboratorio."
  value       = oci_core_instance.lab.id
}

output "private_ip" {
  description = "IP privada de la instancia (sin IP pública por diseño)."
  value       = oci_core_instance.lab.private_ip
}

output "workspace_mount" {
  description = "Punto de montaje del volumen de workspace en el host."
  value       = local.workspace_mount
}

output "next_steps" {
  description = "Bootstrap manual posterior al apply."
  value       = <<-EOT
    1. Accede por OCI Console Connection (no hay SSH público).
    2. Une Tailscale manualmente con one-off key (ver security/tailscale/README.md) y revócala.
    3. Copia .env por SSH sobre el tailnet: scp .env ${var.admin_user}@<tailnet-host>:~/seclab-sbf/.env
    4. Clona este repo en el host y levanta: docker compose up -d
  EOT
}
