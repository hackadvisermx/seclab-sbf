# Workspace del laboratorio

Directorio de trabajo de `tester`. En local es un volumen Docker con
nombre, no una carpeta del host. Sobrevive a `make compose-down`.

## Como se organiza

```
/workspace
  engagements/   un directorio por cada engagement o labor
  retos/         un directorio por cada reto o CTF
```

Cada trabajo empieza en su propio directorio dentro de `engagements/` o de
`retos/`, copiando la plantilla que corresponda. La estructura viene en la
imagen, asi que un volumen nuevo ya la tiene.

## Que se anota aqui

- **Engagements**: objetivos, alcance, activos, IPs, credenciales
  encontradas, evidencias y conclusion.
- **Retos**: enunciado, pista inicial, solucion paso a paso, y por que no
  sirvieron los caminos que se probaron primero.
- **Salidas de herramientas**: XML de nmap, capturas, scripts, ficheros
  obtenidos.

## Como se saca algo al host

El volumen no es una carpeta del host, asi que no se ve en Finder. Dos
formas, sin salir de make:

```bash
make workspace-list                          # ver que hay dentro
make workspace-export RUTA=retos/mi-reto/solucion.md
make workspace-export ENG=mi-engagement DEST=./salida/
```

La segunda copia el directorio entero del engagement a `./salida/`.

## Copias de seguridad

Un volumen no se copia con `scp`. El procedimiento esta en
`docs/backups.md`.

## Aviso

Aqui se escriben notas de engagements reales, con datos de clientes. No
subas nada de esto a un repositorio ni hornees el workspace en una
imagen: por eso vive en un volumen y no en la imagen.
