# Fase 182: fuentes de fichas dañadas visibles y sin estado inventado

Fecha: 2026-10-11 UTC. Segunda de dos tareas adicionales. V3-03n parcial. Rama `phase/182-finding-source-errors`, base `f7cd32e`.

## Problema y resultado

Lecturas de YAML inválido descartaban metadata y mostraban CANDIDATE; listas/scalars o CVSS no serializable causaban 500 en detalle y omitían filas del listado. Claves duplicadas aceptaban el último valor y podían sobrescribirse silenciosamente. La reproducción de seis pruebas sobre fuentes fase181 registra 18 fallos, sin errores de infraestructura (`tmp/phase182/baseline-source-errors-final.log`). La comparación usa las rutas públicas del baseline; omite únicamente las aserciones directas al nuevo helper privado, comprobadas en la imagen final.

Lista y detalle comparten lectura por descriptores. Fichas con YAML inválido, delimitador incompleto, estructura distinta de objeto, claves duplicadas, merges YAML, campos conocidos incompatibles con el esquema o CVSS no finito/fuera de 0–10 devuelven `source_error` seguro. La tarjeta muestra «Estado sin interpretar» y «Sin clasificar», sin atribuir un estado confirmado/candidato o identidad a la fuente dañada. El placeholder API usa BLOCKED/UNKNOWN con campos vacíos y no se persiste en el workspace. Texto UTF-8 estable disponible conserva cuerpo original completo y SHA-256; archivos binarios/NUL/no UTF-8, demasiado grandes o cambiados durante lectura conservan fila con error, cuerpo vacío y sin versión editable. No incluye rutas privadas ni diagnósticos del parser en el mensaje.

Fuentes válidas, Markdown sin metadata, objetos vacíos, CRLF y alias explícitos conservan las lecturas anteriores y no migran ni asignan UUID al leer. Referencias/identidad/confirmación inválidas mantienen sus indicadores específicos previos.

Guardar una ficha existente exige metadata estructural válida además de la versión; duplicados/tipos inválidos no se reparan por sobrescritura del formulario. UI bloquea edición/borrado de fuentes dañadas y la comparación de fase180 no permite adoptarlas. El visor abre el original como texto literal, con los límites/huella del lector de artefactos existente; revisar no escribe. Reparar el original en el workspace y recargar habilita la edición versionada. No requiere red/proveedor ni nuevas dependencias.

## Compatibilidad y límites

`source_error` es aditivo y nullable; GET/list conservan filas dañadas en vez de omitirlas. Clientes deben tratar una ficha con error como no interpretada, aunque conserve hash/texto. Merges YAML y claves duplicadas, incluso en metadata anidada, requieren reparación explícita (aplanar/eliminar ambigüedad). Los parsers CLI/reporte/contexto permanecen independientes y no se declara paridad global. No añade editor de metadata raw ni reparación automática, historial inmutable o autoría. El guard global de proyectos sigue rechazando enlaces simbólicos; el lector también evita seguirlos. V3 global continúa parcial.

## Verificación

Seis pruebas backend cubren matrices de YAML/estructura/duplicados/tipos/CVSS, delimitador incompleto, binario/NUL/límite 32 MiB, cambio durante lectura, enlace rechazado sin exponer fuente externa, lectura legacy/CRLF sin migración y reparación manual con nuevo guardado/UUID. Detalle/lista coinciden, no mutan fuentes y las ediciones rechazadas conservan bytes.

Tres casos Vue cubren tarjeta visible, fuente literal sin ejecutar HTML, edición/borrado bloqueados, apertura del original, comparación inválida sin perder borrador y recuperación tras reparación/recarga. Chromium instalado reutiliza sesión/proyecto sintéticos: POST 409, original intacto, visor raw, reparación explícita y guardado versionado conservando cuerpo; scope/historial intactos.

Resultados finales: 237 Python (`make verify`), 237 backend instalado, 154 frontend/audit 0, 4 UI y 5 integraciones Chromium aprobados. Capturas finales `tmp/phase182/captures/finding-source-invalid.png` y `finding-source-original.png` inspeccionadas; separación de acciones corregida y recorrido instalado repetido en la imagen definitiva. Build, smoke (cuatro manifiesto, ocho UUID y 21 checkpoint), Compose local/inside, Actionlint y gate High/Critical aprobados con política existente, sin nuevas excepciones/dependencias. Gitleaks final aprobado.

Imagen aislada `seclab-sbf:full-phase182`, insumos `62e9e2173d7223b8`, ID `sha256:f8becaf3645699af73c1295b224299e26fd7d9470d65a091e610ef9ee4d22f56`, igual al checkout; base172 comprobada `f772cb17ffe418a0`. La construcción usa el Dockerfile full real; las descargas del snapshot Ubuntu demoraron la reconstrucción final. Evidencia local `tmp/phase182/`; laboratorio healthy, sin publicar/desplegar ni modificar proyectos del owner. Cada merge requiere CI del head exacto y autorización vigente hasta 2026-10-11 16:43:06 UTC.

SBOM CycloneDX 1.7, 2251 componentes, `tmp/phase182/sbom/seclab-sbf-full-phase182-62e9e2173d7223b8.json`, SHA-256 `7535a5fb19b0d31837025bddd1a36c6cad6ca23ba250ee4e147d0d7a54834482`.

## Cierre confirmado

PR [#202](https://github.com/hackadvisermx/seclab-sbf/pull/202) fusionado en `dddac539cf70e6e8a9686536838cec26448ab8ad` el `2026-10-11T01:01:30Z`. CI [38100220882](https://github.com/hackadvisermx/seclab-sbf/actions/runs/38100220882), intento 2, aprobó los cuatro jobs para head `f03d59371a2d05b9d251087e298e440dea8d2ffa`. El primer intento no inició las pruebas frontend: Amazon ECR rechazó la descarga de Node con `toomanyrequests` (salida Docker 125). El reintento del mismo commit pasó sin cambiar ni omitir gates.

Rama local/remota y worktree de fase182 retirados; baseline sincronizado y limpio tras el merge. Las dos tareas solicitadas (fases 181 y 182) quedaron terminadas y fusionadas. La imagen aislada conserva la huella del código integrado; el laboratorio del owner seguía healthy y no se desplegó esta imagen.
