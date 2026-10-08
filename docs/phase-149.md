# Fase 149: alcance versionado y revalidación durante reconocimiento

Fecha: 2026-10-07. Base: `efc4e01`. Rama: `phase/149-recon-scope-revalidation`. Worktree: `/Users/castr/tmp/t01-recon-scope-revision`. Primera entrega V3-01a.

## Cambios

El pipeline conserva un contrato con reglas de alcance y límites operativos normalizados; SHA-256 del JSON canónico identifica su revisión. El resumen registra contrato, revisión y el run_id suministrado por el dashboard (null para CLI sin ID). El checkpoint conserva esa revisión.

Antes de cada etapa y proceso externo se carga nuevamente el scope. Una modificación, ausencia o error bloquea nuevas acciones con recuperación concreta. El sondeo interno además revalida el host antes de DNS y el endpoint justo después de esperar el rate limit, antes de cada conexión HTTP/HTTPS. Los controles existentes de DNS/IP protegida, pinning, Host/SNI y redirects se mantienen.

Reanudar exige un checkpoint de la misma revisión. Los checkpoints anteriores sin versión requieren simular y reiniciar sin `--resume`, conservando los artefactos previos. Comentarios YAML no cambian la revisión. La simulación incluye contrato/revisión sin invocar procesos, DNS, sockets ni escribir archivos.

## Validación

- 7 pruebas nuevas: cambio después del plan, archivo borrado/inválido, límites modificados antes de proceso, revocación antes de DNS, cambio entre HTTPS/HTTP y durante rate limit, rechazo de checkpoint incompatible/legacy y simulación sin efectos con revisión reproducible.
- Regresión en baseline `efc4e01` falla; pruebas actuales pasan. Se usan mocks de DNS/conexión y targets `.test`, sin sondeos reales.
- `make verify`: 160 Python; build aislado `seclab-sbf:full-phase149`, hash `e0e63cab7fa19596`, igual a los insumos.
- Backend real, smoke, Compose `.env.example`, Actionlint y gate High/Critical: resultados finales en el PR, con política existente y sin nuevas excepciones.
- Recorder host/contenedor sin red: [medición 149](baselines/v3-phase149.json) registra revisión tanto en simulación como en checkpoint, preservando los resultados anteriores de reporte/export.

## Límites

Este cambio no introduce todavía referencia/vigencia ni permisos pasivo/activo de autorización: esa parte de V3-01 sigue pendiente. El hash identifica contenido, no una firma o historial permanente. Solo se conserva el resumen/checkpoint actual; historial completo corresponde a V3-02/03.

La revalidación no cancela solicitudes o procesos ya iniciados ni elimina la carrera entre la comprobación y apertura de conexión. Una herramienta externa en ejecución puede terminar su trabajo; la siguiente acción se bloquea. Scope Guard no intercepta terminal libre ni helpers externos al runner.

El estado operativo continúa usando `failed` con causa de bloqueo; la máquina de estados ampliada se entregará en V3-02. No se modificó el proyecto, imagen viva ni contenedor del owner. Reversión: revertir el PR; sin migración automática. Merges autorizados excepcionalmente durante esta sesión, sujetos a gates/CI.
