# Fase 154: instalación de Playwright y credenciales temporales

Fecha: 2026-10-08. Base: `aaacc97` (#173 mergeado con aprobación individual). Rama `phase/154-playwright-setup`, worktree `/Users/castr/tmp/t01-playwright`.

## Estado al detenerse

Owner pidió detenerse para salir. Instalación funcional guardada; no mergeada. Pendiente reconstruir imagen con el último ajuste de configuración, repetir sus gates finales y revisar CI antes de pedir aprobación individual. No iniciar otra mejora mientras siga vigente la petición de parar.

## Entrega

Playwright Test 1.64.0 fijado como dependencia de desarrollo y lockfile actualizado. Chromium instalado en la caché local. Configuraciones para UI con API simulada y login real con backend desechable; scripts npm para instalación, ejecución, modo UI/visible y reporte.

La aplicación solo admite `tester`, sin creación multiusuario. Se pidió aclaración sobre nombres distintos; por ahora se implementó `tester` temporal con contraseña aleatoria por ejecución, datos/workspace vacíos y sesión revocada tras logout. No se modifica la cuenta ni el password del laboratorio real. Las credenciales se guardan privadas y se borran al finalizar.

Dos pruebas de UI y una de login/logout real pasaron. Se detectó que el cierre forzado por defecto de Playwright dejaba Docker y credenciales; se corrigió con `gracefulShutdown` SIGTERM. Repetición de integración aprobada y comprobación posterior: ningún contenedor `seclab-playwright-*` ni directorio de credenciales permanece. El fixture inicial se limpió explícitamente.

## Validación y pendientes

- 169 Python, 97 frontend, audit 0; dos pruebas Chromium UI y una integración real aprobadas.
- Imagen aislada `seclab-sbf:full-phase154` (`1650475a883fd914`) construida antes del último ajuste de cierre gradual; 146 backend, smoke, Compose, Actionlint y CVE aprobados contra ese snapshot.
- **La imagen todavía no corresponde a los insumos finales** (configuración de cierre actualizada después). Reconstruir etiqueta aislada y volver a registrar hash/gates antes de aprobación. No se toca `seclab-sbf:full` ni el contenedor vivo.
- Instalación/utilización documentadas en [guía E2E](../dashboard/frontend/e2e/README.md). La suite de UI simulada no sustituye la integración real; las tres pruebas iniciales no cubren toda la aplicación. Solo Chromium configurado; CI no ejecuta todavía estas suites.

Reversión: retirar dependencia/scripts/configuraciones/pruebas. Los binarios Chromium viven en caché del usuario y no son recursos del laboratorio. Ninguna cuenta de producción ni datos del owner fueron modificados.
