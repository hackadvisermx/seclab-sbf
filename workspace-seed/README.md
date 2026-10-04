# Workspace del laboratorio

Directorio de trabajo de `tester`. Es una carpeta del proyecto montada en
`/workspace`, y aqui se documentan los engagements y las soluciones de retos.

## Como se organiza

```
/workspace
  engagements/   un directorio por cada engagement o labor
  retos/         un directorio por cada reto o CTF
  templates/     plantillas de alcance (scope.txt) e informes (report.md)
```

Cada trabajo empieza en su propio directorio dentro de `engagements/` o de
`retos/`, copiando la plantilla que corresponda (`templates/scope.txt`,
`templates/report.md` o las plantillas en cada subdirectorio). Las plantillas
estan aqui y se copiaron desde `workspace-seed/` cuando `make` creo la carpeta.

## Que se anota aqui

- **Engagements**: objetivos, alcance, activos, IPs, credenciales
  encontradas, evidencias y conclusion.
- **Retos**: enunciado, pista inicial, solucion paso a paso, y por que no
  sirvieron los caminos que se probaron primero.
- **Salidas de herramientas**: XML de nmap, capturas, scripts, ficheros
  obtenidos.

## Notas

Estas notas son tuyas mientras trabajas dentro del contenedor. No hace falta
copiar nada a mano para conservarlas: la carpeta del proyecto es la misma que
ves en el host.

Para llevarte una parte a otra sitio:

```bash
make workspace-list                          # ver que hay
make workspace-export RUTA=retos/mi-reto     # copiar al host
make workspace-export ENG=mi-engagement      # un engagement entero
```

## Aviso

Aqui se escriben notas de engagements reales, con datos de clientes. La carpeta
esta en `.gitignore` a proposito: no la subas a ningun repositorio ni la
hornees en una imagen.