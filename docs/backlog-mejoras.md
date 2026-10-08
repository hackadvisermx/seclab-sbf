# Backlog de mejoras — benchmark con proyectos similares (2026-10-06)

> Estado: acciones A1–A21 completadas. Este archivo conserva el backlog histórico; el roadmap siguiente está en [backlog de mejoras v3](backlog-mejoras-v3.md).

Este documento nace de un ejercicio de comparación entre `seclab-sbf` y proyectos externos de
reconocimiento/pentesting automatizado, orientado a identificar mejoras — en especial para la
fase de reconocimiento y para que el laboratorio sea más sencillo de operar para un usuario no
experimentado. No implementa nada por sí mismo: es un backlog para ir tomando una acción a la vez,
cada una como su propia fase con su propia rama y PR, según el flujo de `AGENTS.md`.

## Estado de partida

Al momento de escribir esto, la rama por defecto (`bootstrap/baseline`) ya integró hasta la fase
103 (catálogo de modelos de OpenRouter). Las fases 92-101 añadieron soporte de retos CTF Jeopardy,
modo claro/oscuro, terminal multi-pestaña, la metodología Evidence-First con gates de control
negativo y modos de acceso RICH/PARTIAL/UNAUTH, resolución de `pt-cheat`/`skills`, telemetría de
red en la barra, cierre del panel VPN, la guía del operador integrada al dashboard y el chat/copiloto
con OpenRouter. `AGENTS.md` quedó desactualizado frente a este estado real (ver A3).

## Filosofía del proyecto (resumen para dar contexto al backlog)

- **Uso autorizado, responsabilidad del operador**: el laboratorio no decide si un objetivo está
  autorizado; valida *alcance declarado* (`target.yaml`), no *permiso legal* (`docs/uso-autorizado.md`).
- **Aislamiento y exposición cero**: sin puertos públicos, sin `--privileged`, acceso solo por
  Tailscale o loopback, rootfs de solo lectura, `cap_drop: ALL` (`plan.md` sección 2 y 8).
- **Filesystem-first / Evidence-first**: `/workspace` es la fuente de verdad editable; cada
  hallazgo exige PoC reproducible y, desde la fase 95, control negativo explícito.
- **Un único usuario, un único flujo de trabajo**: `tester` como único usuario Unix, sin `sudo`.
- **Reproducibilidad por máquina**: versiones y digests fijados, sin `latest`, sin `curl | bash`.

La capa de guía para principiantes (`pt-guide`, `pt-next`, la guía por misiones del dashboard) es
reciente (fases 99-101) y convive con un flujo de entrada todavía pensado para un operador experto.

## Benchmark externo

| Proyecto | Qué aporta de relevante | Enlace |
|---|---|---|
| reconFTW | Modos por nivel de intrusión, checkpoints por función para resumir tras un fallo, **modo diff** que resalta solo lo nuevo entre corridas, notificaciones Slack/Discord/Telegram, `--dry-run` | https://github.com/six2dez/reconftw |
| BBOT | Presets YAML componibles, flags por nivel de riesgo (`safe`/`passive`/`active`/`aggressive`), `--current-preset` para inspeccionar qué va a ejecutar antes de correr, múltiples formatos de salida | https://github.com/blacklanternsecurity/bbot |
| AutoRecon | Carpeta de resultados autoexplicativa, archivo `_manual_commands.txt` con comandos de seguimiento sugeridos, `_patterns.log` con hallazgos resaltados automáticamente | https://github.com/Tib3rius/AutoRecon |
| reNgine | Subscans (profundizar en un activo sin repetir todo el pipeline), correlación/diff de datos entre escaneos, notas por objetivo, descripciones de vulnerabilidad asistidas por LLM | https://github.com/yogeshojha/rengine |
| Exegol | Wrapper que reduce todo a comandos simples, historial de comandos pre-poblado, carpeta "my-resources" persistente entre contenedores, logging automático de shell | https://docs.exegol.com |
| Ghostwriter / Faraday / SysReptor | Biblioteca de hallazgos reutilizables por tipo de vulnerabilidad, deduplicación automática entre herramientas, reportes en Markdown reutilizable | https://github.com/GhostManager/Ghostwriter · https://github.com/infobyte/faraday · https://docs.sysreptor.com |
| OWASP WSTG Tracker | Checklist visual con estado explícito por ítem (completo/pendiente/bloqueado), en vez de un porcentaje inferido por heurística | https://github.com/adanalvarez/owasp-wstg-tracker |
| PentestGPT / PentAGI / CAI / Strix / HexStrike (agentes IA de pentesting) | Patrón común: aprobación humana antes de acciones de riesgo, validación de alcance explícita antes de sugerir un comando, PoC generado y validado antes de reportar un hallazgo (reduce falsos positivos) | — |

## Hallazgos verificados en el código durante esta revisión

Dos de ellos son errores reales, no solo oportunidades de mejora:

1. **El editor de alcance del dashboard pierde datos al guardar.**
   `dashboard/frontend/src/views/EngagementDetailView.vue`, función `saveScopeConfig` (~L1757-1775):
   construye el payload con `cidrs: []` y `endpoints: []` fijos (se pierden sin aviso) y mete
   cualquier CIDR escrito en el campo "IPs y CIDRs" dentro de `ips`. `scripts/seclab_scope.py`
   (`validate_scope`, ~L83-86) exige que cada entrada de `ips` sea una IP válida vía
   `ipaddress.ip_address()`, así que un CIDR ahí deja `target.yaml` inválido y rompe `pt-scope`
   y el recon en el siguiente intento. Ver **A1**.
2. **`pt-guide --web` expone todo `/workspace`, no solo la guía.**
   `scripts/pt-guide.py` (~L182) abre `socketserver.TCPServer(("0.0.0.0", puerto), CustomHandler)`
   usando como raíz la carpeta del primer candidato de guía encontrado, y ese candidato (~L43) es
   `/workspace/guia.html` — por lo que `SimpleHTTPRequestHandler` sirve el directorio
   **completo** `/workspace`, incluidos `loot/` y `evidence/` de cualquier engagement, en el
   puerto 8888 abierto en todas las interfaces y alcanzable por cualquier par en `tun0`/Tailscale.
   Contradice el principio de exposición cero del propio proyecto. Ver **A2**.

## Acciones a implementar

Cada acción tiene un ID estable para referenciarla en sesiones futuras (p. ej. "implementa A6").
El orden es la prioridad sugerida.

### Tier 0 — Corregir errores reales ya detectados

- **A1 — Arreglar el editor de alcance del dashboard.**
  Archivos: `dashboard/frontend/src/views/EngagementDetailView.vue` (`saveScopeConfig`,
  `loadScope`), posiblemente `dashboard/backend/app/api/endpoints/scope.py` para validar en el
  servidor antes de escribir `target.yaml`.
  Por qué: hoy se pierden `cidrs`/`endpoints` al guardar y un CIDR escrito en el campo de IPs deja
  el `target.yaml` inválido sin aviso inmediato — el error solo aparece después, al correr el
  recon. Clasificar IP vs CIDR antes de enviar y validar contra `seclab_scope.validate_scope` en
  el backend antes de persistir.

- **A2 — Restringir `pt-guide --web` a loopback y a servir solo la guía.**
  Archivo: `scripts/pt-guide.py`.
  Por qué: hoy liga en `0.0.0.0:8888` y sirve todo `/workspace` (incluye `loot/`, `evidence/`).
  Cambiar el bind a `127.0.0.1` y copiar/servir únicamente el HTML de la guía desde una carpeta
  propia sin datos de engagements (p. ej. `/usr/local/share/seclab/guide/`).

- **A3 — Poner `AGENTS.md` y `docs/dashboard.md` al día.**
  Archivos: `AGENTS.md`, `docs/dashboard.md`.
  Por qué: `AGENTS.md` describe la fase 91 como la más reciente cuando el repo ya integró hasta la
  103. `docs/dashboard.md` afirma que la recuperación de proyectos "no está disponible" (existe
  desde la fase 91, la papelera) y que los logs usan streaming en vivo (en realidad es *polling*
  REST cada 3s desde `EngagementDetailView.vue`).

- **A4 — Unificar el nombre del artefacto de recon entre las skills y el pipeline real.**
  Archivos: `skills/recon-profiling/SKILL.md`, `skills/prompts/recon-agent.prompt.md`,
  `scripts/pt-recon-pipeline.py`.
  Por qué: las skills instruyen a un agente a compilar `recon/surface.json`, pero el pipeline real
  genera `recon/summary.json` — nadie lee lo que el prompt pide generar. Decidir un único nombre
  y alinear ambos lados.

### Tier 1 — Simplicidad para el usuario no experimentado

- **A5 — Redirigir al detalle del proyecto tras crearlo.**
  Archivo: `dashboard/frontend/src/views/EngagementsView.vue`.
  Por qué: hoy, tras crear un engagement, la UI vuelve a la lista en vez de llevar directo a la
  pestaña de Alcance — pierde la oportunidad de guiar el siguiente paso.

- **A6 — Enlazar la Papelera en la barra de navegación.**
  Archivo: `dashboard/frontend/src/components/Navbar.vue`.
  Por qué: la vista `TrashView` existe desde la fase 91 pero solo se llega a ella desde un botón
  dentro de la lista de proyectos; no está en el menú principal.

- **A7 — Mostrar los límites operacionales reales por defecto en la UI.**
  Archivo: `dashboard/frontend/src/views/EngagementDetailView.vue` (pestaña Alcance).
  Por qué: cuando `target.yaml` no define `operational_limits`, la UI muestra 20 req/s y 5 hilos
  como si fueran el valor activo, pero el default real aplicado por `WorkspaceSyncService` y
  `seclab_scope.py` es 1 req/s y 1 hilo. Induce a error de expectativa sobre la velocidad del recon.

- **A8 — Ayuda contextual sobre jerga en la UI.**
  Archivo: `dashboard/frontend/src/views/EngagementDetailView.vue` y componentes compartidos.
  Por qué: términos como Scope Guard, Evidence-First, BDT (Bounded Non-Destructive Testing),
  control negativo o patrones `gf` aparecen sin explicación. Un ícono "?" con popover corto por
  término reduce la curva de entrada sin tener que salir a leer la guía completa.

- **A9 — Asistente guiado de "nueva auditoría".**
  Archivos: nueva vista o modal en `dashboard/frontend/src/views/`, reutilizando los endpoints
  existentes de `engagements.py` y `scope.py`.
  Por qué: hoy crear engagement, definir alcance y lanzar el primer recon son 3 pasos manuales
  separados. Un único flujo guiado que los encadene (con la validación de A1 ya aplicada) reduce
  la fricción inicial — el punto de entrada más citado como difícil para un novato.

- **A10 — Sesión única para la terminal embebida.**
  Archivos: `dashboard/frontend/src/views/TerminalView.vue`, `scripts/entrypoint/ttyd-as-tester*.sh`.
  Por qué: hoy el usuario inicia sesión en el dashboard y luego otra vez en ttyd al abrir la
  terminal — dos logins para una sola tarea.

### Tier 2 — Reconocimiento (fase prioritaria señalada por el owner)

- **A11 — Modo diff entre corridas de recon.**
  Archivo: `scripts/pt-recon-pipeline.py` (función `generate_summary` y las de cada etapa),
  reflejo en `dashboard/backend/app/services/recon_service.py` y la UI de resultados.
  Por qué: hoy `subdomains.txt` se acumula sin marcar qué es nuevo. Escribir
  `subdomains_new.txt`/`live_hosts_new.txt` comparando contra el `summary.json` anterior y mostrar
  "N activos nuevos desde el último escaneo" en el dashboard — inspirado en el modo diff de
  reconFTW.

- **A12 — Checkpoint por etapa en vez de cortar toda la cadena.**
  Archivo: `scripts/pt-recon-pipeline.py` (`run_all`, ~L296-313, hoy hace `break` en el primer
  fallo).
  Por qué: si una etapa falla (p. ej. `gau` no responde), se pierde la oportunidad de reintentar
  solo esa etapa; hoy el usuario debe re-ejecutar todo con `--stage` manualmente sabiendo cuál
  falló. Guardar qué etapas ya completaron y permitir reanudar desde ahí — inspirado en el sistema
  de marcadores `.called_fn/` de reconFTW.

- **A13 — Resultados de recon como tabla real en el dashboard.**
  Archivo: `dashboard/frontend/src/views/EngagementDetailView.vue` (pestaña Reconocimiento),
  `dashboard/frontend/package.json` (no tiene ninguna librería de tablas/gráficos hoy).
  Por qué: hoy solo se ven contadores y hay que descargar el `.txt` en crudo desde Artefactos para
  ver subdominios, hosts vivos o URLs. Una tabla ordenable con estado HTTP/título por host vivo
  cierra una brecha de UX confirmada en el código.

- **A14 — Archivo de "próximos comandos sugeridos" al final del recon.**
  Archivo: `scripts/pt-recon-pipeline.py` (nueva salida `recon/next_commands.txt`).
  Por qué: patrón `_manual_commands.txt` de AutoRecon — generar, por cada host vivo encontrado,
  una línea concreta de `pt-nmp`/`pt-fuzz-params` lista para copiar. Le da al novato el siguiente
  paso sin que tenga que decidirlo desde cero.

- **A15 — Notificación opcional al terminar un recon o recibir un callback OOB.**
  Archivos: `scripts/pt-recon-pipeline.py`, `shell/pentest-lab/pentest-lab.plugin.zsh` (`pt-callback`),
  reutilizando el patrón de `scripts/host/notify.sh`.
  Por qué: hoy la única notificación del proyecto es para respaldos del host. Una notificación
  apagada por defecto y activable con una sola línea de configuración evita que el novato tenga
  que estar revisando la terminal activamente.

### Tier 3 — Hallazgos y reportes

- **A16 — Biblioteca mínima de plantillas de hallazgo reutilizables.**
  Archivos: `workspace-seed/templates/evidence.md` (nuevas variantes), `shell/pentest-lab/pentest-lab.plugin.zsh`
  (`pt-finding new --template <nombre>`).
  Por qué: plantillas precargadas para tipos frecuentes (XSS reflejado, IDOR, falta de rate limit)
  con título/CWE/CVSS/remediación ya sugeridos evitan la hoja en blanco a quien no sabe redactar
  un hallazgo desde cero — inspirado en la biblioteca de hallazgos de Ghostwriter/SysReptor.

- **A17 — Deduplicación por causa raíz en el compilador de reportes.**
  Archivo: `scripts/pt-report-compiler.py`.
  Por qué: la convergencia por causa raíz ya está documentada en
  `skills/duplicate-scope-guard/SKILL.md` pero no hay código que la aplique. Marcar automáticamente
  hallazgos que comparten CWE + activo como posible duplicado, al estilo de la deduplicación de
  Faraday.

### Tier 4 — Seguimiento metodológico

- **A18 — Reducir la dependencia de heurística por palabra clave en `pt-audit-checklist`.**
  Archivo: `scripts/pt-audit-checklist.py`.
  Por qué: hoy la cobertura por disciplina se infiere por coincidencia de palabras clave en
  `terminal.log` y en el cuerpo de las fichas de hallazgo, lo que genera falsos positivos y
  negativos. Añadir un marcador explícito y reconocible (p. ej. una etiqueta
  `## Disciplina: auth` en `notes.md`) como señal confiable adicional, sin eliminar la heurística
  actual como respaldo.

- **A19 — Barra de progreso visual por disciplina en la pestaña Metodología.**
  Archivo: `dashboard/frontend/src/views/EngagementDetailView.vue` (pestaña Metodología).
  Por qué: hoy solo hay un porcentaje y una lista plana de 8 áreas. Un indicador visual por
  disciplina (completo/parcial/pendiente) se lee más rápido — inspirado en OWASP WSTG Tracker.

### Tier 5 — Copiloto / IA

- **A20 — Validar contra `pt-scope-validator` cualquier host/URL que sugiera el copiloto.**
  Archivos: `dashboard/backend/app/api/endpoints/copilot.py`, `scripts/pt-scope-validator.py`.
  Por qué: hoy el respeto al alcance depende solo de una instrucción en el system prompt
  ("respeta estrictamente in_scope/out_of_scope"). Verificar programáticamente cada host/URL que
  aparezca en la respuesta del modelo contra el Scope Guard antes de mostrarla reduce el riesgo de
  que un novato siga una sugerencia fuera de alcance sin darse cuenta — patrón de validación de
  alcance explícita visto en HexStrike/PentestGPT.

- **A21 — Aviso explícito de que el copiloto nunca ejecuta comandos por sí mismo.**
  Archivo: `dashboard/frontend/src/views/EngagementDetailView.vue` (pestaña Copiloto).
  Por qué: hoy la respuesta se muestra como texto plano sin aclarar que es solo una sugerencia.
  Un aviso corto y permanente evita que un usuario sin experiencia asuma que el sistema ya corrió
  algo por él.

## Cómo usar este backlog

Cada acción se implementa por separado, siguiendo el flujo normal del repositorio: rama
`phase/<numero>-<slug>` desde `bootstrap/baseline`, cambios acotados a esa acción, pruebas
relevantes (`make dashboard-tests`, `make python-units-check` según el área tocada), commit en
español con el formato `tipo(área): resumen`, y PR hacia `bootstrap/baseline` pendiente de
aprobación del owner antes de mergear.
