# Fase 154: instalación de Playwright y credenciales temporales

Fecha: 2026-10-08. Base: `aaacc97` (#173 mergeado con aprobación individual). Rama `phase/154-playwright-setup`, worktree `/Users/castr/tmp/t01-playwright`.

## Estado al retomar

PR #174 fusionado con aprobación individual en `006e10b`; CI del head final aprobado en run `37808267032`. Rama/worktree retirados y baseline sincronizado. La fase 155 requiere su propia aprobación.

## Entrega

Playwright Test 1.64.0 fijado como dependencia de desarrollo y lockfile actualizado. Chromium instalado en la caché local. Configuraciones para UI con API simulada y login real con backend desechable; scripts npm para instalación, ejecución, modo UI/visible y reporte.

La aplicación solo admite `tester`, sin creación multiusuario. Se pidió aclaración sobre nombres distintos; por ahora se implementó `tester` temporal con contraseña aleatoria por ejecución, datos/workspace vacíos y sesión revocada tras logout. No se modifica la cuenta ni el password del laboratorio real. Las credenciales se guardan privadas y se borran al finalizar.

Dos pruebas de UI y una de login/logout real pasaron. Se detectó que el cierre forzado por defecto de Playwright dejaba Docker y credenciales; se corrigió con `gracefulShutdown` SIGTERM. Repetición de integración aprobada y comprobación posterior: ningún contenedor `seclab-playwright-*` ni directorio de credenciales permanece. El fixture inicial se limpió explícitamente.

## Validación final

- **170 Python**, **146 backend**, **97 frontend**, audit **0 vulnerabilidades**; dos pruebas Chromium UI y una integración real aprobadas.
- Imagen aislada `seclab-sbf:full-phase154`, hash `3e435b50c65014f8`, idéntico al cálculo de insumos tras las pruebas. Build, smoke, Compose `.env.example`, Actionlint y gate CVE bajo política vigente aprobados, sin excepciones nuevas.
- Un timeout forzado de 1 ms produce el fallo esperado; después no queda contenedor ni directorio de credenciales. Una nueva ejecución normal vuelve a pasar con cleanup comprobado.
- Se detectó y corrigió que los reportes/resultados de Playwright entraban en el hash y contexto Docker. `.dockerignore` y `EXCLUDED_ROOTS` excluyen reportes, resultados, blob-report y el directorio privado de credenciales. La regresión comprueba que no cambian el hash y que config/helpers/tests sí lo cambian; también verifica las exclusiones Docker.
- No se modifica `seclab-sbf:full` ni el laboratorio vivo.
- Instalación/utilización documentadas en [guía E2E](../dashboard/frontend/e2e/README.md). La suite de UI simulada no sustituye la integración real; las tres pruebas iniciales no cubren toda la aplicación. Solo Chromium configurado; CI no ejecuta todavía estas suites.

Reversión: retirar dependencia/scripts/configuraciones/pruebas. Los binarios Chromium viven en caché del usuario y no son recursos del laboratorio. Ninguna cuenta de producción ni datos del owner fueron modificados.
