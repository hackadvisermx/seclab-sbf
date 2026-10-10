# Fase 174: versiones de artefactos conservadas por job

Fecha: 2026-10-10. Rama `phase/174-recon-artifact-history`, base `d3d5ba9`, worktree `/Users/castr/tmp/t01-artifact-history`. Segunda de tres tareas adicionales; entrega parcial V3-03h/V3-02m.

## Problema y resultado

La reproducción instalada en full-phase173 confirma que el checkpoint tiene referencias path/SHA-256/tamaño pero summary.json no las conserva. Al desaparecer el checkpoint tras completar o al ejecutar otro job, el historial solo conserva conteos y origen de etapas.

El pipeline incorpora `stage_artifacts` al resumen: inventario fijo de 17 outputs, compartido con el validador backend. Las etapas completadas conservan hashes/tamaños obtenidos al completar, y las recuperadas conservan las referencias verificadas del checkpoint. Una etapa posterior que cambie un archivo o falle no sustituye esa versión registrada. No se declara versión completada para etapas fallidas o simulaciones.

Las etapas manuales también intentan registrar versiones; si los archivos faltan, cambian durante la lectura, son enlaces/no regulares o exceden el presupuesto, la captura queda `unavailable` sin referencias ni detalles privados. Ese fallo de metadata no cambia su resultado funcional anterior. La cadena all conserva el gate estricto de fase172, requerido para checkpoint/resume.

El resumen normalizado v3 conserva `artifact_capture` por etapa y origen de fase173 en la tabla SQLite existente, con finalización transaccional y límite existente de 16 KiB. Valida campos exactos, inventario/orden, SHA-256, tamaño entero y presupuesto agregado de 32 MiB; capturas de etapas fallidas, inventarios extra/incompletos y rutas arbitrarias se rechazan. Una captura unavailable solo corresponde a etapa manual actual. V1/v2 permanecen legibles sin inventar huellas antiguas. No añade columnas, migraciones ni dependencias.

## Verificación

Tres regresiones nuevas del pipeline cubren cambio después de completar/fallo posterior, etapa manual/captura no disponible y reanudación/simulación. La regresión instalada falla sobre full-phase173 por ausencia de stage_artifacts. Tres pruebas backend cubren SQLite/reapertura/backup/job posterior legacy, referencias inválidas/inventarios/etapas fallidas y presupuesto/origen recuperado. Integración Chromium real compara la huella registrada con los bytes del output de sondeo instalado, modifica ese archivo y comprueba que el historial conserva su referencia original incluso tras otro job; el job bloqueado no reclama artefactos completados. Los conteos de URLs del workspace se mantienen separados del inventario propio del sondeo. Pruebas sin tráfico a objetivos; fixtures desechables tester/network-none.

`make verify`: 231 Python y linters; 211 backend instalado, 123 frontend/audit 0, 21 regresiones instaladas en smoke, 4 UI y 5 integraciones Chromium aprobados; captura final inspeccionada. Compose/VPN y Actionlint aprobados. Imagen aislada `seclab-sbf:full-phase174`, ID `sha256:6151ec1fd37f16c5a2915da4e3d9537ce74f5e5c45dc9b830b6d00934ce43c9d`, hash `035901f3c7a10554`, igual al checkout; base172 reutilizada tras validar hash de insumos. Gate High/Critical aprobado bajo política existente sin nuevas excepciones. SBOM CycloneDX válido `tmp/phase174/sbom/seclab-sbf-full-phase174-035901f3c7a10554.json`, SHA-256 `cab5c8646da2ff36bb5c34e16ce1e9787a24ba4513e55aa97f246f0294dd688e`. PR y CI del head exacto requeridos antes de merge. Evidencia en `tmp/phase174` del checkout principal.

## Límites

Conserva referencias a bytes observados, no los bytes anteriores. Outputs acumulados pueden contener líneas de otras ejecuciones: el ID de origen de la etapa no demuestra productor de cada línea ni autor. Metadata local sin firma. No incorpora jobs CLI al historial del dashboard, habilita resume en API/UI ni confirma hallazgos. Consulta visual/comparación de versiones históricas pendiente de la tercera tarea.

Fase173/PR193 fusionada en d3d5ba9, CI 38073414333 aprobado para head 83c8293; rama/worktree retirados y primera tarea adicional completa. Autorización de merges vigente hasta 2026-10-11 16:43:06 UTC condicionada a gates/CI del head exacto. Laboratorio healthy; sin publicar/desplegar ni modificar proyectos.

Para mantener espacio durante gates se retiraron 58 etiquetas temporales full/base de fases143–171 y full-phase172 ya cerrada, además de exports binarios regenerables de fase172. Se conservaron logs, hashes, metadata y SBOM; full/base del owner, imagen de regresión phase173 y base172 permanecen. El host recuperó aproximadamente 29 GiB libres y el laboratorio siguió healthy. No se borraron proyectos ni volúmenes.
