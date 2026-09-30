# Backups y restauración

El workspace es una **carpeta del disco de arranque de la VM**
(`CLOUD_WORKSPACE_DIR`). Hasta el 2026-09-29 era un volumen aparte del
proveedor; se quitó porque un disco de 50 GB se factura aunque la VM esté
apagada. Ver `docs/phase-8.md` para el antes y el después.

La consecuencia es directa y hay que tenerla presente: **el workspace
depende de la vida de la VM**. Si la VM se destruye o se reemplaza, el
workspace se va con ella. El backup es, por tanto, manual y disciplina del
operador, no algo que el proveedor haga por su cuenta.

## Qué proteger y qué no

| Dato | Dónde | ¿Se protege? |
|---|---|---|
| Workspace del laboratorio | carpeta en el disco de la VM | **solo con copia manual** |
| Imagen del laboratorio | se reconstruye en caliente en cada máquina | no hace falta, `seclab.build-inputs` registra de qué código salió |
| `.env` y perfiles `.ovpn` | fuera del repo, sin seguimiento | fuera del alcance de este documento |
| Llaves SSH de Tailscale | fuera del repo | fuera del alcance |

El criterio de siempre: **los secretos no viajan a ningún backup en la
nube**. Un backup que contenga el `.env` o una auth key sería un fichero de
secretos en un tercero, que es justo lo que el diseño evita. La copia sale
de la VM hacia la máquina del operador, no al revés.

## Copia

El workspace se copia desde dentro del contenedor, que es donde vive el
contenido. Se hace con `scp` desde tu máquina, no desde el host:

```bash
# 1. Empaquetar dentro del contenedor
make compose-shell
#   tar czf /tmp/workspace-$(date +%Y%m%d).tar.gz -C /workspace .

# 2. Sacarlo por scp
make lab-ssh   # en otra terminal, para tener el puerto abierto
scp tester@127.0.0.1:/tmp/workspace-20260929.tar.gz ~/
```

O todo desde el host, con `docker cp`:

```bash
cid="$(docker compose -f compose.yaml -f compose.local.yaml ps -q lab)"
docker cp "$cid:/workspace" ~/workspace-$(date +%Y%m%d)
```

El archivo queda en tu máquina, junto a lo que ya tienes. Sin checksum
obligatorio, pero conviene uno si lo vas a guardar mucho tiempo:

```bash
shasum -a 256 ~/workspace-20260929.tar.gz
```

## Restaurar

```bash
# 1. VM levantada y repo clonado
# 2. Entrar al contenedor
make compose-shell

# 3. Restaurar dentro
tar xzf /ruta/al/tar.gz -C /workspace
ls -lh /workspace
```

El workspace arranca vacío en cada VM nueva: `plan.md` dice que no se crean
subdirectorios automáticamente. Si el directorio no existe, el `mkdir` del
cloud-init lo deja listo en el host y el bind mount lo expone al contenedor.

## Antes de tirar la VM

Este es el momento crítico. Si vas a destruir o reemplazar el nodo:

1. **Copia el workspace** con el procedimiento de arriba.
2. **Verifica la copia**: `tar tzf <archivo> | head` para confirmar que
   no está vacío ni corrupto.
3. Solo entonces destruye.

Para ver si el plan va a destruir algo antes de aplicar:

```bash
STACK=oci make tf-destroy-check
```

Ese comando no aplica nada. Sale con código 1 si el plan destruye algo o si
el nodo ya no existe.

## Limpieza

El workspace acumula resultados de escaneos, notas y wordlists extraídas.
Antes de tirar la VM decide qué te llevas y borra el resto:

```bash
make compose-shell
# revisar qué hay
```

`pentest-reset` solo limpia el historial de tmux; **no toca el workspace**.

## Pendiente y límites

- **No hay backup automático.** Es una decisión consciente: el backup
  automático del proveedor implicaba un disco que sobrevive a la VM, y eso
  es lo que se quitó por coste.
- **No se ha probado una restauración en una VM real.** El procedimiento
  está escrito pero no ejecutado de punta a punta.
- **La copia es manual**, así que el riesgo real es humano:olvidar
  hacerlo antes de un `tf-destroy`. Por eso `tf-destroy-check` avisa.
