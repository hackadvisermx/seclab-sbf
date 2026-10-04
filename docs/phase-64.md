# Fase 64: Registro y Auditoría Continua de Engagements (`pt-log`)

## 1. Contexto y Objetivos

Durante auditorías de seguridad, pruebas de penetración autorizadas o resolución de laboratorios (HackTheBox, TryHackMe), contar con una bitácora íntegra, cronológica y reproducible de cada comando ejecutado y su salida es un requisito indispensable para:
- Respaldar los hallazgos y evidencias en los reportes técnicos finales.
- Proveer trazabilidad de acciones ante cualquier incidente o requerimiento del cliente.
- Documentar writeups y notas estructuradas sin la carga de copiar y pegar manualmente desde la terminal.

Inspirado en el patrón de logging continuo de entornos como Exegol:

1. **Helper Zsh `pt-log`**:
   - Activa el volcado continuo y transparente de la sesión de terminal activa directamente hacia `/workspace/engagements/<nombre_engagement>/terminal.log` (o `/workspace/retos/<nombre_reto>/terminal.log`).
   - Opera de forma no intrusiva aprovechando las capacidades nativas de `tmux pipe-pane` para desviar una copia exacta del flujo del terminal en tiempo real.

2. **Subcomandos Ergonómicos**:
   - `pt-log start <engagement>` (o simplemente `pt-log <engagement>`):
     - Inicia la captura continua hacia `/workspace/engagements/<engagement>/terminal.log`.
     - Admite el prefijo `reto:<nombre>` (ej. `pt-log reto:ad-pivot`) para organizar retos y CTFs en `/workspace/retos/`.
     - Inyecta una cabecera estructurada con fecha, usuario, host, sesión de tmux, ID de pane y ruta del workspace.
     - Valida estrictamente el identificador contra la expresión regular `^[a-zA-Z0-9._-]+$` para bloquear cualquier intento de path traversal.
   - `pt-log stop`:
     - Detiene la tubería de `pipe-pane` en el pane actual.
     - Registra el pie de cierre con timestamp final y emite un resumen en consola con el número de líneas capturadas y el tamaño del archivo.
   - `pt-log status`:
     - Consulta si el pane actual está grabando activamente, el nombre del engagement asignado, el tiempo transcurrido, la ruta del archivo y las métricas actuales.
   - `pt-log mark "<nota>"`:
     - Inserta una marca o hito de auditoría con timestamp ISO 8601 directamente en el log (e.g. `pt-log mark "Acceso inicial obtenido mediante CVE-2023-XXXX"` o `pt-log mark "Escalada de privilegios a SYSTEM completada"`).
   - `pt-log list`:
     - Lista todos los registros de auditoría existentes en `/workspace/engagements/` y `/workspace/retos/` con métricas de líneas, tamaño y última modificación.
   - `pt-log view [engagement]`:
     - Abre el archivo `terminal.log` con `less -R` conservando las secuencias de escape y colores ANSI originales.
   - `pt-log tail [n]`:
     - Permite inspeccionar en vivo las últimas líneas del registro actual con `tail -f`.

3. **Aliases Ergonómicos**:
   - `alias ptlog="pt-log"`
   - `alias logeng="pt-log"`
   - Integrado en `pt-help` y banner del laboratorio.

---

## 2. Decisiones de Arquitectura y Seguridad

- **Aislamiento por Pane de tmux**:
  - Cada terminal o panel dentro de la sesión `pentest-lab` almacena su propio estado de logging mediante opciones de usuario en tmux (`@seclab_log_file`, `@seclab_log_eng`, `@seclab_log_start`).
  - Permite que múltiples ventanas o paneles registren simultáneamente tareas paralelas (e.g. escaneo de puertos en un panel y explotación en otro) hacia el mismo log o logs separados sin interferencias.
- **Trazabilidad Forense**:
  - El formato de inicio, marcas intermedias y detención incluye timestamps inmutables (`date '+%Y-%m-%dT%H:%M:%S%z'`).
  - La captura vía `pipe-pane` preserva tanto la entrada enviada como las respuestas de las herramientas (nmap, nxc, metasploit, curl, etc.).
- **Persistencia en el Workspace**:
  - Los logs se guardan dentro del bind mount `/workspace` (`./workspace`), garantizando que sobreviven a reinicios del contenedor y quedan accesibles de inmediato desde el host para generar informes.

---

## 3. Verificaciones y Calidad

- **Pruebas Unitarias Python**:
  - `test_engagement_logging_helpers` en `scripts/verify/check-python-units.py`, validando la existencia de todos los subcomandos modulares (`_pt-log-workspace-dir`, `_pt-log-start`, `_pt-log-stop`, `_pt-log-status`, `_pt-log-mark`, `_pt-log-list`, etc.), las invariantes de validación alfanumérica y las marcas de auditoría.
  - Actualización de `test_pentest_lab_plugin_helpers_and_aliases` comprobando `pt-log()`, los aliases `ptlog`/`logeng` y su presencia en `pt-help` (55/55 pruebas unitarias en verde).
- **Pruebas Funcionales**:
  - Simulación de ciclo de vida completo en sesión tmux: activación con `pt-log start`, ejecución de comandos interactivos, registro de hitos con `pt-log mark`, consulta con `pt-log status`, detención con `pt-log stop` y verificación de integridad del fichero `terminal.log`.
- **Herramientas de Calidad**:
  - `zsh -n shell/pentest-lab/pentest-lab.plugin.zsh` limpio.
  - `make verify` pasando al 100% (55 pruebas unitarias, Gitleaks, Hadolint, Makefile, Compose refs, Compose security).
  - `make compose-config ENV_FILE=.env.example` limpio en todas las configuraciones.
