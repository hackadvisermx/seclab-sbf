# Configuracion de tflint. Version 0.64.0, fijada en el job de Terraform
# de .github/workflows/security.yml junto con su SHA-256.
#
# Solo el ruleset `terraform`, que va embebido en el binario. No se
# activan plugins del registro de tflint a proposito: cada plugin es una
# dependencia mas que descargar en tiempo de ejecucion, y este repositorio
# no los anade para el resto de las herramientas.
config {
  call_module_type = "local"
}

plugin "terraform" {
  enabled = true
}
