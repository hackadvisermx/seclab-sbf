# Backups y restauración

El workspace vive en un **volumen del proveedor**, separado del disco del
sistema. `tf-destroy` lo destruye con el nodo. Lo único que sobrevive a un
`destroy` es un backup explícito.

## Estado actual

Los tres stacks crean un **snapshot inicial del workspace en el momento del
apply**, controlado por `workspace_backup_retention_days` (0 por defecto, o
sea desactivado). Con un valor mayor que cero:

| Stack | Qué crea | Copias posteriores |
|---|---|---|
| OCI | `oci_core_volume_backup_policy` + `_assignment` + `oci_core_volume_backup` | el servicio de backup las hace según la política |
| Azure | `azurerm_snapshot` con `create_option = "Copy"` | manuales |
| DigitalOcean | `digitalocean_volume_snapshot` | manuales |

**Lo que esto no cubre:** el snapshot se crea una vez, en el `apply`. En
DigitalOcean y Azure no hay backup programado, así que las copias
posteriores hay que hacerlas a mano con el procedimiento de abajo.

**En OCI hay una limitación real:** el schema del provider 9.3.0 no deja
fijar la retención en días desde el stack. `expiration_time` es de solo
lectura, y `retention_in_days` no existe en la política. Así que
`workspace_backup_retention_days` en OCI decide **si** se crea el backup,
pero **cuánto se conserva lo fija la política de OCI**, que hay que crear a
mano en la consola. Está anotado en el propio `main.tf`.

Además, el comportamiento real de todo esto **no está verificado**: ningún
stack se ha aplicado con credenciales reales. Solo `validate` y `tflint`.

## Qué proteger y qué no

| Dato | Dónde | ¿Se protege? |
|---|---|---|
| Workspace del laboratorio | volumen del proveedor, montado en la misma ruta del contenedor | sí, es el único dato irremplazable |
| Imagen del laboratorio | se reconstruye en caliente en cada máquina | no hace falta, `seclab.build-inputs` registra de qué código salió |
| `.env` y perfiles `.ovpn` | fuera del repo, sin seguimiento | **no se suben a ningún backup en la nube**; se regeneran |
| Llaves SSH de Tailscale | fuera del repo | nunca en un backup en la nube |
| Claves de API del proveedor | configuración local | nunca en un backup en la nube |

El criterio es que **el backup vive junto al volumen en el mismo proveedor**.
Los secretos no viajan ahí: un backup en la nube que contenga el `.env` o
una auth key sería un archivo de secretos en un tercero, que es justo lo que
el diseño evita.

## Procedimiento manual

### Antes de cualquier `tf-destroy`, o como respaldo periódico

1. Monta el workspace en local y comprueba su tamaño:

   ```bash
   make compose-up
   make compose-shell
   ls -lh /workspace
   ```

2. Copia fuera del volumen, al equipo del operador:

   ```bash
   tar czf ~/seclab-workspace-$(date +%Y%m%d).tar.gz -C /workspace .
   shasum -a 256 ~/seclab-workspace-$(date +%Y%m%d).tar.gz
   ```

   El checksum se anota junto al archivo. Un backup sin verificar no sabe si
   se puede restaurar.

3. Verifica que el tar no está vacío ni corrupto:

   ```bash
   tar tzf ~/seclab-workspace-$(date +%Y%m%d).tar.gz | head
   ```

### Restaurar

1. Levanta el nodo y monta el volumen (los pasos de `docs/phase-8.md`).
2. Copia el tar de vuelta:

   ```bash
   make compose-up
   make compose-shell
   tar xzf ~/seclab-workspace-20260929.tar.gz -C /workspace
   ls -lh /workspace
   ```

3. Si el volumen se creó vacío y hay que formatearlo, el cloud-init lo hace
   solo en el primer arranque. Comprueba que `/workspace` existe antes de
   copiar dentro.

4. Copia también el `.env` y los perfiles `.ovpn`, que **no** vienen del
   backup:

   ```bash
   make env-copy-oci TF_HOST=<tailnet-host>
   make vpn-copy TF_HOST=<tailnet-host>
   ```

## Limpieza

El workspace acumula resultados de escaneos, notas y wordlists extraídas.
Antes de un `destroy` conviene decidir si se conserva algo:

```bash
make compose-shell
# revisar qué hay y qué se quiere quedar
tar czf ~/seclab-workspace-$(date +%Y%m%d).tar.gz -C /workspace .
```

`pentest-reset` solo limpia el historial de tmux; **no toca el workspace**.

## Pendiente

- **Verificar que el snapshot se crea y se restaura.** El HCL valida y
  tflint pasa, pero ningún `apply` se ha ejecutado. Hasta que no haya un
  `plan` y un `apply` con credenciales reales, esto es código sin probar.
- **Backup programado en Azure y DigitalOcean.** Los dos proveedores no lo
  traen para el recurso que se usa aquí. Habría que decidir entre un
  cron externo, una función del proveedor, o aceptar el snapshot inicial y
  documentar el procedimiento manual como la vía real.
- **Fijar la retención en OCI desde el stack**, si se quiere. Requiere
  cambiar de recurso en el provider o aceptar la consola.
- **Cifrado en reposo del backup**: depende del proveedor y del bucket de
  destino, y está sin decidir.
- **Almacenamiento del backup**: hoy los backups se crean junto al volumen,
  en la misma cuenta. Si la cuenta se destruye, se van con él.
- **El nodo de OCI está caído desde 2026-09-29** por falta de cuota de shape,
  así que hoy no hay nada que respaldar en el cloud. El volumen de 50 GB
  sigue ahí. Ver `phase-8.md`.
