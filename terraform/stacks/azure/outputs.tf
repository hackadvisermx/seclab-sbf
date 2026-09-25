output "vm_id" {
  description = "ID de la VM del laboratorio."
  value       = azurerm_linux_virtual_machine.lab.id
}

output "private_ip" {
  description = "IP privada de la VM (sin IP pública por diseño)."
  value       = azurerm_network_interface.lab.private_ip_address
}

output "workspace_mount" {
  description = "Punto de montaje del disco de workspace en el host."
  value       = local.workspace_mount
}

output "next_steps" {
  description = "Bootstrap manual posterior al apply."
  value       = <<-EOT
    1. Accede por Azure Serial Console (no hay SSH público).
    2. Une Tailscale manualmente con one-off key (ver security/tailscale/README.md) y revócala.
    3. Copia .env por SSH sobre el tailnet: scp .env ${var.admin_user}@<tailnet-host>:~/seclab-sbf/.env
    4. Clona este repo en el host y levanta: docker compose up -d
  EOT
}
