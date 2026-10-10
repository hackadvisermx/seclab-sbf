# Fase 178: orientación local del Copiloto sin IA

Fecha: 2026-10-10. Tarea solicitada «toma otra tarea y terminala»; V3-05c parcial. Rama `phase/178-copilot-local-guidance`, base `91a5766`, worktree `/Users/castr/tmp/t01-copilot-local-guidance`.

## Problema y resultado

El Copiloto termina con un mensaje de error si el proveedor falta, falla o agota su timeout. La siguiente decisión determinista vive en otra pestaña y no ofrece una salida en ese flujo. Una respuesta de chat tardía también puede aparecer después de cambiar proyecto. Las nuevas regresiones contra la vista de fase177 confirman ambas brechas.

La acción «Orientación local sin IA» consulta la API existente de siguiente decisión (`prompt=false`) y muestra fuente, título, motivo, job pendiente y revisión/cobertura navegable. No depende de llave/modelo, no envía contexto remoto ni añade endpoint/herramienta de ejecución. El botón está disponible mientras se espera una consulta IA. Las sugerencias de comando, cuando existen en la decisión, se muestran para revisión y uso manual; un bloqueo conserva la acción de revisar alcance o reconocimiento sin sugerir ejecutar.

Un fallo de consulta IA, respuesta vacía o contenido inválido mantiene el error visible y abre una consulta local fresca. No reintenta ni cambia proveedor/modelo. Si el recomendador local falla o devuelve una forma inválida, retira el comando/decisión previa y permite reintentar. El panel comparte la lectura y controles existentes con Metodología & Cobertura; el backend sigue reconsultando el último estado persistido después de pt-next.

Cada petición IA se liga al proyecto/tipo y a un contador de solicitud. Cambiar proyecto limpia conversación/input/espera/panel; las respuestas o errores antiguos y las respuestas tras desmontaje se descartan. No cancela una petición que el proveedor ya recibió. La orientación no declara autorización ni confirma hallazgos.

## Verificación

237 Python (`make verify`), 215 backend sobre Python instalado, 137 frontend/audit 0, 4 UI y 5 integraciones Chromium aprobados. Nueve pruebas nuevas de componente cubren ausencia de IA, navegación de revisión, timeout/error/contenido vacío o inválido, recomendador local indisponible/inválido, y éxito/error tardíos tras cambiar proyecto. Ocho de estas pruebas reproducen las brechas en la vista fase177; logs baseline conservados.

La integración real reusa la sesión temporal ya autenticada: crea solo proyecto/hosts sintéticos, confirma Vault vacío y bloqueo antes de tráfico; la orientación manual hace solo GET. La consulta IA real sin proveedor devuelve error y abre la orientación local fresca. Compara scope por bytes e historial/job antes/después, sin escrituras de esos recursos ni nuevos jobs, y abre Alcance/Cobertura. Contenedor tester/read-only/sin red. Capturas `copilot-local-no-provider.png` y `copilot-local-after-failure.png` inspeccionadas. Primer intento de fixture falló por login sin esperar y sesión extra; corregido reusando la sesión existente, suite completa aprobada.

Imagen aislada final `seclab-sbf:full-phase178`, label build-inputs `432846f67572c82d`, ID `sha256:d56bb3f82d10d9d24d4046fcae7622e1cff9e47a0264a970edbd4f222d75f7ed`, igual a los insumos del checkout. Build/smoke (incluye cuatro regresiones de manifiesto, ocho UUID CLI y 21 checkpoint), Compose host/inside y Actionlint aprobados. Logs/capturas en `tmp/phase178` del checkout principal. Gate High/Critical aprobado bajo política existente sin nuevas excepciones. SBOM CycloneDX1.7 válido, 2251 componentes, `tmp/phase178/sbom/seclab-sbf-full-phase178-432846f67572c82d.json`, SHA-256 `ce4b0fc09738135d8c9e81cf5dd9a2b3cbfd272ef6f90a8622087f3f87a276d9`. PR [#198](https://github.com/hackadvisermx/seclab-sbf/pull/198), CI `38093821641` aprobado para head `82ea2d94b4757409fb61591581395b47e3c4655a`. Merge `297ccf08cd0a90dcc38d41dc9d4bb4c35258e5fb` confirmado a las 23:07:44 UTC dentro de la autorización vigente; rama/worktree retirados y baseline sincronizado.

## Límites

La alternativa responde la siguiente decisión operativa mediante reglas existentes; no contesta preguntas libres, redacta hallazgos ni reemplaza un modelo. Hereda la cobertura heurística y disponibilidad del recomendador; no demuestra suficiencia probatoria. El flujo de chat remoto conserva su comportamiento y envío de contexto actuales; redacción/revisión de ese contexto y citas siguen pendientes. V3 global parcial.

Merges autorizados hasta 2026-10-11 16:43:06 UTC con diff revisado, gates y CI del head exacto aprobados. Sin publicar/desplegar ni modificar proyectos del owner.
