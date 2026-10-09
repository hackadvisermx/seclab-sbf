# Fase 165: paridad del checklist instalado

Fecha: 2026-10-09. Rama `phase/165-installed-checklist-parity`, base `4e6d05c`, worktree `/Users/castr/tmp/t01-checklist-parity`. Entrega parcial V3-02g.

## Problema comprobado y cambio

`Dockerfile` instala el checklist como `/usr/local/bin/pt-audit-checklist`, sin `.py`. pt-next, pt-context y check_closure_readiness del packer intentaban cargarlo con spec_from_file_location sin loader explícito. Python no selecciona un loader para ese nombre, y los consumidores caían silenciosamente a sus comportamientos anteriores sin evaluator. Las pruebas desde scripts con `.py` no reproducían la instalación.

En `full-phase164`, una fixture sin red con un host sintético y marcador `## Disciplina: fuzzing` producía checklist 25%, contexto 0%, siguiente paso recon y recomendaciones de cierre vacías. La nueva regresión instalada falla en esa imagen. Con el arreglo produce contexto 25%, matriz de ocho disciplinas, siguiente auth y las recomendaciones del mismo evaluator del checklist.

Los tres consumidores usan SourceFileLoader de la biblioteca estándar y consideran también el archivo vecino sin extensión. Se conserva la prioridad de la fuente `.py`, el path instalado y el respaldo relativo. No agrega módulos/dependencias ni modifica el evaluator, permisos, comandos definidos o reglas de cierre. La revisión del último job agregada por fase164 sigue teniendo prioridad en el dashboard cuando corresponde.

## Validación

```sh
make verify
make build-full BUILD_TAG=-phase165
make dashboard-tests LAB_IMAGE=full-phase165 IMAGE_SOURCE=remote
npm --prefix dashboard/frontend test
npm --prefix dashboard/frontend run audit
npm --prefix dashboard/frontend run test:e2e
npm --prefix dashboard/frontend run test:e2e:integration
make smoke-test SCAN_IMAGE=seclab-sbf:full-phase165
make compose-config ENV_FILE=.env.example LAB_IMAGE=full-phase165
go run github.com/rhysd/actionlint/cmd/actionlint@v1.7.12
make scan-image SCAN_IMAGE=seclab-sbf:full-phase165
```

- 184 Python, 195 backend, 118 frontend, audit 0. La nueva prueba Python verifica ambos nombres (`.py` y sin extensión) en instalación temporal: puntaje, estados de matriz, siguiente disciplina y readiness/recomendaciones de cierre coinciden con el evaluator real.
- `scripts/verify/check-installed-checklist.sh` integrado en smoke ejecuta los comandos instalados reales como tester, raíz de solo lectura y `--network none`, fuera del repo. Comprueba checklist/contexto/matriz/pt-next y revisión de cierre; no lanza reconocimiento ni proveedor. Falla en phase164 y pasa en phase165.
- 3 UI y 5 integraciones Chromium aprobadas con backend/tester temporal sin red. El caso de sesión conserva login/logout y agrega API/checklist/next, panel con 25% y visor de contexto con 2/8 disciplinas. Captura `installed-checklist.png` inspeccionada; ninguna consulta de IA ni jobs nuevos en ese caso. Fixture/credenciales eliminados al terminar.
- Imagen aislada `seclab-sbf:full-phase165`, hash `06d43313ac4bf916`, idéntico al checkout. Build, smoke, Compose, Actionlint y gate CVE High/Critical aprobados bajo la política existente; CI del head final se registra al cerrar el PR. Sin dependencias ni excepciones nuevas. Logs/reproducción/captura en `tmp/phase165` del checkout principal.

## Compatibilidad, límites y reversión

No migra archivos, bases o jobs. Corrige la paridad de ejecución instalada con el código fuente: puede cambiar la recomendación y los datos de cobertura incluidos en el contexto, que antes eran el fallback vacío. La política de readiness del checklist permite cerrar sin exigir todas las disciplinas; esta entrega no convierte un puntaje de cobertura en una compuerta de autorización o garantía de pruebas completadas.

La heurística de archivos y marcadores sigue igual; el checklist no lee jobs. Checklist ausente o fallando conserva los fallbacks anteriores, sin nuevo aviso de disponibilidad. Tampoco añade fuentes navegables, revisión/redacción de contexto remoto, aceptación humana o timeline. Revert restaura el comportamiento anterior sin pérdida de datos. No cambia el contenido de la UI ni ejecuta consultas al objetivo. Laboratorio vivo, imagen full y proyectos del owner intactos.

Merge requiere PR hacia bootstrap/baseline, revisión del diff, gates y CI del head exacto. Autorización explícita renovada vigente hasta 2026-10-10 14:56:00 UTC (08:56 Ciudad de México); después vuelve aprobación individual.
