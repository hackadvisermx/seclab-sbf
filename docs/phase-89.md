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

## Estado confirmado después del relevo

PR [#109](https://github.com/hackadvisermx/seclab-sbf/pull/109) mergeado el 2026-10-05; checkout en baseline `e2da77e`. CI del PR y [baseline](https://github.com/hackadvisermx/seclab-sbf/actions/runs/37380267562) successful. El relevo siguiente conserva el estado previo al merge como antecedente. La aceptación visual del despliegue no se confirmó en esta sesión. La continuidad de respaldo/restauración se desarrolla en `docs/phase-90.md`.

## Relevo de sesión — 2026-10-05 (anterior al merge)

El punto de partida para retomar es la rama `phase/89-recon-job-lifecycle`, commit `912efd7`, con seguimiento remoto `origin/phase/89-recon-job-lifecycle`. El working tree estaba limpio antes de añadir esta nota. Otra sesión realizó avances después de la implementación inicial; las validaciones instaladas arriba son las registradas por esa sesión en la documentación vigente. Los logs y el parche antiguos de `/tmp/seclab-phase89*` corresponden al estado anterior y no sustituyen el checkout actual.

En esta sesión había restricciones de escritura en `.git`, red y acceso a Docker. Esas restricciones pertenecen a la sesión y no prueban un fallo del repositorio o de las credenciales de GitHub. No se requiere rehacer el código ni aplicar el parche antiguo.

Para cerrar la fase 89:

1. Revisar `git status`, rama y HEAD antes de editar; conservar los avances de otras sesiones.
2. Confirmar si existe el PR de esta rama hacia `bootstrap/baseline`; registrar su URL y estado. Si falta, abrirlo con alcance, validaciones, riesgos y limitaciones. No duplicarlo ni hacer push directo a baseline.
3. Confirmar evidencia de `make build-full`, `make dashboard-tests`, `make verify`, `make scan-image` y SBOM de la imagen local correspondiente a estos insumos. Las pruebas registradas no equivalen a un resultado nuevo de CVEs; falta confirmar aquí el digest y el gate de escaneo.
4. Validar desde el dashboard instalado la cancelación de un fixture local, el bloqueo de nueva ejecución/borrado durante la cancelación y la persistencia/recuperación al reiniciar. Confirmar el despliegue de la imagen validada y su aceptación visual. Usar fixtures, sin nuevas consultas a objetivos externos.
5. Revisar CI y obtener aprobación del owner antes de mergear. La construcción sigue siendo local; Docker Hub es el destino de publicación, sin GHCR ni build de imagen en CI.

La última propuesta de mejora continúa en este orden, sin iniciar otra implementación durante este cierre de sesión:

- **Fase 90 propuesta: respaldo y restauración del dashboard.** Incluir una copia consistente de las bases SQLite y la clave de la bóveda, junto con el workspace; proteger secretos y permisos, verificar integridad y probar restauración con fixtures. El respaldo actual del workspace no demuestra por sí solo recuperación del estado en `lab-state`.
- **Fase 91 propuesta: recuperación de proyectos eliminados.** Diseñar papelera y restauración desde el dashboard antes de sustituir el borrado definitivo; mantener validación de rutas, aislamiento por tipo y bloqueo durante reconocimiento activo.

Ambas propuestas requieren revisar primero las fuentes y el alcance concreto. La fase 89 conserva solo el último job por proyecto; no es un historial completo de ejecuciones. No se realizaron nuevas pruebas de reconocimiento sobre UAZ durante esta fase.
