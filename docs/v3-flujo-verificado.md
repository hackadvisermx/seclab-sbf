# V3-00: revisión técnica del flujo de auditoría

Fecha: 2026-10-07. Fuente de código: `b353a46`; corrección de shell y fixtures en fase 146. Estado: **revisión técnica entregada; validación con personas pendiente**. Este documento no acredita una auditoría contra un objetivo real.

## Frontera operativa comprobada

SecLab-SBF dispone de un matcher compartido y un sondeo HTTP controlado. No dispone de una frontera universal que intercepte todo comando de una shell libre. La autenticación de la terminal y las políticas de VPN/rutas/red protegen acceso y destinos de infraestructura; no sustituyen las reglas de un engagement.

El límite del reconocimiento gestionado por el producto es:

**dashboard/`pt-recon` → pipeline → scope cargado → filtrado de candidatos → sondeo fijado a IP → artefactos**

El pipeline carga `target.yaml`/`scope.txt` al construir la ejecución. Utiliza ese objeto durante las etapas; no registra una versión de alcance ni recarga el archivo antes de cada petición. Por tanto, editar el alcance mientras corre no revoca automáticamente lo que autorizó el snapshot ya cargado. Esa diferencia pertenece a V3-01.

## Inventario de caminos

| Camino real | Interacción | Control comprobado | Límites/procedencia y trabajo pendiente |
|---|---|---|---|
| Alta y edición de proyecto: `WorkspaceSyncService.create_engagement`, `save_target_yaml` | Local | `initial_scope` y `validate_scope`; el wizard confirma antes de recon | No es una autorización universal de terminal ni un permiso activo versionado |
| `POST /recon/{id}/run` → `ReconService.run_pipeline` | Depende de etapa | Tipos/etapas válidas; ejecución única por proyecto; pipeline carga scope; gestión de cancelación | Crea job antes de la validación del pipeline; error queda como `failed`; no existe estado específico de bloqueo por autorización |
| `pt-recon` → `pt-recon-pipeline run` | Depende de etapa | Mismo pipeline que dashboard | Fase 146 elimina el fallback que evitaba matcher/límites y omitía `--dry-run` |
| `run_subdomain_enumeration` y `run_url_harvesting` | Consultas a fuentes externas, declaradas pasivas | Resultados filtrados con el matcher; fallos de herramientas no se aceptan como resultados parciales | No comprobar aquí el comportamiento de red completo de cada binario; verificar los modos de proveedores en V3-01/04. Hallazgo de un host no amplía scope |
| `run_live_probing` → `ProbeClient.probe_host` | HTTP/HTTPS activo | Filtra host, endpoint y direcciones DNS; rechaza destinos protegidos; fija IP de conexión; conserva Host/SNI; no sigue redirects; aplica rate, concurrencia, timeout y límite de targets | Scope es el snapshot de la ejecución. Guarda IP observada y Location, pero no historia de DNS/CNAME con timestamps por resolución |
| `run_pattern_classification` (`gf`) | Local | Filtra URLs según scope antes/después de clasificación | Clasificación no confirma vulnerabilidad ni crea automáticamente ficha de hallazgo |
| `pt-nmp` / alias `nmp` | Activa | Sin invocación de Scope Guard en el helper | Escaneo de puertos y scripts a tasa alta; no consume `operational_limits`. Requiere decisión del operador; V3-01/04 debe definir un camino guiado adecuado |
| `pt-fuzz-params` / alias `fuzzparams` | Activa | Comprueba existencia de `x8`, no scope ni límites del engagement | Admite flags adicionales; su comportamiento no queda interceptado por el pipeline |
| `pt-s3-ls` / alias `awsl` | Consulta remota | Sin asociación a engagement | Usa AWS CLI, s3scanner o curl; no interpretar esa consulta como autorizada por Scope Guard |
| Terminal integrada → ttyd y comandos directos | Depende del operador | Autenticación de sesión y renovación de autorización de acceso | Reenvía bytes, no interpreta targets. Un `curl`/`nmap` directo puede evitar helpers; alcance sigue dependiendo del operador y controles de red aplicables |
| `pt-forward`, `pt-socks`, `pt-web` → `proxy-control.resolve_target` | Activa/proxy | Exige VPN activa, ruta por `tun0` y bloquea rangos protegidos | No carga `target.yaml`; una ruta VPN permitida no prueba que el objetivo esté dentro del scope |
| `pt-callback`, `pt-serv-web`, `pt-serv-smb`, `pt-serv-payloads` | Listener/recepción, no escaneo por sí mismo | Exposición limitada por políticas de red del despliegue | Escuchan en interfaces del laboratorio. Callback guarda en `/tmp`, sin job/engagement/token de evidencia; la consulta que induzca el callback debe autorizarse por separado |
| Proxy Shodan y catálogo/Chat/Copiloto LLM | Proveedores configurados | Vault y autenticación del dashboard; timeouts del proveedor | El endpoint de Shodan no toma engagement; las peticiones LLM contienen contexto. No atribuir permiso activo contra un target por configurar un proveedor |
| Copiloto `/chat` | Consulta LLM | Envía contexto a proxy IA; comprueba targets sugeridos y antepone advertencia | No tiene despacho de comandos. Validación ausente/fallida puede omitirse; no hay contrato de citas a artefactos ni preview obligatorio del contexto saliente |
| Findings → `pt-report check/build` → pack/cierre | Local/export | `check` valida estructura y rechaza exclusión explícita; reporte distingue estados; paquete calcula SHA-256 | `build` no llama a `check`; `UNKNOWN` no falla en `check`; pack/cierre no hacen cumplir esa comprobación. Ver hallazgos D06–D08 |

## Puntos de entrada y fuentes

- [Matcher compartido](../scripts/seclab_scope.py): `initial_scope`, `normalize_target`, `check_scope`, `endpoint_matches`.
- [Pipeline](../scripts/pt-recon-pipeline.py): `ReconPipeline.__init__`, etapas, `run_all`, `.checkpoint.json`, `retry_command`.
- [Sondeo HTTP](../scripts/seclab_recon_probe.py): `destination_permitted`, `PinnedConnection`, `probe_host`.
- [Helpers de shell](../shell/pentest-lab/pentest-lab.plugin.zsh): `pt-recon`, `pt-nmp`, `pt-fuzz-params`, `pt-callback` y alias.
- [Lifecycle de recon](../dashboard/backend/app/services/recon_service.py) y [job store](../dashboard/backend/app/core/recon_jobs.py): job por engagement, cancelación, recuperación y reemplazo de último job.
- [Terminal](../dashboard/backend/app/api/endpoints/terminal_proxy.py) y [route guard](../scripts/proxy-control.py).
- [Artefactos/findings](../dashboard/backend/app/services/workspace_sync.py): `list_artifacts`, `save_finding`; [compilador](../scripts/pt-report-compiler.py); [packer/cierre](../scripts/pt-engagement-packer.py).
- [Copiloto](../dashboard/backend/app/api/endpoints/copilot.py), [contexto](../scripts/pt-agent-context.py) y [auditoría de proxy](../dashboard/backend/app/services/proxy_service.py).

## Hipótesis contrastadas y entregas siguientes

| ID | Estado | Evidencia | Acción |
|---|---|---|---|
| D01 | **Confirmada y corregida en 146** | Sin script, el fallback de `pt-recon` aceptaba `--dry-run` y ejecutaba herramientas legacy sin matcher | Detener con error antes de crear artefactos o invocar herramientas. Regresión real en Zsh y contenedor sin red |
| D02 | **Refutada para matcher actual** | Dominio exacto y wildcard distintos, exclusiones primero, canonicalización IDNA/IP, IPv6 y endpoints cubiertos por código/pruebas existentes | Conservar semántica y extender la explicación en UI, sin reescribir el matcher |
| D03 | **Refutada para sondeo interno; otros caminos pendientes** | `PinnedConnection` utiliza IP comprobada, Host/SNI original y registra `redirect_followed: false` | Verificar individualmente helpers/proveedores; no afirmar que todo producto aplica ese control |
| D04 | **Confirmada** | `pt-nmp`, `pt-fuzz-params` y shell libre no pasan por matcher; route guard comprueba rutas, no engagement | V3-01/04: delimitar ejecución gestionada y responsabilidades del operador; controles técnicos que sean viables |
| D05 | **Corregida en 149/150 para pipeline** | Baseline: scope cargado una vez, sin revisión ni permiso operativo explícito | Revisión/recarga en [fase 149](phase-149.md); referencia, vigencia y permisos pasivo/activo en [fase 150](phase-150.md), antes de tráfico. Terminal libre e historial ampliado pendientes |
| D06 | **Corregida en 147** | En fixture: `check` rechaza activo excluido (exit 1), `build` genera reporte que lo incluye (exit 0) | Check/build comparten validación; export recompila; download no reutiliza paquetes previos ante bloqueo. Ver [fase 147](phase-147.md) |
| D07 | **Parcialmente corregida en 147; procedencia pendiente** | En fixture: `check` acepta activo `UNKNOWN` (exit 0), texto PoC sintético sin artefacto original y estado `PROVEN`; cierre llega a `closed` | UNKNOWN y activo ausente ya bloquean check/build/export. Revisión de fuente original y cierre siguen pendientes en V3-03 |
| D08 | **Corregida en 148 para los casos diagnosticados** | Reporte asegura que `terminal.log` está archivado aunque el archivo no exista; pack omite `probe_observations.jsonl` y `recon.log`, pero hashes de archivos incluidos son correctos | Reporte basado en existencia de log; export conserva outputs diagnosticados y hashes original/copia. [Fase 148](phase-148.md). Cadena finding/job pendiente |
| D09 | **Confirmada parcialmente** | Job tiene `run_id`; En baseline SQLite conservaba el último job por engagement. Fase 152 añade historial persistente de jobs del dashboard, pendiente de merge. Artefactos expuestos por ruta/tamaño/mtime, sin ID independiente/job/source | V3-02/03: historial de decisiones y relaciones estables. No declarar ausencia total de IDs o hashing |
| D10 | **Refutada para recon; default corregido en 151** | El pipeline escribe recon, no findings. Baseline creaba ficha PROVEN por defecto | [Fase 151](phase-151.md): CANDIDATE inicial y sin estado; evita herencia de status en shell. Requisitos de confirmación/vínculo a output original pendientes |
| D11 | **Confirmada parcialmente** | Proxy registra proveedor/modelo/tiempo/latencia; chat inyecta contexto automáticamente. No hay dispatcher de ejecución para IA ni referencias estructuradas a artefactos | V3-05: citas, contexto saliente revisable, redacción y degradación visible del validador |
| D12 | **Pendiente con personas** | No se realizaron sesiones con principiantes, expertos ni instructores | Medir claridad, fricción y necesidad de supervisión. No inferir abandono ni preferencias de la revisión técnica |

La corrección D06 tiene precedencia dentro de V3-03: puede implementarse como fase pequeña antes de la arquitectura completa de IDs. Las demás brechas P0 confirmadas se mantienen visibles y se entregan en PRs separados para revisión.

## Línea base técnica reproducible

El [recorder de fixtures](../scripts/verify/record-v3-baseline.py) trabaja sólo en directorios temporales, desactiva notificaciones y bloquea sockets/DNS en su proceso. El sondeo y proveedores del recorrido de reanudación son doubles de fixture identificados como tales; no acreditan reconocimiento real. El resultado medido está en [v3-phase146.json](baselines/v3-phase146.json).

| Tarea | Resultado observado |
|---|---|
| Definir scope exacto y simular | `example.test` permitido; subdominio no confirmado y exclusión descartados; 1 target de sondeo previsto; workspace sin cambios |
| Reanudar tras fallo de fuente de URLs | Checkpoint conserva subdomains/probe; reanudación completa sin repetir esas dos etapas; checkpoint retirado al finalizar |
| Pasar de ficha a reporte | Una ficha `PROVEN` sintética sin output vinculado pasa `check` con target `UNKNOWN`; target excluido falla `check` pero entra mediante `build` |
| Empaquetar/cerrar | SHA-256 del manifiesto correcto; dos fuentes originales preparadas no se incluyen; el cierre permite `closed` para la ficha sintética |

Comandos desde la raíz del checkout de revisión:

```sh
python3 scripts/verify/record-v3-baseline.py
/bin/sh scripts/verify/check-recon-shell.sh seclab-sbf:full-phase146
docker run --rm --read-only --network none --user tester \
  --tmpfs /tmp:rw,nosuid,nodev,mode=1777 \
  --mount type=bind,src="$PWD",dst=/repo,readonly \
  --entrypoint /opt/nxc/bin/python3 seclab-sbf:full-phase146 \
  /repo/scripts/verify/record-v3-baseline.py
```

El recorder informa comportamiento observado y no fija los fallos actuales como expectativas de regresión. Los futuros fixes pueden cambiar sus resultados. La regresión de shell sí exige bloqueo sin pipeline, ausencia de artefactos/llamadas y preservación de argumentos/código de salida del pipeline válido.

## Validación con personas pendiente

Para completar V3-00 faltan sesiones de tareas con perfiles reales. Registrar por sesión: perfil, tarea, resultado, tiempo hasta identificar el próximo paso, bloqueos/reintentos, hint utilizado, duda textual y evidencia que la persona pudo justificar. Los targets deben ser de práctica autorizada; no registrar claves ni contenido de auditorías reales.

1. Principiante: definir alcance exacto/subdominios, explicar qué autoriza, simular y distinguir simulación de resultado ejecutado.
2. Principiante/experto: salir, volver y continuar la etapa que falló; explicar por qué se repite o no una acción.
3. Principiante/experto: partir de una señal, conservar fuente, seleccionar candidato/confirmado y justificar el finding.
4. Experto/supervisor: localizar en el reporte el origen de una afirmación y decidir si es defendible.

No hay aún porcentajes de finalización, abandono, falsos bloqueos o tiempo de supervisión medidos. La instrumentación existente de jobs y proxy aporta datos técnicos, pero no mide decisiones/hints ni sustituye esas sesiones.

## Evolución posterior a la línea base

La línea base 146 se conserva como registro histórico. [Medición 147](baselines/v3-phase147.json): check UNKNOWN = 1, build de activo excluido = 1, export excluido = blocked. El recorder usa después una ficha dentro de alcance para observar los límites todavía pendientes de procedencia/cierre.

[Medición 148](baselines/v3-phase148.json): los outputs diagnosticados están en el export y la afirmación de log archivado sin archivo desaparece. El manifiesto de origen conserva hashes del original y la copia redactada; no prueba autoría ni vínculo finding/job.

[Medición 149](baselines/v3-phase149.json): simulación y checkpoint registran revisión del scope. Las pruebas de fase 149 demuestran bloqueo antes de nuevos procesos/DNS/conexiones al cambiar contrato. No se amplía la garantía a procesos ya iniciados o shell libre.

[Entrega 150](phase-150.md): autorización explícita por interacción y ventana; ausencia/expiración bloquea herramientas y DNS/conexiones nuevas. Chrome verifica conservación de permiso pasivo sin activar probe. Revisión con personas, preview detallado e historial durable siguen pendientes.

[Entrega 152 guardada](phase-152.md): historial durable de metadatos de jobs del dashboard con migración limitada al último job legado, API por cursor y UI. Reinicio y paginación comprobados con fixture aislado. Sesión detenida por petición del owner; pendiente CI/revisión/merge. No completa eventos del engagement ni snapshots/vínculos de artefactos.
