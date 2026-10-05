# Workspace del laboratorio

Directorio de trabajo de `tester`. Es una carpeta del proyecto montada en
`/workspace`, y aqui se documentan los engagements y las soluciones de retos.

## Guia de Inicio Rapido y Asistencia

Si es tu primera vez en el laboratorio o necesitas saber que paso sigue:
- **Asistente en Terminal**: Ejecuta `pt-guide` (alias: `guia` o `guide`) para ver el asistente interactivo con comandos listos.
- **Guia Visual Web**: Abre `guia.html` en tu navegador o ejecuta `pt-guide --web` para iniciar el servidor de ayuda interactivo.
- **Asesor Metodologico**: Ejecuta `pt-next` (alias: `next`) en cualquier momento para que el sistema analice tu avance y te recomiende la siguiente accion tactica.
- **Ayuda General**: Ejecuta `pt-help` para ver la lista completa de utilidades y configuracion de seguridad.

## Como se organiza

```
/workspace
  guia.html      guia interactiva visual y mapa de ruta
  engagements/   un directorio por cada engagement o labor
  retos/         un directorio por cada reto o CTF
  templates/     plantillas de alcance (target.yaml), hallazgos (evidence.md) e informes (report.md)
  skills/        playbooks metodologicos de las 10 Agent Security Skills
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