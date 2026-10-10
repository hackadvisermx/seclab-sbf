# Fase 173: origen de etapas recuperadas

Fecha: 2026-10-10. Rama `phase/173-recon-resume-origin`, base `8c65194`, worktree `/Users/castr/tmp/t01-resume-origin`. Primera de tres tareas adicionales solicitadas; entrega parcial V3-02l.

## Problema y resultado

En full-phase172, una etapa subdomains terminada por run A y recuperada por run B aparece en `stages_executed` de B, sin origen. La reproducción instalada se hizo con IP sintética, mocks, tester/read-only/network-none. La nueva regresión falla allí y pasa en el checkout corregido.

Cada etapa conserva `execution` (current/recovered) y `origin_run_id`. Al recuperar una etapa se conserva el ID que tenía al terminar; otras reanudaciones no lo sustituyen. `stages_executed` enumera intentos del run actual, incluido el que falló; `stages_recovered` enumera el prefijo recuperado. Un intento bloqueado no implica tráfico. CLI sin ID externo genera un UUID por run; IDs externos no canónicos no se incorporan al nuevo campo de origen. El ID del job del dashboard sigue siendo el asignado por su worker.

Checkpoint v2 de fase172 sin esos campos sigue aceptándose cuando sus hashes/alcance son válidos: la etapa queda recovered con origen desconocido. Campos nuevos parciales/inválidos bloquean antes de acciones/escrituras. No se inventa procedencia para checkpoints históricos. CLI legible también muestra etapas recuperadas y origen registrado o desconocido.

El historial admite resumen v2 con los dos campos y conserva v1 legible. La extracción y lectura validan ID actual, formato del origen, orden/prefijo, estado y listas ejecutadas/recuperadas; una etapa recuperada no se atribuye al job actual ni puede ser fallida. No se copian URLs, comandos, errores ni metadata libre. La tabla existente mantiene finalización transaccional y resultados por run; no cambia columnas ni requiere migración. UI marca recuperada/origen, completada o intentada en este job, y origen no registrado para resúmenes anteriores.

## Verificación

Seis nuevas pruebas de pipeline cubren A→B, A→B→C con fallos intermedios, CLI sin ID externo, compatibilidad de checkpoint anterior, metadata malformada y etapa manual/ID externo inválido. La suite instalada de smoke pasa a 18 casos. Tres pruebas backend nuevas cubren persistencia/reapertura y job posterior legacy, origen inválido/inconsistente y bloqueo tras recuperación. Vue cubre origen conocido/desconocido y fallback v1. Chromium UI usa API simulada y comprueba etiquetas sin escrituras; integración real comprueba que el resumen del pipeline instalado v2 y su origen actual llegan al historial/API/UI. Capturas y logs en `tmp/phase173` del checkout principal.

Gates finales aprobados: `make verify` (228 Python y linters), 208 backend, 123 frontend/audit 0, 18 regresiones instaladas en smoke, 4 UI y 5 integraciones Chromium. Capturas de origen recuperado simulado y resultados reales inspeccionadas. Compose, Compose VPN y Actionlint aprobados; gate High/Critical aprobado bajo política existente, sin nuevas excepciones ni dependencias.

La construcción final reutiliza `seclab-sbf:base-phase172` después de comparar su etiqueta con `python3 scripts/build-inputs.py base`, mediante el mismo comando buildx de full con hash del checkout y tag aislado full-phase173. Mantiene bytes/pins de base. Imagen `seclab-sbf:full-phase173`, ID `sha256:464ebc9163bb8526bcc4000e1c52c2c426905c025fce1ad01b6e262c15ecbe78`, hash `d1e89779873bf2fd`. SBOM CycloneDX válido `tmp/phase173/sbom/seclab-sbf-full-phase173-d1e89779873bf2fd.json`, SHA-256 `be8dad53a4331f7db35af2a10e4475205d819362c7d06c5437d0b25b89895d3a`. PR y CI del head exacto requeridos antes de merge.

## Límites

El origen identifica un run declarado localmente, sin firmar ni demostrar productor/autor. No vincula cada línea del output al run, añade snapshots, migra IDs históricos ni registra jobs CLI en SQLite del dashboard. La API/UI del dashboard no añade un modo de ejecución resume; las pruebas visuales de recovered se alimentan de metadata validable simulada y las reanudaciones reales se prueban con el pipeline instalado. Los conteos de workspace siguen pudiendo incluir archivos previos. No completa timeline ni V3-02/03. No cambia alcance, permisos, límites de herramientas ni gates de reporte.

Fase172/PR192 fusionada en `8c65194`, CI `38071743565` aprobado para head `adacb2a`; ramas/worktree retirados y baseline sincronizado. Autorización de merges vigente hasta 2026-10-11 16:43:06 UTC, condicionada a gates/CI del head exacto. Laboratorio existente healthy tras reparación autorizada de fase172; sin publicación/despliegue ni modificación de proyectos.
