# Añadir herramientas al laboratorio

Este documento responde a la pregunta que más aparece en el uso diario: **¿cómo
instalo una herramienta nueva si no tengo `sudo`?**

La respuesta corta es que **no se instalan en runtime, por diseño**. Las
herramientas entran en la imagen, se revisan y solo entonces se usan. Este
documento explica por qué, cómo se hace, y qué trampas hay.

## 1. Por qué no hay `sudo` ni `su`

No es que falte un paquete. Son cuatro mecanismos que se refuerzan entre sí:

| Mecanismo | Efecto |
|---|---|
| `read_only: true` en el servicio `lab` | El rootfs no se escribe, ni siquiera como root |
| `cap_drop: ALL` y `cap_add` mínimo | Sin `CAP_DAC_OVERRIDE` ni `CAP_SYS_CHROOT` no hay escalada |
| `tester` sin password | La cuenta está bloqueada, así que `su` falla siempre |
| `sudo` no está instalado | Y aunque lo estuviera, no habría a qué escalar |

`tester` es el usuario `ubuntu` renombrado con `usermod --login tester`, sin
password por diseño: el acceso es solo por llave SSH.

### La razón de fondo

`make scan-image` solo significa algo si la imagen es auditable. Si `tester`
pudiera instalar paquetes, el contenido real del contenedor sería distinto del
que se revisó, y ni el lockfile ni el escaneo de CVEs valdrían.

El laboratorio asume un modelo distinto al de un contenedor de trabajo: se
reconstruye. Como no hay registry, cada máquina construye en caliente, así que
cambiar la imagen es un `make build-full` y un `make scan-image`.

## 2. Lo que sí es escribible

| Ruta | Qué es |
|---|---|
| `/workspace` | Bind mount del host, persiste, escribible por `tester` |
| `tmpfs` del contenedor | Temporal, se pierde al parar |
| `/vpn` | Perfiles `.ovpn` montados en solo lectura |
| `/run/secrets` | `.env` montado en solo lectura |

Y las rutas de las herramientas que necesitan estado ya resueltas con symlinks
al volumen, porque `/home/tester` es de solo lectura:

| Ruta en el home | Apunta a | La usa |
|---|---|---|
| `~/.msf4` | `/var/lib/seclab/tester/.msf4` | Metasploit |
| `~/.nxc` | `/var/lib/seclab/tester/.nxc` | NetExec |
| `~/.cache` | `/var/lib/seclab/tester/.cache` | wpscan |

**Si añades una tool que escriba en su home, necesita el mismo symlink.** El
error típico es `Read-only file system` en runtime, y no aparece probando con
`docker run`, porque ahí el rootfs no es de solo lectura. Solo lo reproduce el
laboratorio levantado de verdad.

## 3. El procedimiento para añadir una tool

Son cuatro pasos. Ninguno es opcional.

### 3.1 Fijar el origen en el Dockerfile

Dos vías, según de dónde venga la herramienta.

**Desde source, por commit exacto** (para lo que no tiene release binario):

```dockerfile
FROM --platform=$BUILDPLATFORM ${GO_BUILDER} AS go-builder
ARG TARGETOS
ARG TARGETARCH
ARG FOO_COMMIT
RUN git init /src/foo \
 && git -C /src/foo remote add origin https://github.com/…/foo.git \
 && git -C /src/foo fetch --depth 1 origin "${FOO_COMMIT}" \
 && git -C /src/foo checkout --detach "${FOO_COMMIT}" \
 && test "$(git -C /src/foo rev-parse HEAD)" = "${FOO_COMMIT}"
```

**Desde release oficial, con SHA256**, solo si existe para la arquitectura. Se
verifica el hash y se rechaza si no cuadra.

Nunca `latest`, nunca una rama flotante, nunca `releases/latest/download`.

### 3.2 Anotarla en `supply-chain/tools.lock.yaml`

Versión, origen, hash o commit, y la distribución cuando importa. Este fichero
es el inventario real: lo que no está aquí, no está en la imagen.

```yaml
  - name: herramienta
    version: 1.2.3
    source: https://github.com/…
    commit: <sha de 40>
    tag: v1.2.3
```

### 3.3 Darla de alta en `shell/tools.json`

Con las tres claves, sin excepción. Es lo que hace que la tool aparezca en
`pt-help` con su categoría y su descripción.

```json
"herramienta": {
  "category": "forensics",
  "command": "herramienta",
  "description": "Qué hace y cuándo se usa"
}
```

Y añadir el nombre al array del perfil correspondiente, en `profiles`.

Si introduces una categoría nueva, también va en el mapa `categories` y en el
`map()` de `pt-category-summary` del plugin.

### 3.4 Reconstruir y revisar

```bash
make build-full
make scan-image           # el gate de CVEs
```

Si el escaneo encuentra algo, se sube la dependencia a la versión corregida en
el propio Dockerfile, como ya se hace con `pgx` en `s3scanner` y `xpath` en
`bettercap`. No se silencia con una excepción si hay versión corregida.

## 4. El atajo, y lo que cuesta

Dentro de `/workspace` se puede descargar y descomprimir un binario estático
(`curl`, `git` y `p7zip` están en la imagen). Para muchas herramientas de Go y
Rust funciona.

**Lo que se pierde:** ese binario no ha pasado el gate de CVEs, no está en el
lockfile y no sale en `pt-help`. Desaparece del inventario.

Para un script puntual en un entorno desechable, aceptable. Para una tool que
vayas a usar en un engagement, no: que pase por la imagen.

## 5. Trampas reales encontradas

Estas no se deducen de los ficheros, se encontraron construyendo.

### 5.1 Los pines de los builders son de Debian, no de Ubuntu

La imagen `golang` oficial es **Debian trixie**, no Ubuntu. Los pines de apt en
los stages de build son de Debian, y los del runtime son de Ubuntu. No se pueden
intercambiar:

| | Debian trixie (builder) | Ubuntu noble (runtime) |
|---|---|---|
| `gcc` | `4:14.2.0-1` | — |
| `libpcap-dev` | `1.10.5-2` | — |
| `libusb-1.0-0-dev` | `2:1.0.28-1` | `libusb-1.0-0` `2:1.0.27-1` |

En runtime solo tiene que coincidir el *soname* (`libusb-1.0.so.0`).

### 5.2 CGO necesita las cabeceras de sus dos dependencias

`bettercap` depende de `gousb` (libusb) y además arrastra `gopacket/pcap`
(libpcap). Compilar solo con `libusb` falla con `pcap.h: No such file or
directory`. Y `CGO_ENABLED=0` no es opción: `gousb` es dependencia **directa** y
no hay build tag que la excluya, así que no existe build sin cgo.

Por eso el release oficial de `bettercap` solo sirve para `linux_amd64`: en
`arm64` hay que compilarlo, con el mismo patrón de cross-compile que ya usa
`naabu` en la imagen del laboratorio.

### 5.3 Los gems de Ruby se compilan en `msf-builder`, no en la imagen final

`wpscan` y cualquier gem con extensiones nativas (`yajl-ruby`, `ffi`) necesitan
`make`, y la imagen final no lo lleva. Además deben compilarse contra **ese
mismo Ruby**, así que van en `msf-builder` y se copian ya instalados.

Un gem que se quiera aparte del bundle de Metasploit va a su propio
`GEM_HOME`. Y en runtime necesita un wrapper: si el `GEM_HOME` no está en el
entorno de la imagen, el binstub aborta con `Gem::GemNotFoundException`, y
exportarlo en la imagen haría que Metasploit lo viera también.

### 5.4 `make scan-image` necesita `SCAN_TIMEOUT` para `full`

El default de Trivy son 5 minutos por operación, y con `full` se queda corto en
las capas grandes. Sin esto el escaneo muere con `context deadline exceeded`,
que **parece un fallo de CVEs y no lo es**. Está en `SCAN_TIMEOUT` (45m).

### 5.5 Los pins de `apt` no siempre son los de `main`

Comprobar el candidato **con el snapshot configurado**, no leyendo el índice de
`main`. `gdb-multiarch` está en `universe`, y su versión en `main` no existe. El
candidato real sale de `apt-cache policy` dentro de un contenedor con el snapshot
ya puesto, y es el mismo en `amd64` y `arm64` porque el resto de paquetes se
resuelven sin versión explícita: **el snapshot es el mecanismo de pin**, y el
lockfile documenta lo que resuelve.

### 5.6 Los hashes de pip son por versión de Python, no por paquete

Al subir a Ubuntu 26.04, Python pasa de 3.12 a **3.14**, y los ficheros
`pwntools-requirements-*.txt` dejaron de cuadrar. El build lo detectó solo:

```
ERROR: THESE PACKAGES DO NOT MATCH THE HASHES FROM THE REQUIREMENTS FILE
  cffi==2.1.1 from .../cffi-2.1.1-cp314-cp314-manylinux2014_aarch64.whl:
    Expected sha256 68e62fe1...     ← el hash del wheel cp312
      Got        58acb8ab...     ← el hash del wheel cp314
```

Es el **mismo paquete y la misma versión**, con otro binario. Cada
combinación de versión de Python tiene su propio wheel, así que cambiar de
Python obliga a rehacer los dos ficheros:

```sh
pip download --python-version 3.14 --implementation cp --abi cp314 \
             --platform manylinux2014_aarch64 -r requisitos.txt
# y el sha256 de cada .whl descargado
```

Que el build pare por esto es buena noticia: el pin hizo su trabajo.

**Y `--break-system-packages` no salva del `uninstall-no-record-file`.** Si un
pin pide una versión distinta de la que instaló dpkg, pip intenta desinstalar
la del sistema y aborta con *The package's contents are unknown: no RECORD
file was found*. La salida es alinear el pin con la del sistema, que es lo que
se hizo con `packaging`.

### 5.7 En 26.04 cambiaron de nombre cuatro paquetes

| 24.04 | 26.04 | Por qué |
|---|---|---|
| `p7zip-full` | `7zip` | El paquete se renombró; el binario sigue siendo `7z` |
| `dnsutils` | `bind9-dnsutils` | Reempaquetado por BIND 9 |
| `libxml2` | `libxml2-16` | El runtime por la transición a 64-bit `time_t` |
| `python3-setuptools` | (ya no viene) | Ver abajo |

`libxml2` en concreto es un nombre de metapaquete: instalarlo en 26.04 falla
con *"Package 'libxml2' has no installation candidate"*. El runtime es
`libxml2-16`, y `libxml2-16t64` tampoco existe.

**`python3-setuptools` desaparece de la imagen y con ella el `purge`.** En
24.04 venía preinstalada y dpkg la tenía registrada, así que el `apt-get purge`
final funcionaba. En 26.04 no viene, y lo que se desinstala al final es el
`setuptools` que instaló pip en `/usr/local`, que dpkg **nunca registró**:
pedir su purge mata el build con `uninstall-no-record-file`. Por eso la lista
de purgado se reduce a los paquetes que sí registró dpkg.

Y con eso `packaging` desaparece de la imagen, porque `apt-get autoremove` se
lo lleva al ser dependencia de pip. pwntools lo necesita, así que hay que
instalar `python3-packaging` de forma explícita o el `import` falla en
runtime aunque el build pase.

### 5.8 El snapshot tiene que ser POSTERIOR a la imagen base

Este es el que más rato costó y no se ve en los ficheros.

La imagen `ubuntu:26.04` trae `libssl3t64 3.5.5-1ubuntu3.7` ya instalado. Con
el snapshot `20260925T000000Z` (el que tenía el repo en 24.04), ese paquete
**no existe**: el archivo solo tenía `3.5.5-1ubuntu3.5`. Apt no puede ni
bajarlo ni subirlo, así que cualquier etapa que instale `libssl-dev` falla:

```
E: Unable to satisfy dependencies. Reached two conflicting assignments:
   1. libssl-dev=3.5.5-1ubuntu3.5 is selected for install
   2. libssl-dev Depends libssl3t64 (= 3.5.5-1ubuntu3.5)
      but none of the choices are installable
```

El mensaje habla de `3.5.5-1ubuntu3.5`, que es lo que ve el snapshot, y no
dice nada de la `3.7` que ya está en la imagen. Por eso parece una
inconsistencia del archivo cuando en realidad es que **el pin es más viejo que
la imagen**.

La regla: al cambiar la imagen base, el snapshot tiene que ser **posterior** a
la fecha de publicación de esa imagen. Se comprobó `libssl3t64` en varios
snapshots hasta dar con uno coherente:

| Snapshot | `libssl3t64` |
|---|---|
| `20260925T000000Z` | `3.5.5-1ubuntu3.5` (no sirve, la imagen trae 3.7) |
| `20260928T000000Z` | `3.5.5-1ubuntu3.5` |
| `20261001T000000Z` | `3.5.5-1ubuntu3.6` |
| `20261005T000000Z` | `3.5.5-1ubuntu3.7` ✓ |

## 6. Cómo descubrir qué hay ya instalado

`pt-tools` lista lo declarado; para comprobar el estado real de un comando:

```bash
command -v herramienta        # ruta o nada
herramienta --version
```

Una tool puede estar en la imagen y no en `tools.json` (o al revés). Si el
inventario y la imagen discrepan, manda la imagen para lo que se puede
ejecutar, y hay que corregir `tools.json`.

### 5.10 impacket 0.14 no trae los ejecutables, pero NetExec sí

El venv de NetExec trae `impacket 0.14`, y parece la respuesta obvia a
"necesito secretsdump": los ficheros están, en
`.../site-packages/impacket/examples/`. **No son ejecutables**, y no por falta
de permiso: es que ese paquete ya no distribuye la CLI.

Comprobado en la imagen:

```sh
/opt/nxc/bin/python -c "
from importlib.metadata import distribution
d = distribution('impacket')
print(d.metadata['Summary'])
print([e.name for e in d.entry_points if e.group == 'console_scripts'])"
# Network protocols Constructors and Dissectors
# []
```

Es la librería pura. Sus ficheros de `examples/` son módulos que el propio
código de NetExec importa (`from impacket.examples.secretsdump import ...` en
`nxc/protocols/smb.py`), y **no tienen** `if __name__ == "__main__"`, ni
`main()`, ni `parse_args()`, ni entry point.

Esto se intentó y falló dos veces antes de entenderlo:

1. `chmod +x` sobre el fichero: lo deja ejecutable, pero al correrlo no imprime
   nada y sale con **0**. Importado, sin nada que ejecutar.
2. Ponerle shebang a mano: no llevan ninguno, así que sin tocar el upstream los
   ejecutaba `/bin/sh` y fallaba con `import: not found` en cada línea de
   `import`. Con el shebang correcto ya no da error, pero sigue sin hacer nada.

Un wrapper propio tampoco arregla nada: no hay `main()` que llamar.

**Para el volcado de hashes, `nxc` cubre lo mismo** sobre SMB, LDAP y WinRM, y
ya está instalado y auditado.

**Ojo, esto NO significa que no haya CLIs de impacket en la imagen.** Hay dos
conjuntos distintos y confundirlos cuesta un rato:

| Dónde | Qué son | Ejecutables |
|---|---|---|
| `.../site-packages/impacket/examples/` | Módulos de la librería | **No.** Sin `main()`, no hacen nada al ejecutarlos |
| `/opt/nxc/bin/*.py` | Scripts CLI que trae **NetExec** | **Sí.** Con `main()`, `argparse` y shebang `#!/opt/nxc/bin/python3` |

Los segundos son los que se usan contra un objetivo: `netview.py`, `psexec.py`,
`smbexec.py`, `wmiexec.py`, `smbclient.py`, `GetUserSPNs.py`, `getTGT.py`,
`getST.py`, `getPac.py`, `dacledit.py`, `rbcd.py`, `owneredit.py`, `dpapi.py`,
`mimikatz.py`, `secretsdump.py` y compañía. Más `certipy`, que es la vía a
abuso de certificados y viene de la misma venv.

El criterio para exponerlos fue comprobarlos uno a uno, no fiarse del nombre
del fichero: `netview.py -h` imprime su `usage` con sus flags, lo que delata
que tiene `argparse` de verdad. Un módulo de `examples/` no imprime nada.

### 5.11 `tools.json` declara el `command`, no el nombre de la clave

`fd` declara `command: fdfind` y `wireguard` declara `command: wg`, porque esos
son los binarios reales en Ubuntu. Al verificar el manifiesto hay que comparar
contra `tools[k]["command"]`, no contra las claves de `installed`:

```sh
python3 -c 'import json
d = json.load(open("shell/tools.json"))["tools"]
for k in sorted(d): print(d[k]["command"])' > /tmp/cmds.txt
```

Con las claves da dos falsos `AUSENTE: fd` y `AUSENTE: wireguard` que no son
reales: los binarios se llaman `fdfind` y `wg`.

### 5.9 `apt-cache policy` engaña si no pones el snapshot bien

Las imágenes `arm64` de Ubuntu usan `ports.ubuntu.com`, no
`archive.ubuntu.com`. Un `sed` que solo reescriba `archive` deja el `apt-get
update` del snapshot a medias, y entonces **todos** los paquetes aparecen como
inexistentes:

```
jq            AUSENTE
socat         AUSENTE
openvpn       AUSENTE
...           (y 8 más)
```

No es que falten: es que las listas no se descargaron. Para que `apt-cache
policy` diga la verdad hacen falta **los dos pasos del bootstrap**: instalar
`ca-certificates` primero (si no, falla la verificación TLS del snapshot) y
después el `sed`. Sin el primero el error es
`certificate verify failed`, que también se traga los listados.

Comprueba siempre con `grep '^URIs' /etc/apt/sources.list.d/ubuntu.sources` que
los URIs apuntan al snapshot antes de fiarte de un `Candidate:` vacío.

## Referencias

- `plan.md` §3 y §6: arquitectura, cadena de suministro y gates.
- `AGENTS.md`: contrato operativo para agentes.
- `supply-chain/tools.lock.yaml`: inventario real.
- `docs/acceso.html`: guía de acceso y operación.
