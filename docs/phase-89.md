# Fase 89: persistencia y ciclo de vida de jobs de reconocimiento

Esta fase dota al dashboard táctico de persistencia de estado para los procesos de reconocimiento y control de ciclo de vida con cancelación controlada.

## Cambios Principales

1. **Persistencia en SQLite**:
   - `dashboard/backend/app/core/recon_jobs.py` guarda el último job por tipo (`engagement` / `reto`) e identificador en `SECLAB_DATA_DIR/recon-jobs.db` dentro del volumen persistente `lab-state`.
   - Modos y estados: almacena `run_id`, `status` (`running`, `cancelling`, `completed`, `failed`, `simulated`, `interrupted`, `cancelled`), `stage`, `dry_run`, `started_at`, `finished_at` y mensaje de error.

2. **Exclusión Mutua y Recuperación ante Reinicios**:
   - El ciclo de vida de la aplicación (`lifespan`) obtiene un bloqueo exclusivo de `recon-jobs.db.lock`.
   - En el arranque (`startup`), las tareas pendientes en estado `running` o `cancelling` se marcan automáticamente como `interrupted` (sin intentar relanzar procesos antiguos ni reutilizar PIDs persistidos).
   - Los procesos hijos heredan el descriptor de bloqueo para evitar que instancias concurrentes del dashboard tomen el control del mismo estado.

3. **Cancelación Segura**:
   - `POST /api/v1/recon/{id}/cancel?type=engagement|reto` valida la sesión autenticada.
   - Pasa el estado a `cancelling` y envía señal `SIGTERM` al grupo de procesos (con escalamiento a `SIGKILL` tras 2 segundos si el proceso no responde).
   - Al finalizar, el estado se actualiza a `cancelled`.
   - Se bloquea el borrado del proyecto o el lanzamiento de un nuevo job mientras el estado sea `running` o `cancelling`.

4. **Integración en Frontend**:
   - Botón de **Cancelar reconocimiento** visible cuando un pipeline está en ejecución o cancelándose.
   - Etiquetas de estado ampliadas: `EJECUTANDO`, `CANCELANDO`, `COMPLETADO`, `FALLIDO`, `SIMULADO`, `INTERRUMPIDO`, `CANCELADO`.
   - Avisos informativos claros sobre el estado de los artefactos.

## Verificación

- `make dashboard-tests`: 37 pruebas en contenedor sin red (incluye 12 pruebas de ciclo de vida en `test_recon_lifecycle.py` y la integración instalada).
- `make verify`: 105 pruebas unitarias de seguridad y validaciones de repositorio.
- Frontend: 4 pruebas de renderizado/estilos (`npm test`), build de producción (`npm run build`) y auditoría de dependencias (`npm audit` con 0 vulnerabilidades).
