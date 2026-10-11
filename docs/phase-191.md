# Fase 191: metadatos YAML coherentes y gates locales de PR

Fecha: 2026-10-11 UTC. Rama `phase/191-finding-yaml-parity`, basada en fase190. V3-03s parcial.

## Problema y cambio

La ficha `status: PROVEN` seguida de YAML roto (`other: [unclosed`) se leía como confirmada en el checklist y el contexto, aunque el dashboard estricto rechazaba el frontmatter. La imagen de fase190 devuelve `PROVEN` para esa entrada. Un merge YAML o una clave anidada inválida también podía dar señales contradictorias.

Los lectores de fichas comparten ahora una validación del frontmatter completo. Rechazan YAML inválido, claves duplicadas, merges y campos principales no textuales antes de adoptar metadata o cuerpo. Checklist/contexto conservan una fila `UNINTERPRETED`, la decisión de cierre sigue pendiente y el compilador bloquea el reporte. El compilador mantiene su representación literal de referencias y motivo después de validar el YAML, para conservar compatibilidad con fichas existentes. Sin PyYAML, los lectores CLI aceptan solo escalares simples y fallan cerrados ante estructuras que no pueden interpretar.

## Runner local

`make local-pr-gates LOCAL_GATE_MODE=build LOCAL_GATE_IMAGE=seclab-sbf:full-local-pr LOCAL_GATE_BASE_IMAGE=seclab-sbf:base` construye la imagen full desde una base **ya presente** cuyo hash de insumos coincide. Omite `--pull` y no publica, inicia ni destruye el laboratorio. La variante `LOCAL_GATE_MODE=check` reutiliza una imagen full local solo si su hash coincide con el checkout. Se pueden indicar las mismas variables al ejecutar `scripts/verify/local-pr-gates.sh build|check`.

El runner encadena `make verify`, frontend unit/build/audit, backend instalado, UI Chromium, smoke, Actionlint fijado por lock, CVE High/Critical y SBOM. Los archivos de linters verificados se cachean en `tmp/local-ci-linters`; la primera ejecución puede descargar sus releases. Trivy usa la imagen y base de datos locales cuando ya están en cache. Escaneo y SBOM se ejecutan secuencialmente para no disputar el cache. El runner se detiene ante cualquier gate fallido y no hace pushes a GitHub; CI del head exacto continúa siendo requisito de merge.

## Verificación y límites

La regresión cubre YAML incompleto, merge no resuelto, estructura inválida, estado sin PyYAML y ficha válida, junto con checklist, contexto, reporte, recomendador y cierre. `make verify` pasó 246 pruebas Python y linters, también con `python3 -S` para simular ausencia de PyYAML. El runner completo pasó 242 pruebas backend instaladas, 155 frontend, 4 UI Chromium, build/audit 0, smoke instalado, Actionlint, gate CVE High/Critical y SBOM CycloneDX válido. Imagen aislada `seclab-sbf:full-phase191` (`sha256:c5b840d203c18b0dbada41a68e1a4043dd6528d996d205e4886def31a25fc876`) con insumos `fe159dd0b819ef02`; SBOM SHA-256 `6c0b6d3085a84d12bf96f0a2f0301922c42216f598b0898f98a5dc12610a2c0e`. El CI del head exacto sigue pendiente antes del merge.

No añade procedencia de hallazgos ni un parser YAML completo al modo sin PyYAML. Los documentos de skill mantienen su parser previo; la validación estricta aplica a fichas de `evidence/`. El laboratorio local permanece detenido y los volúmenes/proyectos no se modifican.
