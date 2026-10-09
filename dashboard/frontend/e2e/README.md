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

`test:e2e` construye el frontend y abre una vista previa propia en `127.0.0.1:4199`. Tres pruebas de UI verifican el formulario/error de acceso, persistencia de tema y aviso de validación no disponible del Copiloto sin ejecución. La API está simulada y las peticiones externas se abortan; estas pruebas no verifican autenticación del backend.

## Backend real con usuario temporal

Construir primero la imagen aislada desde la raíz del repositorio:

```sh
make build-full BUILD_TAG=-phase165
```

Después, desde `dashboard/frontend`:

```sh
npm run test:e2e:integration
```

El runner arranca un contenedor propio como tester, rootfs de solo lectura, sin capabilities y con `--network none`. Un puente Node en `127.0.0.1:4199` utiliza `docker exec -i ... socat STDIO TCP:127.0.0.1:8080` para acceder al backend por su loopback. No publica puertos Docker ni permite salida de red desde el contenedor. Workspace y base de datos empiezan vacíos en directorios temporales. No reutiliza un servidor existente: un puerto ocupado hace fallar el arranque.

El dashboard solo implementa la identidad `tester`. Cada ejecución crea una contraseña aleatoria para esa identidad en el backend desechable. No hay API de alta de usuarios ni se añaden identidades distintas a producción. La prueba de autenticación realiza login real, verifica `/auth/me` y cookie HttpOnly, hace logout y comprueba que la sesión dejó de ser válida.

La prueba de auditoría recorre el wizard, verifica dominio exacto y confirmación, ejecuta una simulación, declara referencia/vigencia sin permisos de tráfico y comprueba bloqueo activo en la vista previa y en un job iniciado directamente por API (para verificar el control del backend). El helper publica la ruta privada del workspace en `workspace.json`; la prueba escribe únicamente `example.test` en la lista de hosts del proyecto recién creado, sin ejecutar descubrimiento. Comprueba dos jobs distintos en el historial tras recargar, crea una ficha CANDIDATE con petición/respuesta sintéticas, compila con cero confirmados, revisa el Markdown y verifica rechazo de PROVEN sin referencias/motivo. Revisa y vincula el archivo sintético, explica el motivo de verificación y declara PROVEN explícitamente para comprobar el reporte con un confirmado sintético. Descarga el paquete y verifica entradas/hashes del source-manifest; guardar confirmado con `outside.test` se rechaza; guardarlo como candidato bloquea recompilación y descarga incluso si existe un reporte previo. Estas pruebas no acreditan suficiencia probatoria ni vínculo estructurado job → finding.

Otra prueba comprueba la vista previa sin crear jobs, el bloqueo por permiso ausente, la invalidación al cambiar modo y el rechazo de una lista modificada tras la revisión. Tras revisar de nuevo, permite simular y comprueba que el historial conserva la revisión original después de cambiar la lista y recargar. Captura `review-history.png` en el directorio local de resultados.

Esa prueba también ejecuta dos sondeos con una lista vacía: no hay targets, sockets ni DNS. Cambia solo la lista sintética de URLs del workspace entre ambos y comprueba que el historial conserva conteos distintos (1 y 3), estados y scope por job al recargar. Un tercer sondeo con un host explícito sin permiso activo queda bloqueado antes de tráfico y conserva un resumen marcado como artefactos previos. La simulación y el bloqueo inicial con summary antiguo no reciben resultados inventados. Captura `result-history.png`; son conteos y estados, sin snapshots ni procedencia completa de outputs.

La auditoría sintética captura `confirmation-gate.png` cuando PROVEN aún carece de motivo. Al final añade una ficha VERIFIED antigua sin vínculos/motivo en el workspace temporal: verifica “Revisión pendiente”, ausencia de modificación al leer y rechazo de reporte/descarga. Captura `legacy-review-pending.png`. Estas comprobaciones validan requisitos e integridad, no la verdad o suficiencia de una afirmación del operador.

Requisitos de integración: Docker local, imagen construida, Chromium instalado y `tar` en el host. `socat` ya forma parte de la imagen. La suite no llama proveedores de IA ni servicios externos.

La prueba de artefactos escribe solo archivos sintéticos del proyecto temporal, compara SHA-256 con bytes originales, comprueba actualización de versión y el límite de previsualización de 2 MiB, y verifica que texto HTML permanece literal. Captura `artifact-fingerprint.png`; no realiza pruebas contra objetivos reales ni acredita vínculo con un job. Las cinco integraciones inician una sesión cada una, dentro del límite de cinco intentos por minuto de la instancia desechable.

Esa prueba también edita una ficha CANDIDATE para vincular explícitamente el artefacto revisado, conserva el vínculo tras recarga y verifica su inclusión/hash en reporte y paquete sanitizado. Cambiar los bytes muestra diferencia con la versión vinculada y bloquea recompilación/descarga; captura `linked-artifact-changed.png`. Vincular no confirma el finding ni acredita su origen en un job.

Credenciales privadas: `e2e/.playwright-fixture/user.json`, modo 0600, ignorado por Git. No se imprimen en stdout. El directorio, el contenedor y los datos se eliminan al terminar mediante SIGTERM con cierre gradual. Si el host muere o se usa SIGKILL, comprobar el contenedor propio antes de limpiar restos; no borrar ni detener el laboratorio vivo.

Para elegir otra imagen local compatible:

```sh
PLAYWRIGHT_LAB_IMAGE=seclab-sbf:full npm run test:e2e:integration
```

Esto crea otro contenedor; no reinicia el que ya esté en uso. La suite real utiliza el frontend instalado en la imagen elegida. Solo Chromium está configurado por ahora. Los reportes/trazas/capturas son locales e ignorados por Git. No se agregó ejecución de navegador a CI en esta entrega.

Configuración y instalación basadas en la [documentación oficial](https://playwright.dev/docs/intro); el [cierre gradual](https://playwright.dev/docs/test-webserver) permite eliminar el fixture de Docker.

El asistente de siguiente decisión da prioridad al bloqueo persistido del último job, aun con archivos y resultados previos. La prueba recarga, verifica el run_id, ausencia de comando/prompt de ejecución y navegación a Alcance; captura `next-decision.png`. No ejecuta la acción recomendada ni consulta un proveedor IA.

La prueba de sesión compara checklist, siguiente paso y contexto de los scripts instalados. Un host sintético y un marcador explícito de fuzzing dan 25% de cobertura, siguiente disciplina auth y contexto con 2/8 disciplinas. Comprueba la interfaz de cobertura y el inspector de contexto, captura `installed-checklist.png` y luego revoca la sesión. No inicia jobs ni envía contexto a un proveedor.
