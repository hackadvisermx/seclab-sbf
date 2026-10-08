# Pruebas de navegador

Playwright Test 1.64.0 está fijado en package.json/lockfile. Los navegadores se instalan en la caché local del usuario; no forman parte de la imagen de producción.

Desde `dashboard/frontend`:

```sh
npm ci
npm run test:e2e:install
npm run test:e2e
npm run test:e2e:ui
npm run test:e2e:headed
npm run test:e2e:report
```

Ejecuta UI e integración de forma secuencial: comparten el puerto 4199 y el directorio de resultados.

`test:e2e` construye el frontend y abre una vista previa propia en `127.0.0.1:4199`. Dos pruebas de UI verifican el formulario/error de acceso y persistencia de tema. La API está simulada y las peticiones externas se abortan; estas dos pruebas no verifican autenticación del backend.

## Backend real con usuario temporal

Construir primero la imagen aislada desde la raíz del repositorio:

```sh
make build-full BUILD_TAG=-phase158
```

Después, desde `dashboard/frontend`:

```sh
npm run test:e2e:integration
```

El runner arranca un contenedor propio como tester, rootfs de solo lectura, sin capabilities y con `--network none`. Un puente Node en `127.0.0.1:4199` utiliza `docker exec -i ... socat STDIO TCP:127.0.0.1:8080` para acceder al backend por su loopback. No publica puertos Docker ni permite salida de red desde el contenedor. Workspace y base de datos empiezan vacíos en directorios temporales. No reutiliza un servidor existente: un puerto ocupado hace fallar el arranque.

El dashboard solo implementa la identidad `tester`. Cada ejecución crea una contraseña aleatoria para esa identidad en el backend desechable. No hay API de alta de usuarios ni se añaden identidades distintas a producción. La prueba de autenticación realiza login real, verifica `/auth/me` y cookie HttpOnly, hace logout y comprueba que la sesión dejó de ser válida.

La prueba de auditoría recorre el wizard, verifica dominio exacto y confirmación, ejecuta una simulación, declara referencia/vigencia sin permisos de tráfico y comprueba bloqueo activo en la vista previa y en un job iniciado directamente por API (para verificar el control del backend). El helper publica la ruta privada del workspace en `workspace.json`; la prueba escribe únicamente `example.test` en la lista de hosts del proyecto recién creado, sin ejecutar descubrimiento. Comprueba dos jobs distintos en el historial tras recargar, crea una ficha CANDIDATE con petición/respuesta sintéticas, compila con cero confirmados, revisa el Markdown y declara PROVEN explícitamente para comprobar el reporte con un confirmado sintético. Descarga el paquete y verifica entradas/hashes del source-manifest; un activo `outside.test` bloquea recompilación y descarga incluso si existe un reporte previo. Estas pruebas no acreditan suficiencia probatoria ni vínculo estructurado job → finding.

Otra prueba comprueba la vista previa sin crear jobs, el bloqueo por permiso ausente, la invalidación al cambiar modo y el rechazo de una lista modificada tras la revisión. Tras revisar de nuevo, permite simular y comprueba que el historial conserva la revisión original después de cambiar la lista y recargar. Captura `review-history.png` en el directorio local de resultados.

Requisitos de integración: Docker local, imagen construida, Chromium instalado y `tar` en el host. `socat` ya forma parte de la imagen. La suite no llama proveedores de IA ni servicios externos.

Credenciales privadas: `e2e/.playwright-fixture/user.json`, modo 0600, ignorado por Git. No se imprimen en stdout. El directorio, el contenedor y los datos se eliminan al terminar mediante SIGTERM con cierre gradual. Si el host muere o se usa SIGKILL, comprobar el contenedor propio antes de limpiar restos; no borrar ni detener el laboratorio vivo.

Para elegir otra imagen local compatible:

```sh
PLAYWRIGHT_LAB_IMAGE=seclab-sbf:full npm run test:e2e:integration
```

Esto crea otro contenedor; no reinicia el que ya esté en uso. La suite real utiliza el frontend instalado en la imagen elegida. Solo Chromium está configurado por ahora. Los reportes/trazas/capturas son locales e ignorados por Git. No se agregó ejecución de navegador a CI en esta entrega.

Configuración y instalación basadas en la [documentación oficial](https://playwright.dev/docs/intro); el [cierre gradual](https://playwright.dev/docs/test-webserver) permite eliminar el fixture de Docker.
