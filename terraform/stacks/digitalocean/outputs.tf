output "droplet_id" {
  description = "ID del droplet del laboratorio."
  value       = digitalocean_droplet.lab.id
}

output "droplet_urn" {
  description = "URN del droplet."
  value       = digitalocean_droplet.lab.urn
}

output "workspace_mount" {
  description = "Ruta del workspace en el host (carpeta del disco de arranque)."
  value       = local.workspace_mount
}

output "next_steps" {
  description = "Bootstrap manual posterior al apply."
  value       = <<-EOT
    El droplet conserva IP pública por limitación de DO, pero el firewall
    bloquea TODO lo entrante. Acceso inicial solo por Recovery Console:
    1. Entra por la consola web del panel (no hay SSH público).
    2. Une Tailscale manualmente con one-off key (ver security/tailscale/README.md) y revócala.
    3. Copia .env por SSH sobre el tailnet: scp .env ${var.admin_user}@<tailnet-host>:~/seclab-sbf/.env
    4. Clona este repo en el host y levanta: docker compose up -d
  EOT
}
