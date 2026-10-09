# Fase 169: siguiente decisión de reconocimiento compartida con CLI

Fecha: 2026-10-09. Rama `phase/169-cli-recon-decision`, base `8be8735`, worktree `/Users/castr/tmp/t01-cli-job-decision`. V3-02j parcial.

## Problema reproducido

Con un job persistido failed y permisos declarados, pt-next seguía la heurística de archivos, recomendaba pt-recon y generaba un prompt de ejecución. La regresión instalada reproduce lo mismo contra full-phase168 como tester, raíz de solo lectura y sin red. El dashboard ya priorizaba ese fallo; CLI y API ofrecían decisiones diferentes. Evidencia en `tmp/phase169/reproduction.json` y `installed-reproduction.log` del checkout principal.

## Cambio

- `seclab_recon_state.py` comparte decisión, estados terminales y huella de revisión con backend. La serialización usada para revisiones existentes se conserva; no cambia su significado o política de aceptación.
- La CLI consulta únicamente el job actual de su proyecto/tipo dentro del workspace configurado. SQLite se abre mode=ro/query_only, en transacción de lectura, sin crear DB ni migrar tablas. Soporta la tabla legacy de nueve columnas y tablas adicionales cuando existen. Lectura de plan/resumen acotada, espera de bloqueo máximo de un segundo, rechazo de DB/directorio inmediato/journals enlazados e identidad de archivo comprobada para jobs leídos. Se admite el alias de sistema /var de macOS sin aceptar un directorio de datos directamente enlazado.
- Running/cancelling/bloqueo/fallo/cancelación/interrupción ofrecen una acción local en el dashboard con run_id/estado/etapa. La revisión vigente registrada en fase168 permite preparar otro plan. `command` permanece null, prompt disponible false; --prompt no genera instrucciones de ejecución, --all no añade otros pasos ejecutables y --copy no invoca el portapapeles para esas decisiones.
- Metadata cambiada invalida la revisión mediante la misma huella. DB bloqueada, ilegible, schema inválido, estado desconocido, timestamps incompletos o filas ambiguas conducen a revisar el estado, con mensaje genérico sin paths/motivos privados.
- La CLI reconsulta antes de presentar el resultado de la heurística; un job iniciado mientras se calculaba el checklist retira comando/prompt. Runner transmite las rutas configuradas del dashboard al subprocess para leer el mismo proyecto/estado.
- Si no existe DB/job, o el directorio es independiente del workspace configurado, se conserva el comportamiento previo. Completed/simulated sin decisión de preparar otro plan mantienen la heurística anterior. No se marcan etapas completadas ni se confirma evidencia.

## Validación

`make verify`: 193 Python; `make dashboard-tests LAB_IMAGE=full-phase169 IMAGE_SOURCE=remote`: 204 backend. Regresión instalada integrada en smoke, Compose con .env.example, Actionlint v1.7.12 y gate High/Critical aprobados bajo política existente sin nuevas excepciones. Cinco integraciones Chromium aprobadas con backend real/tester temporal/sin red, incluyendo el fixture predeterminado actualizado a phase169. No cambia la UI ni añade dependencias.

Imagen aislada `seclab-sbf:full-phase169`, build-inputs `1c1d3c64133eadc6`, image_id `sha256:54beccd7065ff6cdfa598302c8fafb456910e2ee19242dd8178c69d959313288`. Hash medido igual a etiqueta de imagen. SBOM CycloneDX válido ligado al hash final, SHA-256 `ba20412b4cc72606c87bfe41fe24e1d9b19783a1b4dfad416234aa81e50d29d6`. CI del head exacto requerido antes del merge.

Las siete pruebas CLI cubren fallo legacy, ausencia de DB, aislamiento por tipo/directorio, estado corrupto/ambiguo/terminal incompleto, enlaces, DB bloqueada, revisión vigente/metadata cambiada y job iniciado durante heurística. Comprueban JSON, --prompt/--all/--copy, mensaje sanitizado y ausencia de modificación/creación del estado. La prueba backend usa ReconJobStore real y subprocess CLI para todos los estados, revisiones y job nuevo. El smoke instalado compara decisión API/CLI, preserva bytes de DB/target.yaml y ejecuta como tester/read-only/network-none. Logs y reproducción conservados en `tmp/phase169` del checkout principal.

## Límites y operación

La lectura es una observación del estado y puede quedar obsoleta después; pt-next no ejecuta la recomendación ni es una frontera de ejecución. El lanzamiento conserva sus gates de scope/permisos. No lee historial completo ni atribuye archivos vivos a un job, no modifica el esquema ni firma revisiones. pt-context y la cobertura mantienen su contrato previo; timeline/procedencia finding/job siguen pendientes. SQLite sigue usando su mecanismo habitual de coordinación de lectores; no se promete inmutabilidad física de sidecars durante actividad concurrente. V3-02 permanece parcial.

Laboratorio vivo, proyectos del owner, etiqueta full y publicación/despliegue intactos. Cada entrega exige PR hacia bootstrap/baseline, revisión de diff, gates locales y CI del head exacto. Autorización de merge vigente hasta 2026-10-10 14:56 UTC.
