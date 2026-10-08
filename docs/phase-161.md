# Fase 161: versiones de artefactos vinculadas a hallazgos

Fecha: 2026-10-08. Rama `phase/161-finding-artifact-links`, base `eef7924`, worktree `/Users/castr/tmp/t01-finding-artifacts`. Entrega parcial V3-03e.

## Cambio

Las fichas admiten `artifact_refs`, lista explícita de objetos con `path` y `sha256`. La UI permite revisar el artefacto y luego vincular esa versión; no cambia el estado del hallazgo. Conserva el cuerpo Markdown y referencias al editar/recargar. Abrir una referencia muestra el original actual y avisa si su hash difiere del guardado. Respuestas tardías del revisor se descartan al cambiar ruta, modal o proyecto.

La API comprueba las referencias explícitas antes de guardar. Omitir el campo conserva referencias anteriores; `[]` las retira explícitamente y `null` se rechaza. Metadata inválida se muestra con error sin ocultar la ficha y exige reparación explícita antes de editar. Las referencias se escriben como JSON de una sola línea dentro del frontmatter YAML, compatible con el parser de reporte existente.

El lector de fase 160 se comparte mediante `scripts/seclab_artifacts.py`, instalado en la imagen y reexportado desde el backend para mantener consumidores. Conserva apertura por descriptores, NOFOLLOW, rechazo de archivos no regulares y comprobaciones de cambios. El modo privado de exportación captura los bytes de la misma lectura; no se expone por la API.

Check/build validan todas las referencias declaradas, incluidos candidatos. Referencias inválidas, archivos ausentes o hashes distintos bloquean antes de sobrescribir REPORT.md. El reporte muestra ruta/enlace y hash. El compilador entrega al packer las referencias que validó para evitar seleccionar desde una nueva lectura de fichas. El packer vuelve a comprobar los bytes al copiar, incluye los archivos seleccionados y registra hashes de original/copia en `source-manifest.json`. Duplicados con archivos ya incluidos se comparan y no se copian dos veces. Sanitización modifica solo la copia; binarios/NUL y texto no UTF-8 seleccionado bloquean el export sanitizado, incluso si ya formaban parte de la selección convencional. El bundle previo y los originales se conservan ante rechazo; staging se limpia.

## Validación

Comandos de esta entrega:

```sh
make verify
make build-full BUILD_TAG=-phase161
make dashboard-tests LAB_IMAGE=full-phase161 IMAGE_SOURCE=remote
npm --prefix dashboard/frontend test
npm --prefix dashboard/frontend run audit
npm --prefix dashboard/frontend run test:e2e
npm --prefix dashboard/frontend run test:e2e:integration
make smoke-test SCAN_IMAGE=seclab-sbf:full-phase161
make compose-config ENV_FILE=.env.example LAB_IMAGE=full-phase161
go run github.com/rhysd/actionlint/cmd/actionlint@v1.7.12
make scan-image SCAN_IMAGE=seclab-sbf:full-phase161
```

- `make verify`: 180 Python; 174 backend; 110 frontend; audit 0. Pruebas nuevas cubren preservación/omisión/remoción, metadata inválida, referencias duplicadas/traversal/ausentes/cambiadas, bloqueo antes de sobrescribir reporte, hashes y sanitización, binarios convencionales/seleccionados y cambio después de validación.
- 3 UI Chromium con API simulada y 5 integraciones con backend instalado, tester temporal y red deshabilitada. La integración extendida revisa/vincula, guarda/recarga, compila con cero confirmados, descarga/verifica hashes y bloquea al mutar el archivo. Captura `linked-artifact-changed.png` inspeccionada; temporal y credenciales eliminados al terminar.
- Imagen aislada `seclab-sbf:full-phase161`, hash de insumos finales `b0f9704b4f544565`. Build, smoke, Compose `.env.example`, Actionlint y gate CVE High/Critical aprobados bajo política vigente, sin nuevas dependencias ni excepciones. Laboratorio vivo intacto.
- CI remoto del head exacto pendiente al crear el PR.

## Límites, compatibilidad y reversión

Máximo 10 referencias por ficha, rutas ASCII sin espacios en recon/, fuzzing/ o screenshots/, sin componentes vacíos/dot/traversal ni duplicados. No se permite seleccionar loot/. Límite de 32 MiB de archivos referidos por ficha y de selección total del paquete; preview conserva límite de 2 MiB. Validación de una referencia puede leerla antes de detectar que la suma excede el límite. No se limita aquí el tamaño de los archivos convencionales legacy del packer.

Las referencias identifican contenido, no procedencia, autorización ni suficiencia de prueba. Siguen siendo opcionales; PROVEN todavía no exige vínculo ni rationale estructurado. No se crean IDs persistentes, snapshots inmutables ni vínculos a job/herramienta/target originales. Renombrar o cambiar un archivo requiere revisar y volver a vincularlo. La validación no garantiza un snapshot atómico de todas las fichas/inputs del engagement ni impide cambios posteriores.

El dashboard exporta siempre sanitizado: un screenshot binario vinculado bloqueará esa descarga; la CLI permite export no sanitizado explícito. Un archivo sanitizado puede diferir del hash guardado del original: source-manifest conserva ambos; el paquete redacted no constituye por sí mismo un engagement recompilable con los mismos hashes.

Revert elimina el editor y gates nuevos; fichas conservan metadata aditiva, sin migración destructiva. No hay dependencias nuevas ni cambios de autorización. Laboratorio vivo, proyectos del owner e imagen `seclab-sbf:full` no se modifican.

Merge sujeto a CI aprobado del head exacto y autorización temporal hasta 2026-10-09 19:09:04 UTC; después vuelve aprobación individual.
