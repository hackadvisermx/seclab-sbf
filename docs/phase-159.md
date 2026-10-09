# Fase 159: validación de alcance no disponible en Copiloto

Fecha: 2026-10-08. Rama `phase/159-copilot-validation-status`, base integrada `ccc00ee`, worktree `/Users/castr/tmp/t01-copilot-validation`. Entrega parcial V3-05a.

## Problema reproducido y cambio

En la imagen instalada `full-phase158`, `_validate_copilot_scope` devolvía `[]` tanto ante scope YAML inválido como ante timeout del subprocess. El mismo valor representaba una comprobación limpia, por lo que la respuesta del Copiloto no avisaba que carecía de comprobación de alcance.

El helper distingue ahora disponibilidad y resultados. Scope/validador ausentes, timeout, fallo de inicio, salida vacía, código inesperado, JSON/schema inválidos o contradicción entre findings y código de salida producen indisponibilidad con motivo fijo. Los códigos aceptados siguen siendo 0 limpio, 1 con exclusiones y 3 solo UNKNOWN. No se envían stderr ni detalles de excepciones a la respuesta.

Ante indisponibilidad, `/copilot/chat` antepone un aviso visible que pide revisar el alcance y recuerda que el Copiloto no autoriza ni ejecuta pruebas. Conserva íntegra la sugerencia original y proveedor, modelo, latencia y usage. Las advertencias existentes para exclusiones/UNKNOWN siguen vigentes y una comprobación limpia no cambia el texto. El contenido vacío evita una comprobación innecesaria.

No cambia el schema de respuesta ni la vista productiva: el aviso usa `content`, mostrado como texto literal por el panel actual. Los clientes que consumen este campo también reciben el aviso cuando la comprobación no está disponible.

## Validación

- Reproducción en contenedor anterior, tester, raíz de solo lectura y `--network none`: scope inválido y timeout retornaban `[]`.
- 176 Python (`make verify`); 166 backend con validador real instalado para limpio/excluido/UNKNOWN/scope inválido y casos simulados de indisponibilidad/inconsistencia. TestClient y proveedor simulado verifican contenido original, metadata y ausencia de directorio recon.
- 104 frontend; audit 0. Vue verifica aviso, texto hostil literal y ausencia de llamada a reconocimiento.
- 3 UI Chromium con API simulada: login/error, tema y aviso Copiloto. Captura `copilot-validation-unavailable.png` inspeccionada; `<script>` permanece texto literal y la única escritura es `/api/v1/copilot/chat`.
- 4 integraciones Chromium existentes con backend instalado y tester temporal en contenedor sin red: autenticación, auditoría/reporte, revisión persistente y bloqueo inicial de scope. No prueban un proveedor LLM real.
- Imagen aislada `seclab-sbf:full-phase159`, hash de insumos `ae455a7444c94a02`, coincide con fuente final. Build, smoke, Compose `.env.example`, Actionlint y gate CVE High/Critical aprobados bajo política vigente; sin dependencias ni excepciones nuevas.
- Recursos/credenciales de Playwright eliminados. Laboratorio vivo, proyectos del owner e imagen `seclab-sbf:full` intactos.

```sh
make verify
make build-full BUILD_TAG=-phase159
make dashboard-tests LAB_IMAGE=full-phase159 IMAGE_SOURCE=remote
npm --prefix dashboard/frontend test
npm --prefix dashboard/frontend run audit
npm --prefix dashboard/frontend run test:e2e
npm --prefix dashboard/frontend run test:e2e:integration
make smoke-test SCAN_IMAGE=seclab-sbf:full-phase159
make compose-config ENV_FILE=.env.example LAB_IMAGE=full-phase159
go run github.com/rhysd/actionlint/cmd/actionlint@v1.7.12
make scan-image SCAN_IMAGE=seclab-sbf:full-phase159
```

## Límites y reversión

La extracción de targets sigue siendo la heurística previa; esta fase no acredita cobertura de todos los formatos IPv6/host. Una comprobación limpia no acredita autorización operativa, vigencia ni verdad de la sugerencia. El aviso conserva el consejo original para revisión humana, incluso si es incorrecto. Los errores del proveedor conservan el comportamiento previo 400/502 y su aviso de UI.

Fuentes navegables, timestamps de provenance, política/revisión del contexto remoto, fallback determinista y persistencia de conversaciones siguen pendientes de V3-05. No se añaden capacidades de ejecución, permisos ni migraciones de datos. Solo Chromium y Docker Desktop macOS comprobados. Revert restaura la omisión anterior del aviso.

PR #179 fusionado en `d0611da`, CI `37834726343` aprobado del head `2505623`. Rama/worktree retirados y baseline sincronizado. Merge bajo autorización del owner hasta 2026-10-09 19:09:04 UTC; después vuelve aprobación individual.
