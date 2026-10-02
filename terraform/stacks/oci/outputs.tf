output "instance_ocid" {
  description = "OCID de la instancia del laboratorio."
  value       = oci_core_instance.lab.id
}

output "private_ip" {
  description = "IP privada de la instancia, dentro de la subnet de la VCN compartida."
  value       = oci_core_instance.lab.private_ip
}

output "public_ip" {
  description = <<-EOT
    IP publica EFIMERA de la instancia. Solo como referencia: NO es una via de
    acceso. El NSG y la security list de la subnet no tienen ninguna regla de
    ingress y el firewall del host cierra el resto, asi que entrar por aqui no
    funciona. El acceso real es solo por Tailscale.

    Es efimera porque el limite reserved-public-ip-count del compartment es 1 y
    lo puede gastar otro recurso; al recrear la instancia cambia de valor.
  EOT
  value       = oci_core_instance.lab.public_ip
}

output "workspace_mount" {
  description = "Ruta del workspace en el host (carpeta del disco de arranque)."
  value       = local.workspace_mount
}

output "next_steps" {
  description = "Bootstrap manual posterior al apply."
  value       = <<-EOT
    1. Une Tailscale manualmente con one-off key (ver security/tailscale/README.md) y revocala.
    2. Accede por el tailnet: ssh ${var.admin_user}@<tailnet-host>
    3. Comprueba el firewall: sudo nft list table inet seclab_host   (input policy drop)
    4. Copia .env por SSH sobre el tailnet: scp .env ${var.admin_user}@<tailnet-host>:~/seclab-sbf/.env
    5. Clona este repo en el host y levanta: docker compose up -d

    La IP publica que sale en `terraform output public_ip` NO sirve para entrar:
    todo el ingress esta filtrado a proposito. Si necesitas Consola de OCI,
    usa OCI Console Connection, que va por una sesion gestionada.
  EOT
}
