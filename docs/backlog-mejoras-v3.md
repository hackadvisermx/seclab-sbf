# Backlog de mejoras v3 — auditoría trazable y segura

Fecha: 2026-10-07. Base local revisada: `b353a46` (merge de la fase 145, PR #165). Fuente de producto: investigación de producto y roadmap aportada por el owner.

## Propósito

Esta versión ordena el siguiente ciclo de SecLab-SBF alrededor de una cadena verificable:

**autorización → alcance → decisión → acción → artefacto → evidencia → hallazgo → reporte → cierre**

El objetivo es que el producto pueda explicar qué estaba permitido, qué ocurrió, qué resultado se conservó y por qué una afirmación llegó al reporte. La prioridad no es añadir herramientas. Cada nueva iniciativa debe mejorar seguridad, trazabilidad o claridad del recorrido.

Este backlog no declara como bugs las brechas que el deep research no pudo comprobar en GitHub. La primera iniciativa contrasta esas hipótesis con el checkout y tareas reales antes de proponer cambios. Este documento reorganiza el trabajo pendiente de experiencia descrito en las fases 2–7 de [plan-experiencia-principiante.md](plan-experiencia-principiante.md); ese plan y el [backlog v2](backlog-mejoras.md) permanecen como contexto histórico.

## Estado de partida comprobado

- Las acciones A1–A21 del backlog anterior están implementadas y mergeadas, según `AGENTS.md`.
- El checkout de este documento está en `b353a46`, que integra el PR #165 y su progreso de reconocimiento en vivo. La fase 146 reconcilia la anotación anterior de PR abierto en `AGENTS.md` y en la nota de fase 145 con el merge confirmado en GitHub.
- La fase 145 muestra etapa, comando, salida reciente y cancelación del job actual. `recon/progress.json` es una vista acotada y correlacionada por ejecución; no es todavía un historial durable de decisiones de todo el engagement. Detalle: [phase-145.md](phase-145.md).
- La fase 143 evita sembrar objetivos inventados y exige revisar/confirmar el alcance desde el wizard. Esa confirmación no constituye una frontera global para todos los caminos de terminal y herramientas. Detalle: [plan-experiencia-principiante.md](plan-experiencia-principiante.md).
- `scripts/seclab_scope.py` centraliza el matcher compartido: aplica primero exclusiones, diferencia dominio exacto de `*.dominio` (el wildcard no incluye el apex), normaliza nombres IDNA e IP y compara endpoints por ruta. La cobertura de DNS, CNAME, redirects, CDN/IP compartida y revalidación justo antes de cada acción debe comprobarse por flujo; no se presume aquí que esté ausente.
- El flujo actual ya distingue hallazgos `PROVEN`, `CANDIDATE` y `DISPROVED`; el compilador de reportes trata `PROVEN` como hallazgo confirmado. La mejora propuesta es completar la procedencia entre ejecución, artefacto, evidencia y afirmación del reporte, no volver a crear esos estados.
- El Copiloto valida texto sugerido contra el alcance y advierte sobre objetivos excluidos o no confirmados. Es una advertencia informativa; si el validador no está disponible, el camino actual puede omitirla. La propuesta v3 hace visible ese estado y conecta la respuesta con sus fuentes.

La aplicación registra alcance declarado; no determina si una autorización es legalmente válida. La persona operadora sigue siendo responsable de confirmar permiso y límites.

## Priorización

V3-00 iniciada en fase 146: [revisión técnica y línea base](v3-flujo-verificado.md), fallback inseguro de `pt-recon` corregido y validación con personas pendiente. El diagnóstico confirmó que `pt-report build` evita el gate de `check`; V3-03a se implementa en fase 147 con validación obligatoria en compilación y exportación, incluido el dashboard. V3-03b en fase 148 incorpora los outputs/logs al export y hashes de original/copia, y corrige las afirmaciones automáticas del reporte. V3-01a en fase 149 versiona scope/límites y los revalida antes de nuevas acciones; reanudación exige la misma revisión. V3-01b en fase 150 añade referencia/vigencia y permisos pasivo/activo independientes, comprobados antes de tráfico; UI y wizard conservan simulación sin habilitar permisos. V3-03c en fase 151 evita confirmación implícita: nuevas fichas y registros sin estado son CANDIDATE; estados explícitos se conservan. V3-02a en fase 152 (#172 mergeado con aprobación individual en `d186963`): historial persistente de jobs del dashboard y UI paginada, sin snapshots de outputs anteriores. V3-02b en fase 153, #173 fusionado con aprobación individual en `aaacc97`, distingue bloqueo de Scope Guard durante etapas y ofrece revisión de autorización; fase 158 (V3-02d) conserva también el motivo/clase de rechazos iniciales sin summary mediante un descriptor privado por run/etapa; cambios de plan al entrar y scope inválido quedan bloqueados, sin analizar stdout. Fase 154 instala Playwright y tester temporal; fase 155 (#175 fusionado con aprobación individual en `badcb49`) añade una prueba de auditoría sintética de wizard a export con backend real sin red y corrige discrepancias de formulario/compilador y vista ejecutiva. Esto amplía la verificación técnica de V3-00; validación con personas y cadena estructurada de procedencia continúan pendientes. V3-01c en fase 156 añade vista previa local por etapa/targets/permisos/límites y revisión vinculada al lanzamiento del dashboard; los targets futuros del pipeline completo quedan pendientes y fase 157 (V3-01d/V3-02c parcial) conserva un snapshot acotado de la revisión validada al iniciar en el historial SQLite, con hashes, permisos, ventana, límites y muestras de hosts/veredictos. No guarda rutas/consultas/credenciales ni resultados antiguos; jobs sin expected_plan no inventan revisión. Eventos/estados del engagement, requisitos de confirmación/procedencia finding/job y las demás iniciativas siguen pendientes.

| Prioridad | Iniciativa | Resultado esperado | Dependencias |
|---|---|---|---|
| **P0** | V3-00. Verificar el flujo y establecer línea base | Mapa comprobado de caminos activos, controles existentes y fricciones por persona | Ninguna; precede a cambios estructurales |
| **P0** | V3-01. Contrato ejecutable de autorización y alcance | Cada acción gestionada por el producto muestra y vuelve a comprobar por qué está permitida | V3-00 |
| **P0** | V3-02. Estado del engagement y siguiente decisión | Una timeline persistente permite retomar y entender qué decisión falta | V3-00; integra V3-01 y fase 145 |
| **P0** | V3-03. Cadena de procedencia y compuertas de reporte | El reporte se puede rastrear hasta hallazgo, evidencia, artefacto y ejecución | V3-00; IDs de etapa/job/artifact acordados en V3-02 |
| **P1** | V3-04. Playbooks deterministas y experiencia progresiva | Cada procedimiento tiene requisitos, límites, resultado y condición de parada legibles | V3-01–03 |
| **P1** | V3-05. Copiloto con fuentes y fallback visible | La IA explica y redacta con fuentes identificables; el flujo sigue funcionando sin IA | V3-03–04 |
| **P2** | V3-06. Vista ligera de supervisión y checkpoints | Un instructor puede detectar etapa, bloqueo y evidencia pendiente | V3-02–04; validar necesidad con usuarios |
| **P2** | V3-07. Métricas e integraciones justificadas por uso | Decisiones de roadmap basadas en resultados observados, no en cantidad de herramientas | Instrumentación mínima de V3-00–06 |

Las prioridades indican orden de producto, no estimaciones de calendario. Cada iniciativa se divide en PRs pequeños cuando el trabajo exceda una fase revisable.

## Iniciativas

### V3-00 — Verificar el flujo y establecer línea base (P0)

**Problema.** La investigación aporta hipótesis valiosas, pero no pudo inspeccionar el repositorio remoto. Sin inventariar los controles reales, se corre el riesgo de rediseñar funciones que ya existen o de dejar sin detectar un camino de ejecución que los evita.

**Trabajo.** Recorrer una actividad de práctica aislada desde el alta hasta el cierre. Inventariar los caminos de interacción activa gestionados por dashboard, pipeline, terminal, callbacks e integraciones; ubicar dónde se invoca el matcher y cuándo se toma la decisión. Revisar cómo se identifican jobs y artefactos, qué queda en el workspace y qué entra al paquete final. Probar tareas con una persona principiante, una experimentada y, si existe ese perfil de uso, una supervisora.

**Aceptación.**

- Un mapa enlaza cada camino de acción con su punto de validación, sus límites y sus artefactos resultantes.
- Cada hipótesis del research queda marcada como **confirmada**, **refutada** o **pendiente**, con archivo, prueba o tarea que la sustenta.
- El inventario distingue controles aplicados por SecLab-SBF de los que dependen del operador en una terminal libre; no se describe un comando como bloqueado por scope si existe una ruta que evita el matcher.
- Se documentan al menos las tareas «definir alcance y simular», «reanudar una etapa», «convertir una señal en hallazgo» y «justificar una afirmación del reporte»; se registran dudas, errores y pasos donde la persona no sabe qué hacer.
- Hay una línea base de motivos de bloqueo, abandono/reintento, hallazgos sin evidencia suficiente y afirmaciones del reporte sin vínculo navegable. Si no hay telemetría existente, se mide en sesiones de prueba sin recopilar datos de objetivos reales.
- Las brechas de seguridad verificadas se elevan a P0 y se corrigen como cambios concretos; las hipótesis sin evidencia no se redactan como bugs.

**No incluye.** Cambios masivos de UI, nuevas herramientas o un sistema de telemetría que envíe datos fuera de la instancia.

### V3-01 — Contrato ejecutable de autorización y alcance (P0)

**Problema.** `target.yaml` y el matcher ya expresan reglas; falta comprobar que todo flujo de acción del producto aplica el mismo contrato al objetivo concreto justo antes de actuar, y que el operador puede entender el resultado.

**Trabajo.** Basado en V3-00, registrar para el engagement la referencia de autorización declarada por el operador, vigencia/ventana, tipos de actividad permitidos, inclusiones, exclusiones y límites. Conservar una versión del contrato asociada a cada job. Centralizar el chequeo en el límite de ejecución de las acciones gestionadas por SecLab-SBF. Mostrar preview con tipo de interacción, targets resultantes, motivo de inclusión/bloqueo y tráfico previsto.

**Casos del matcher que deben quedar definidos y cubiertos.** Dominio exacto frente a wildcard y apex; exclusión que prevalece; IDNA, IPv4 e IPv6; puertos y endpoints cuando correspondan; redirect externo; CNAME a proveedor; IP compartida/CDN; resolución DNS que cambia entre revisión y ejecución; activo descubierto que no está autorizado expresamente.

**Aceptación.**

- Un job guarda la versión del scope, etapa, clase de interacción (`simulación`, `pasiva` o `activa`), targets evaluados y decisión explicable del matcher.
- Toda acción activa gestionada por la aplicación vuelve a validar scope y permisos inmediatamente antes del despacho; las rutas inventariadas en V3-00 no tienen un bypass silencioso.
- Un target `UNKNOWN` o `OUT_OF_SCOPE`, un scope inválido/vacío o un permiso requerido ausente bloquea el tráfico activo al objetivo con motivo y recuperación concreta; simular o editar el scope sigue disponible localmente.
- La terminal libre y cualquier herramienta que pueda eludir el límite de ejecución tienen un tratamiento explícito: se añade un control técnico viable o se declara con claridad que Scope Guard no intercepta esa acción. La UI nunca promete una garantía global que el producto no aplica.
- Un resultado descubierto no amplía el alcance. Redirects, CNAME y resolución a IP compartida siguen una política explícita y nunca reciben autorización por inferencia.
- `--dry-run` y la simulación visual demuestran que no abren conexión al objetivo. Una prueba de red verifica ausencia de tráfico al destino.
- La interfaz de principiante dice qué targets recibirán tráfico y por qué; el modo avanzado permite inspeccionar reglas canónicas y la decisión técnica.
- La UI aclara que el registro de autorización es una declaración del operador, no una evaluación legal del permiso.

**Pruebas.** Tabla de casos y pruebas de propiedades del matcher; fixtures de DNS/redirect/CNAME; verificación de IPv4/IPv6 e IDNA; integración por cada punto de ejecución; prueba de simulación sin tráfico y de bloqueo activo sin permiso.

**No incluye.** Inferir autorización por propiedad del dominio, registrar automáticamente nuevos targets ni convertir el matcher de aplicación en la única frontera de red del host.

### V3-02 — Estado del engagement y siguiente decisión válida (P0)

**Problema.** El avance en vivo de la fase 145 explica el job que corre, pero el usuario necesita retomar el hilo completo de decisiones entre sesiones y distinguir «terminado», «pendiente», «bloqueado», «fallido» y «cancelado».

**Trabajo.** Definir estados y transiciones del engagement: borrador, revisión de alcance, simulación, revisión de activos, actividad permitida, triaje, reporte y cierre, ajustados al flujo real hallado en V3-00. Registrar eventos de decisión ligados a `engagement_id`, `stage_id`, `job_id` y versión del scope. La vista de inicio del engagement responde qué ocurrió, cuál es la siguiente decisión válida, qué debe revisar el operador y cuándo debe detenerse.

**Aceptación.**

- El estado y los eventos sobreviven recarga y reingreso al proyecto; una transición inválida no marca una etapa como completada.
- El historial diferencia finalización correcta, bloqueo, fallo y cancelación, y conserva el motivo y la decisión que permite continuar.
- El panel de reconocimiento de la fase 145 se relaciona con el job y los artefactos de la timeline; una salida provisional sigue claramente separada de resultados aceptados.
- La timeline muestra autorización/versión de scope, clase de interacción, targets, jobs, artefactos y revisión humana sin duplicar el log completo de stdout.
- Los eventos no guardan secretos en claro; los comandos y datos sensibles se redactan según una regla documentada.
- Una prueba de pausa/reanudación conserva el estado y lleva a la misma decisión pendiente.

**No incluye.** Colaboración multiusuario, control de acceso de aula completo ni una auditoría legal inmutable.

### V3-03 — Procedencia de evidencia, hallazgos y reporte (P0)

**Entrega parcial V3-03e (fase 161).** Las fichas guardan referencias explícitas ruta/SHA-256 a versiones revisadas de artefactos; UI conserva los vínculos al editar/recargar y muestra si el original cambió. Reporte y paquete revalidan las referencias declaradas y bloquean archivos ausentes, cambiados o referencias inválidas. El export incorpora archivos seleccionados con hashes original/copia, sanitiza texto y rechaza binarios/no UTF-8 en modo sanitizado. Detalle en [phase-161.md](phase-161.md). Los vínculos siguen siendo opcionales para fichas legacy y no confirman hallazgos; exigir evidencia y rationale para PROVEN, IDs persistentes, snapshots inmutables y procedencia job/herramienta siguen pendientes.

**Entrega parcial V3-03d (fase 160).** El visor/API identifican la versión leída de un archivo mediante SHA-256 de bytes originales, tamaño y mtime UTC, distinguen límites/binario/decodificación con sustituciones y rechazan cambios detectados durante la lectura. La UI evita mezclar respuestas tardías de otro archivo/carpeta/proyecto. Huella hasta 32 MiB y preview textual hasta 2 MiB; no modifica originales ni crea snapshots persistentes. Detalle en [phase-160.md](phase-160.md). IDs estables de artefacto, vínculos a jobs/findings y revisión humana estructurada siguen pendientes; no se declara V3-03 completa.

**Problema.** Ya existen artefactos, fichas de evidencia, estados de hallazgo, deduplicación y compuertas de paquete. La oportunidad es conectar esas piezas para que una afirmación del reporte pueda justificarse con la fuente original y la decisión humana correspondiente.

**Trabajo.** Acordar IDs estables para artefactos/observaciones y referencias desde findings. Preservar el resultado bruto como fuente identificable; asociar herramienta/versión si aplica, target, job/playbook step, timestamp, estado del parser y hash de contenido. Una observación derivada apunta al artefacto original. El finding referencia una o más evidencias, activo, estado, rationale y revisión humana. El reporte conserva enlaces o identificadores de origen. Extender el packer y compilador existentes en vez de crear un export paralelo.

**Aceptación.**

- Desde cada afirmación técnica publicada se llega a un finding; desde este, a evidencia seleccionada; desde la evidencia, al artefacto original y job que la generaron.
- Los cambios de parser, deduplicación, renombrado o reimport no eliminan ni reemplazan silenciosamente el origen. La deduplicación conserva todos los orígenes y permite revisión humana.
- Un finding marcado `PROVEN` requiere activo, evidencia vinculada y rationale de verificación; la UI mantiene visibles `CANDIDATE` y `DISPROVED` sin presentarlos como riesgo confirmado.
- El compilador bloquea o señala afirmaciones sin soporte, findings confirmados sin evidencia y activos fuera de alcance según la política definida en V3-01.
- El reporte y export identifican alcance revisado, metodología aplicada, limitaciones y cobertura pendiente. La cobertura no se interpreta como garantía de ausencia de vulnerabilidades.
- El paquete permite verificar integridad de los artefactos exportados y no expone secretos fuera de la selección explícita.

**Pruebas.** Fixtures de salida bruto y parsers; reimport/deduplicación; reportes con candidato, descartado y confirmado; evidencia ausente o movida; snapshots de export y redacción.

**No incluye.** Ontología universal de vulnerabilidades, ticketing de remediación ni borrado automático de resultados duplicados.

### V3-04 — Playbooks deterministas y experiencia progresiva (P1)

**Problema.** Una recomendación clara no basta si los requisitos, límites, salida esperada y condición de parada viven sólo en prosa o en el conocimiento del operador.

**Trabajo.** Definir un schema validable por paso de playbook: objetivo, tipo de interacción, precondiciones, permisos, selector de targets, entradas, parámetros, timeout/límites, ejecución, salida esperada, parser, artefactos, evidencia mínima, criterio de éxito y condición de parada. Mantener un mismo estado de auditoría con dos niveles de detalle: guiado para entender la decisión y avanzado para inspeccionar comando, argumentos y raw output.

**Aceptación.**

- Un playbook inválido o sin permiso requerido no puede ejecutarse; las acciones activas usan V3-01.
- Antes de ejecutar se ven propósito, targets, clase de interacción, límites, resultado esperado y opción de detenerse.
- Después de ejecutar se enlazan salida real, artefactos y siguiente decisión; un resultado negativo puede completar una prueba si satisface su criterio.
- El modo avanzado expone comando/parámetros reales; el modo guiado explica términos y no oculta la posibilidad de inspección.
- El recorrido básico funciona con proveedores IA desactivados.

**No incluye.** Motor adaptativo de enseñanza, gamificación, reemplazo de herramientas ni ejecución operada por IA.

### V3-05 — Copiloto con fuentes, límites y fallback (P1)

**Entrega parcial V3-05a (fase 159).** El Copiloto muestra `Validación de alcance no disponible` ante scope/validador ausentes, timeout, fallo de inicio, scope inválido o respuesta/código inconsistentes. Conserva texto original y metadata; una comprobación limpia mantiene la respuesta anterior y las exclusiones/UNKNOWN mantienen sus advertencias. Comprobado con validador instalado, API/proveedor simulado, Vue y Chromium; no ejecuta reconocimiento. Detalle y límites en `phase-159.md`. Fuentes navegables, revisión/redacción del contexto remoto y fallback determinista continúan pendientes; no se declara V3-05 completa.

**Problema.** El copiloto ya es consultivo y recibe contexto del engagement, pero la advertencia de alcance no equivale a una cita de procedencia y puede no ejecutarse si el validador falla.

**Trabajo.** Mantener la ejecución estructuralmente separada de las capacidades del Copiloto. Vincular cada explicación/borrador que use evidencia a IDs navegables; distinguir sugerencia, borrador y contenido revisado; hacer visible modelo/proveedor, hora, fuentes y contexto que saldrá de la instancia. Mostrar degradación si falla IA o validación de alcance. Ofrecer reglas/playbooks deterministas cuando el proveedor no esté disponible.

**Aceptación.**

- El Copiloto no dispone de endpoint, herramienta o credencial capaz de ejecutar acciones contra el objetivo; cambiar proveedor/modelo no cambia permisos.
- Las afirmaciones basadas en artefactos incluyen fuentes navegables y lenguaje de incertidumbre; el usuario puede comparar borrador y fuente.
- Antes de enviar contexto a un proveedor remoto, el usuario puede revisar qué datos se incluyen y aplicar redacción; queda claro si el proveedor es local/remoto.
- Si falla el validador de alcance, no se presenta el texto como si hubiera pasado la comprobación: se muestra `validación no disponible` y el contenido sigue marcado como sugerencia que debe revisarse.
- Timeout, respuesta inválida o proveedor desconectado no bloquea alcance, reconocimiento, triage ni generación determinista de reportes.
- Contenido hostil dentro de artefactos/output se trata como dato no confiable y no altera permisos, scope ni instrucciones del sistema.

**No incluye.** Agente autónomo, ejecución de comandos, expansión de alcance o confirmación automática de findings.

### V3-06 — Vista ligera de supervisión y checkpoints (P2)

**Problema.** Un instructor o supervisor necesita saber si la persona entiende la etapa, dónde está bloqueada y si su evidencia sostiene el hallazgo, sin administrar un LMS completo.

**Trabajo.** En una vista de engagement autorizado, resumir etapa actual, decisión pendiente, artefactos esperados/recibidos, cobertura registrada, bloqueos y revisión del reporte. Los checkpoints piden una decisión explicada por la persona antes de revelar una ayuda más detallada; preservar la salida raw disponible.

**Aceptación.**

- La vista responde en una pantalla: qué etapa está activa, qué falta, por qué está bloqueada y qué evidencia puede revisar la persona autorizada.
- El supervisor puede ver decisiones y relaciones de evidencia necesarias para revisar, sin exposición accidental de claves o contexto de otros engagements.
- Un checkpoint diferencia respuesta propia, hint usado y resultado real; no se usa como puntuación de competencia sin una política explícita.
- Pruebas con instructores confirman una reducción observable en el tiempo para localizar bloqueos y revisar procedencia antes de expandir la función.

**No incluye.** Asignaciones por grupo, calificaciones, leaderboard, cursos o cohortes hasta confirmar esa necesidad.

### V3-07 — Métricas e integraciones justificadas por uso (P2)

**Problema.** El producto necesita evidencia para decidir qué fricción resolver y si una integración adicional mejora el flujo.

**Trabajo.** Definir métricas locales y agregadas con datos mínimos: finalización de la primera auditoría guiada; tiempo hasta identificar la siguiente decisión; reintentos y bloqueos por etapa; acciones fuera de alcance efectivamente ejecutadas (meta de pruebas: cero); findings confirmados con procedencia completa; errores de validación de reporte; uso/corrección/rechazo de borradores IA; tiempo de supervisión. Revisar integraciones propuestas frente a tareas observadas y al modelo de datos estable.

**Aceptación.**

- Cada métrica tiene una definición, denominador, retención y decisión de producto que informa.
- En despliegues autocontenidos, la medición funciona localmente y no transmite datos sin una elección informada del operador.
- No se usa tiempo dentro de la app como métrica primaria ni se recopilan targets, outputs, hallazgos o secretos para analítica general.
- Una nueva integración entra al roadmap solo si cubre una tarea observada y conserva artefacto bruto, target, job y procedencia.

**No incluye.** Telemetría externa obligatoria, ranking de usuarios o amplitud de integraciones como objetivo independiente.

## Métricas de éxito del roadmap

| Resultado | Señal |
|---|---|
| Scope difícil de usar mal | En pruebas automatizadas: 0 acciones fuera de alcance ejecutadas; registrar también falsos bloqueos para no ocultar fricción |
| Primera auditoría más clara | Porcentaje de principiantes que completan el recorrido guiado sin ayuda fuera de los hints previstos |
| Reanudación fiable | Porcentaje de sesiones de prueba que retoman la decisión y etapa correctas después de salir y volver |
| Evidencia defendible | Porcentaje de findings `PROVEN` con activo, fuente, job y rationale completos |
| Reporte trazable | Porcentaje de afirmaciones técnicas que llegan a evidencia y artefacto origen |
| IA útil y acotada | Borradores aceptados/corregidos/rechazados; tasa de afirmaciones sin fuente en muestra revisada; recuperación ante fallo de proveedor |
| Supervisión útil | Tiempo para localizar etapa bloqueada y revisar la evidencia correspondiente |

Las métricas se comparan contra la línea base de V3-00. Los objetivos cuantitativos se fijan después de observar esa línea base, excepto el objetivo de seguridad de cero acciones fuera de alcance.

## Principios de diseño y fuentes

- La autorización y las reglas de engagement se definen antes de la actividad y limitan las acciones autorizadas: [NIST SP 800-115](https://csrc.nist.gov/pubs/sp/800/115/final), [NIST Rules of Engagement](https://csrc.nist.gov/glossary/term/rules_of_engagement) y [OSCAL Assessment Plan](https://pages.nist.gov/OSCAL/learn/concepts/layer/assessment/assessment-plan/).
- La interfaz distingue reconocimiento pasivo de enumeración activa y mantiene el trabajo dentro del scope: [OWASP WSTG — Information Gathering](https://wstg.owasp.org/latest/4-Web_Application_Security_Testing/01-Information_Gathering/00-Information_Gathering_Overview/).
- Las respuestas de IA conservan referencias a las fuentes, incertidumbre y límites de capacidad; la app conserva un camino determinista: [NIST AI RMF](https://www.nist.gov/itl/ai-risk-management-framework) y [OWASP GenAI](https://genai.owasp.org/).
- Los patrones de producto que motivan la trazabilidad incluyen relación entre evidencia, metodología, hallazgos y reportes: [Dradis CE](https://dradis.com/ce/) y [DefectDojo deduplication](https://docs.defectdojo.com/triage_findings/finding_deduplication/). La divulgación progresiva toma como referencia los recorridos estructurados de [HTB Academy](https://help.hackthebox.com/en/articles/12741910-academy-modules-paths) y [TryHackMe assignments](https://help.tryhackme.com/en/articles/6498335-using-and-creating-assignments).

Estas fuentes orientan el diseño; no prueban por sí mismas una carencia del código actual ni obligan a replicar los productos citados.

## Regla de ejecución

Cada entrega futura debe partir de archivos reales, enlazar criterios de aceptación con pruebas, documentar comandos y resultados en `docs/phase-<n>.md`, y conservar el flujo de revisión del repositorio. La autorización temporal explícita del owner permite merges sin preguntar del 2026-10-08 19:09:04 UTC al 2026-10-09 19:09:04 UTC, manteniendo PR, gates y CI aprobados del head exacto. Después vuelve la aprobación individual del owner. Para cambios de UI, validar en navegador con workspace/backend desechables; no usar el dominio ni reiniciar el contenedor del owner sin instrucción.
