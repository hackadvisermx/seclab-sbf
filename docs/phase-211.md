# Fase 211: Panel interactivo y runner de Playbooks en el Dashboard (PlaybooksTab)

Fecha: 2026-10-12 UTC. Rama `phase/211-playbook-ui`, base `8ee4425`. V3-04c parcial.

## Problema y cambio

En las Fases 205 (V3-04a) y 207 (V3-04b) se implementaron el esquema determinista, los playbooks semilla de reconocimiento/puertos, y el runner seguro con interpolación higienizada y compuertas de alcance (`scripts/seclab_playbook.py` y endpoints backend `/api/v1/playbooks`). Sin embargo, el operador en el dashboard aún no disponía de un panel visual para seleccionar playbooks, configurar parámetros dinámicos, ejecutar simulaciones (dry-run) seguras e inspeccionar resultados paso a paso.

En esta fase:
1. Cliente API Frontend (`dashboard/frontend/src/api.js`):
   - Se agregan métodos dedicados para interactuar con el subsistema de automatización controlada:
     - `api.getPlaybooks(engagementId, type)`
     - `api.getPlaybook(id, engagementId, type)`
     - `api.validatePlaybook(playbook, engagementId, type)`
     - `api.runPlaybook(id, payload)`
2. Pestaña e interfaz táctica (`dashboard/frontend/src/views/EngagementDetailView.vue`):
   - Se incorpora la pestaña «📖 Playbooks» (`activeTab === 'playbooks'`) en el menú táctico tanto para engagements como para retos.
   - Selector desplegable reactivo para explorar los playbooks disponibles (`web_recon`, `port_discovery` y playbooks de proyecto).
   - Ficha de metadatos del playbook: título, descripción, autor, versión, categoría e insignia de validez de esquema (`SCHEMA VÁLIDO` / `SCHEMA INVÁLIDO`).
   - Evaluación en vivo del contrato de alcance (Scope Guard): advierte si el playbook contiene pasos de interacción activa no permitidos por `target.yaml`.
   - Formulario reactivo para configurar parámetros dinámicos del playbook (con valores predeterminados y sugerencia automática de dominio en alcance).
   - Barra de control:
     - Selector de límite de pasos (`max_steps`).
     - Conmutador de modo simulación (`dry_run`).
     - Botón «▶️ Simular (Dry-Run)» para previsualizar comandos sin riesgo operativo ni interacción real.
     - Botón «⚡ Ejecutar Playbook» para disparo acotado.
   - Resumen interactivo de corrida: estado global (`SIMULATED`, `COMPLETED`, `BLOCKED`, `STOPPED`), indicador de modo dry-run y conteo de pasos ejecutados vs totales.
   - Lista visual de pasos del flujo con tarjetas detalladas:
     - Título e identificador del paso.
     - Insignia de tipo de interacción: `passive` (azul), `active_low` (verde), `active_high` (ámbar).
     - Insignia de estado de paso: `SIMULATED`, `COMPLETED`/`SUCCESS`, `BLOCKED`, `STOPPED`, `FAILED`, `TIMEOUT`.
     - Bloque de comando (interpolado o plantilla).
     - Detalle expandible con salida/resultado o alerta de motivo de bloqueo.
3. Pruebas y verificación:
   - Nueva suite en Node test runner: `dashboard/frontend/tests/playbook-tab.test.js` con pruebas de:
     - Carga de catálogo y renderizado de tarjetas y pasos con insignias de interacción.
     - Simulación dry-run con parámetros interpolados y visualización de resultados `SIMULATED`.
     - Manejo estricto de bloqueos por contrato de alcance y alertas pedagógicas.
   - 165 pruebas frontend en `npm test` aprobadas con 0 fallos.
   - Compilación exitosa de producción con Vite (`npm run build`).

## Verificación y límites

- 165 pruebas frontend unitarias y de integración pasando.
- Vite build validado sin advertencias críticas ni errores.
- 293 pruebas Python en host previamente verificadas.
- V3-04c parcial: provee la superficie interactiva completa en frontend para simular y ejecutar playbooks deterministas; edición directa en caliente de playbooks YAML desde UI continúa planificada en iteraciones posteriores.
