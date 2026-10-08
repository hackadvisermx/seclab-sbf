# Fase 155: recorrido de auditoría con Playwright

Fecha: 2026-10-08. Base `006e10b` (#174 fusionado con aprobación individual). Rama `phase/155-audit-workflow-e2e`, worktree `/Users/castr/tmp/t01-audit-e2e`.

## Recorrido comprobado

Prueba Chromium con frontend y backend reales instalados en la imagen aislada. Crea `playwright-audit` desde el wizard, verifica alcance exacto `example.test`, confirmación requerida y simulación por defecto. Guarda referencia/vigencia sin habilitar tráfico. Una lista de hosts sintética creada por la prueba permite llegar al gate activo: el job queda bloqueado por permiso activo ausente. Sus dos IDs y estados persisten al recargar.

El formulario crea una ficha CANDIDATE con pasos y petición/respuesta sintéticos. Se compila un borrador con cero confirmados activos y cifras ejecutivas coherentes. La prueba revisa Markdown, conserva evidencia, añade control negativo sintético y selecciona PROVEN explícitamente; el nuevo reporte registra un confirmado sintético. Descarga el paquete y compara hashes SHA-256 de originales y copias con `source-manifest.json`. Al cambiar el activo a `outside.test`, la UI presenta bloqueo y la descarga responde 409 aunque exista un reporte anterior.

El estado PROVEN usado aquí es una declaración del operador del fixture, no una validación de seguridad sobre un objetivo real. No se acredita suficiencia de evidencia ni relación estructurada job → finding. Esto amplía V3-00 sin cerrar las iniciativas de procedencia/revisión humana.

## Fallos encontrados y corregidos

- El compilador no reconocía `## Pasos para Reproducir`, encabezado que genera el formulario. Una ejecución contra la imagen anterior `full-phase154` llegó a la ficha y reprodujo rechazo por PoC ausente; el matcher reconoce ahora ambos formatos. La regresión también comprueba que sin encabezado ni comando no se satisface la comprobación. Esta comprobación sigue siendo heurística.
- La vista ejecutiva contaba todas las fichas, incluidos candidatos/mitigados, mientras el Markdown cuenta solo PROVEN activo. Sus cifras proceden ahora del reporte compilado mostrado; no cambian por editar fichas hasta recompilar.
- La portada mostraba CONFIRMADO para un borrador y calculaba fecha actual al no reconocer `Fecha de Emisión`. Se ajustan al contrato del compilador.
- Un resultado `success=false` de compilación se trataba como respuesta exitosa y recargaba un reporte previo. Se conserva el reporte anterior y se muestra el motivo de rechazo, sin anunciar una compilación nueva.

## Fixture y aislamiento

Tester con contraseña aleatoria, workspace/base de datos temporales, rootfs read-only, capabilities eliminadas. Docker usa `--network none`, comprobado por la prueba. El puente Node escucha solo `127.0.0.1:4199` y usa `docker exec -i`/socat hacia el loopback del backend; Docker no publica puertos. Las peticiones externas del navegador se abortan. No se llama IA, herramientas de descubrimiento ni objetivos externos.

`workspace.json` contiene únicamente ruta/container del fixture y se elimina junto con `user.json`. El puente reserva su puerto antes de iniciar el contenedor, para que un puerto ocupado no deje un proceso tardío. Cierre SIGTERM elimina puente, conexiones, contenedor y datos; SIGKILL o muerte del host siguen requiriendo revisar restos propios. Se conservan exclusiones de reportes/trazas/credenciales en Git, Docker y cálculo de insumos.

## Validación

- 171 Python (`make verify`), 146 backend, 99 frontend, npm audit 0 vulnerabilidades.
- Chromium: 2 pruebas UI y 2 pruebas de integración real aprobadas; recorrido completo repetido sin fallos con fixture sin red.
- Imagen `seclab-sbf:full-phase155`, etiqueta de insumos `da197936713eaab8`, idéntica al cálculo del checkout después de las pruebas. Build, smoke, Compose `.env.example`, Actionlint y gate High/Critical aprobados bajo la política existente, sin nuevas excepciones.
- Timeout intencional de 1 ms falla como se esperaba y limpia recursos; arranque con puerto ocupado devuelve error explícito sin iniciar contenedor ni dejar credenciales. Tras ejecución normal no quedan contenedores `seclab-playwright-*` ni directorio privado.
- PR hacia baseline preparado para revisión; CI remoto y aprobación individual de merge se consultan en el PR.

Comandos:

```sh
make verify
make build-full BUILD_TAG=-phase155
make dashboard-tests LAB_IMAGE=full-phase155 IMAGE_SOURCE=remote
npm --prefix dashboard/frontend test
npm --prefix dashboard/frontend run audit
npm --prefix dashboard/frontend run test:e2e
npm --prefix dashboard/frontend run test:e2e:integration
make smoke-test SCAN_IMAGE=seclab-sbf:full-phase155
make compose-config ENV_FILE=.env.example LAB_IMAGE=full-phase155
go run github.com/rhysd/actionlint/cmd/actionlint@v1.7.12
make scan-image SCAN_IMAGE=seclab-sbf:full-phase155
```

Solo Chromium/macOS Docker Desktop comprobados; no se añade navegador al CI. Requisitos y ejecución en la [guía E2E](../dashboard/frontend/e2e/README.md). Laboratorio vivo, proyectos y etiqueta `seclab-sbf:full` intactos. Reversión mediante revert del commit; retirar el nuevo test/puente y restituir las vistas/parser anteriores no requiere migración.
