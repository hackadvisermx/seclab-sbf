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

`test:e2e` construye el frontend y abre una vista previa propia en `127.0.0.1:4199`. Dos pruebas de UI verifican el formulario/error de acceso y persistencia de tema. La API está simulada y las peticiones externas se abortan; estas dos pruebas no verifican autenticación del backend.

## Backend real con usuario temporal

Construir primero la imagen aislada desde la raíz del repositorio:

```sh
make build-full BUILD_TAG=-phase154
```

Después, desde `dashboard/frontend`:

```sh
npm run test:e2e:integration
```

El runner arranca un contenedor propio como tester, rootfs de solo lectura, sin capabilities, en el puerto loopback 4199. Workspace y base de datos son directorios temporales vacíos. No reutiliza un servidor existente: un puerto ocupado hace fallar el arranque.

El dashboard solo implementa la identidad `tester`. Cada ejecución crea una contraseña aleatoria para esa identidad en el backend desechable. No hay API de alta de usuarios ni se añaden identidades distintas a producción. La prueba realiza login real, verifica `/auth/me` y cookie HttpOnly, hace logout y comprueba que la sesión dejó de ser válida.

Credenciales privadas: `e2e/.playwright-fixture/user.json`, modo 0600, ignorado por Git. No se imprimen en stdout. El directorio, el contenedor y los datos se eliminan al terminar mediante SIGTERM con cierre gradual. Si el host muere o se usa SIGKILL, comprobar el contenedor propio antes de limpiar restos; no borrar ni detener el laboratorio vivo.

Para elegir otra imagen local compatible:

```sh
PLAYWRIGHT_LAB_IMAGE=seclab-sbf:full npm run test:e2e:integration
```

Esto crea otro contenedor; no reinicia el que ya esté en uso. La suite real utiliza el frontend instalado en la imagen elegida. Solo Chromium está configurado por ahora. Los reportes/trazas/capturas son locales e ignorados por Git. No se agregó ejecución de navegador a CI en esta entrega.

Configuración y instalación basadas en la [documentación oficial](https://playwright.dev/docs/intro); el [cierre gradual](https://playwright.dev/docs/test-webserver) permite eliminar el fixture de Docker.
