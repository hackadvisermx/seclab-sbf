# Fase 144: arranque de subfinder en contenedor de solo lectura

Fecha: 2026-10-07. Base: `f0cd7f4`. Rama: `phase/144-subfinder-readonly-config`.

## Incidente y evidencia

El owner reportó un fallo inmediato de la etapa Subdominios en el dashboard. `recon/summary.json` de la ejecución existente registra `subfinder: código de salida 1`; el pipeline descartó los resultados parciales correctamente. No se repitió el reconocimiento contra el dominio ni se modificó el proyecto del owner.

Una comprobación local, `docker exec --user tester seclab-sbf-lab-1 subfinder -version`, muestra:

```text
Could not create provider config file: open /home/tester/.config/subfinder/provider-config.yaml: read-only file system
```

La prueba con el entorno exacto del dashboard (`HOME=/root`, conservado por `su -m`) reproduce el código 1 inmediatamente, incluso con el archivo de proveedores precargado:

```text
open /root/.config/subfinder/config.yaml: permission denied
```

Ese es el fallo fatal de la ejecución del dashboard. La comprobación inicial de versión detectó además otro defecto: la imagen precargaba `config.yaml`, pero faltaba `provider-config.yaml`. El directorio bajo `/home/tester` forma parte de la raíz de solo lectura; el binario intenta generar su configuración de proveedores al arrancar. Que `-version` imprima una versión o termine con cero no basta: también emite este error. La nueva prueba comprueba su diagnóstico.

## Corrección mínima

- `scripts/dashboard-service.sh` fija `HOME=/home/tester` antes de iniciar el backend, igual que el servicio de terminal. Las herramientas hijas dejan de buscar configuración bajo `/root`.
- `images/full/Dockerfile` precarga `provider-config.yaml` como `{}` al construir, junto al archivo de configuración existente. No contiene credenciales ni habilita permisos de escritura adicionales.
- El pipeline reconoce ese error específico y ofrece una acción de reconstrucción sin volcar stderr arbitrario. Conserva el fallo cerrado: no consume stdout parcial ni reemplaza artefactos anteriores.
- Los mensajes de reintento usan la firma real `pt-recon <ruta>` sin el `run` extra. Con checkpoint sugieren `--resume`; una etapa aislada sin checkpoint sugiere `--stage <etapa>`. La ruta se entrecomilla para shell, también en retos o nombres con espacios.
- `scripts/verify/check-subfinder-readonly.sh` ejecuta el binario real como `tester`, con `--read-only --network none`, y falla si hay errores de inicialización aunque `-version` retorne cero. También carga la preparación real de `dashboard-service.sh` con `HOME=/root` heredado, estado temporal y raíz de solo lectura, y exige que `subfinder` arranque sin errores. Se integra en `smoke-test.sh`.
- Dos regresiones Python cubren conservación de artefactos/diagnóstico y la elección de comando con o sin checkpoint.

## Validación

| Comprobación | Resultado |
| --- | --- |
| `make verify` | OK: 140 pruebas Python, secretos, Dockerfile, shell, pines y políticas Compose. |
| `make build-full BUILD_TAG=-phase144` | OK: imagen aislada `seclab-sbf:full-phase144`, build-inputs `cba572239cd61b1d`. |
| `make dashboard-tests IMAGE_SOURCE=remote LAB_IMAGE=seclab-sbf:full-phase144` | OK: 124 pruebas del backend. |
| `make smoke-test SCAN_IMAGE=seclab-sbf:full-phase144` | OK: runtimes, herramientas y arranque de subfinder con entorno del dashboard. |
| `/bin/sh scripts/verify/check-subfinder-readonly.sh seclab-sbf:full-phase144` | OK; falla en imagen anterior y con servicio anterior aunque se añada el archivo de proveedores. |
| `make compose-config ENV_FILE=.env.example` | OK: configuraciones local y VPN-inside. |
| `go run github.com/rhysd/actionlint/cmd/actionlint@v1.7.12` | OK. |
| `shellcheck scripts/verify/check-subfinder-readonly.sh scripts/dashboard-service.sh scripts/verify/smoke-test.sh` | OK. |
| `make scan-image SCAN_IMAGE=seclab-sbf:full-phase144` | OK para la imagen final: gate High/Critical con la política existente, sin nuevas excepciones. |

Las comprobaciones funcionales usaron contenedores desechables, sin red y sin montajes de datos del owner. No hubo cambios de frontend; no corresponde una nueva prueba visual. El gate de CVEs conserva `--ignore-unfixed=true` y las excepciones existentes; no se añaden excepciones ni dependencias.

Reproducción antes del cambio:

```sh
/bin/sh scripts/verify/check-subfinder-readonly.sh seclab-sbf:full-phase143
# exit 1: configuracion-no-precargada
```

## Uso y límites

Una imagen nueva no cambia el contenedor en ejecución. Tras aprobar y fusionar el PR, reconstruir y relanzar cuando el owner decida:

```sh
make build-full
make compose-down
make compose-up
```

Luego reintentar la etapa seleccionada desde el dashboard o, dentro del contenedor:

```sh
pt-recon /workspace/engagements/nombre-del-proyecto --stage subdomains
```

Para una cadena completa fallida que conserve `recon/.checkpoint.json`, usar `--resume`. Los subdominios descubiertos siguen filtrándose por el alcance: un dominio exacto no autoriza sus subdominios. No ampliar el alcance para ocultar un resultado vacío.

La comprobación sin red verifica el arranque y la configuración, no la disponibilidad de cada proveedor pasivo ni la exhaustividad de resultados. No se cambiaron límites, dependencias ni credenciales. El contenedor y los datos del owner permanecieron sin operaciones de escritura o reinicio por parte del agente.

Reversión: revert del PR y reconstrucción; no requiere migración ni modificar proyectos existentes.
