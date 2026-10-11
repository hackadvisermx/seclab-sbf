# Fase 185: fuentes ambiguas visibles en contexto de agente

Fecha: 2026-10-11 UTC. Rama `phase/185-context-finding-source`, base `d820ee2`. V3-03p/V3-05 parcial.

## Problema y cambio

`pt-agent-context` consumía la última aparición de una clave de frontmatter como `asset`, `severity`, `title` o `id`, aun si la fuente tenía declaraciones contradictorias. Una ficha con bytes no UTF-8 se omitía sin aviso. El dashboard de fase182 y el compilador de fase184 ya rechazan las fuentes ambiguas en sus propios recorridos. La regresión instalada en la imagen de fase184 reproduce cinco casos de clave repetida y uno de lectura ilegible.

El contexto ahora rechaza una segunda clave literal en su parser plano y conserva una fila por fuente dañada con estado `UNINTERPRETED`, severidad `UNKNOWN`, activo `N/A`, nombre de archivo y código fijo de error. No adopta metadata ni cuerpo de esa fuente, indica el original en Markdown y cuenta las fuentes sin interpretar por separado. La preparación para cierre que expone el contexto queda bloqueada mientras exista una. El archivo original permanece intacto. La lectura de fichas válidas y el contrato de salida previa se conservan.

## Verificación y límites

Dos pruebas nuevas cubren metadata repetida, archivo ilegible, JSON/Markdown, conteos, bloqueo de cierre y bytes originales. La prueba instalada corre como `tester` en contenedor de solo lectura y sin red y queda integrada en smoke. `make verify` aprobó 240 pruebas Python y linters; Compose y Actionlint, smoke y 237 backend instaladas aprobaron. La imagen aislada `seclab-sbf:full-phase185` (`sha256:54764c2c6fcf23dd53a1c84d828d77c2a59d4a3a6e162482c40764f1fe6b4516`) coincide con los insumos `eab66f97a0e44326`. Gate High/Critical aprobado sin nuevas excepciones; SBOM CycloneDX 1.7 válido, 2251 componentes y SHA-256 `0f3999d30fe9d8f54eff85fca278885c7758ff4ccb4566dce7a239794209b916`. CI del head exacto requerido antes del merge.

El detector cubre claves literales repetidas reconocidas por el parser simple. No valida todo YAML ni garantiza paridad de sintaxis con el dashboard. El checklist instalado aún interpreta otras claves con su parser propio; esa compuerta se aborda por separado. No agrega procedencia job–finding, fuentes citadas para IA ni filtrado del resto del contexto remoto. Laboratorio y proyectos del owner intactos.
