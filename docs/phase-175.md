# Fase 175: comparar versiones de artefactos desde el historial

Fecha: 2026-10-10. Rama `phase/175-recon-artifact-compare`, worktree `/Users/castr/tmp/t01-artifact-compare`. Tercera de tres tareas adicionales; entrega parcial V3-03i/V3-02n. Base integrada `1d35106`, PR194 de fase174 fusionado con CI `38074862401` aprobado para head `9e8a138`. La preparación de UI comenzó desde fase173 y se integró fase174 antes de la construcción final.

## Problema y resultado

La fase174 conserva hashes/tamaños por job, pero la vista de historial no muestra esas referencias ni permite compararlas. La nueva regresión Vue falla con el componente de fase174: falta el botón de comparación.

El historial muestra rutas, tamaños y SHA-256 conservados de cada etapa. Distingue captura no disponible, etapa sin captura completada y resumen anterior sin huellas. El botón Comparar archivo actual abre el visor existente en modo de lectura y mantiene la referencia del job, la etapa y el run de origen declarado o desconocido.

La lectura compara hash y tamaño y comunica coincidencia, diferencia, archivo ilegible o huella actual ausente. Mantiene la referencia histórica incluso ante 404/cambio/límite; el visor muestra los bytes actuales y explica que los anteriores no se guardaron. No afirma que el contenido siga igual después de la lectura. Elegir otro archivo/carpeta/proyecto/finding retira el contexto de comparación; respuestas tardías de otro archivo/job no reemplazan la selección reciente. Reutiliza API autenticada y lector NOFOLLOW con límites existentes, sin endpoints o permisos nuevos.

## Verificación

Dos regresiones Vue prueban coincidencia/diferencia de hash o tamaño, límite/archivo ausente, legacy/captura no disponible y lecturas tardías entre jobs/proyectos. Frontend 125 pruebas aprobadas, audit 0 vulnerabilidades. `make verify`: 231 Python; backend instalado: 211; smoke aprobado con 21 regresiones de checkpoint instaladas, tester/solo lectura/sin red. Compose host/inside y Actionlint aprobados. Playwright: 4 UI y 5 integraciones Chromium aprobadas contra backend/tester temporal de la imagen final, sin red externa. La comparación comprueba un job real frente a archivo intacto, editado y eliminado, ninguna escritura API y payload histórico conservado. Capturas `job-artifact-current.png`, `job-artifact-changed.png` y `job-artifact-missing.png` inspeccionadas: contexto de job/SHA conservado y mensajes legibles.

Imagen aislada `seclab-sbf:full-phase175`, build-inputs `a706265e0e1fb204`, ID `sha256:6b577f62dd65c76bb64c5347157d56e665c7e711bf80615159978ec25c57cd78`; label coincide con fuentes. Gate High/Critical aprobado bajo política existente, sin nuevas excepciones. SBOM CycloneDX válido `tmp/phase175/sbom/seclab-sbf-full-phase175-a706265e0e1fb204.json`, 2251 componentes, SHA-256 `74b3dc708b84ca4789f2c867ffe82cf8ac2da5d8cea9618345f8d449f1060d0f`. Logs y capturas conservados en `tmp/phase175` del checkout principal. PR y CI aprobados del head exacto requeridos antes del merge.

## Límites

No guarda snapshots ni recupera bytes borrados; conserva referencias a versiones observadas. El origen de etapa no prueba productor de cada línea acumulada. No enlaza automáticamente hallazgos a jobs, firma metadata, añade resume al dashboard ni confirma vulnerabilidades. La comparación solo abre el archivo actual sin ejecutar herramientas o registrar aceptación/revisión.

Autorización de merges vigente hasta 2026-10-11 16:43:06 UTC, condicionada a gates/CI del head exacto. Sin publicar/desplegar ni modificar proyectos del owner; laboratorio healthy.
