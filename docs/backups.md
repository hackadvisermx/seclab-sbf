# Backups y restauración

El workspace es una **carpeta del host** montada en `/workspace`. Con `make`
directo es `./workspace` dentro del repo; con `scripts/lab` es la carpeta
**desde la que se lanzó `lab`** (ver abajo). En la nube es
`CLOUD_WORKSPACE_DIR`, la carpeta del disco de arranque de la VM.

Dos antecedentes que explican por qué no hay automatismo: hasta el 2026-09-29
en la nube era un volumen aparte del proveedor, y se quitó porque un disco de
50 GB se factura aunque la VM esté apagada; y el 2026-10-01 se evaluó un volumen
Docker con nombre en local y se descartó. Ver `docs/phase-8.md`.

## Estado completo del dashboard (fase 90)

`make dashboard-backup` copia conjuntamente workspace, `vault.db`, `recon-jobs.db` y `.vault.key`, con el contenedor detenido. `make dashboard-restore BACKUP=...` valida checksum/manifiesto y solo restaura sobre destinos vacíos; revoca sesiones. Estos archivos contienen secretos recuperables y deben permanecer en almacenamiento privado del operador. El backup del workspace descrito abajo no sustituye esta recuperación completa. Ver [procedimiento, pruebas y límites](phase-90.md).

## El workspace se mueve contigo (con `lab`)

Si usas el atajo `lab`, el workspace no es el del repo sino la carpeta desde la
que lo invocas. Eso vale tanto para el backup como para la restauración: lo
que hay que copiar es **la carpeta desde la que lanzas `lab`**, que no tiene por
qué ser el repo.

```bash
cd ~/proyectos/mi-engagement   # el workspace vive aquí
lab up
lab                           # más tarde, desde esta misma carpeta
```

Si lanzas `lab` desde sitios distintos tienes workspaces distintos, y cada uno
es una carpeta normal que se copia como se quiera. `lab workspace-list` y
`lab workspace-export` ya operan sobre el correcto, porque el atajo les pasa la
ruta absoluta.

La consecuencia a tener presente al hacer backup: copiar `./workspace` del repo
puede no ser lo que quieres si llevas tiempo trabajando con `lab` desde otra
carpeta. `lab` sin argumentos imprime la ayuda, no la ruta; para ver cuál es,
`lab workspace-list` la revela en la primera línea, o `SECLAB_WORKSPACE_DIR=...`
si lo fijaste a mano.

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

**Local, que es lo normal:** el workspace es una carpeta del proyecto
(`./workspace`), o sea que sacarla es un `cp` normal. Los targets estan para no
tener que recordar la convencion:

```bash
# copiar todo el workspace a ./salida
make workspace-export ALL=1

# o solo una parte
make workspace-export RUTA=retos/mi-reto
make workspace-export ENG=mi-engagement DEST=./salida-2026-10-01

# empaquetado automatizado con timestamp y checksum SHA-256 (.tar.gz + .sha256)
make workspace-backup
make workspace-backup BACKUP_DEST=~/mis-backups
```

Para restaurar comprobando integridad:

```bash
# restaura y valida el checksum .sha256 si existe
make workspace-restore BACKUP=./backups/workspace-20261003-151920.tar.gz

# si el workspace contiene archivos, exige FORCE=1 para sobreescribir
make workspace-restore BACKUP=./backups/workspace-20261003-151920.tar.gz FORCE=1
```

En la nube el workspace tambien es una carpeta, pero en el disco de la VM, y ahi
no la ves desde tu maquina. Se copia desde dentro del contenedor, con `scp` o
`docker cp`:

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
