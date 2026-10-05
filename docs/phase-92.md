# Fase 92 — soporte para retos CTF Jeopardy

Soporte nativo para retos de tipo CTF Jeopardy (`subtype: "jeopardy"`): asignación de categorías técnicas (`web`, `crypto`, `pwn`, `reverse`, `forensics`, `misc`, `osint`), control de bandera única (`flag{...}`), puntuación (`points`), dificultad (`easy`, `medium`, `hard`, `insane`), estado de solución (`is_solved` / `solved`) y procedimiento de solución / writeup.

## Diseño y almacenamiento

1. **Ubicación en el Workspace**: Los retos CTF Jeopardy se mantienen dentro de `/workspace/retos/<slug>` utilizando un sub-tipo diferenciado (`subtype: "jeopardy" | "machine"`). Esto evita particionar la jerarquía del workspace en nuevas rutas raíz (como `/workspace/jeopardy/`), preservando intacta la compatibilidad con:
   - Papelera y restauración atómica (`ProjectTrash` de fase 91 con `renameat2`).
   - Ciclo de vida y aislamiento de jobs de reconocimiento (`recon-jobs.db` de fase 89).
   - Respaldos reproducibles del workspace y estado del laboratorio (`make dashboard-backup` de fase 90).
   - Regex y validaciones de seguridad de contención de rutas (`workspace_paths.py`).

2. **Estructura de `flags.json` y Sincronización**:
   - `flags.json` almacena:
     ```json
     {
       "subtype": "jeopardy",
       "category": "web",
       "points": 100,
       "difficulty": "medium",
       "solved": false,
       "flag": {
         "value": "flag{...}",
         "status": "pending",
         "captured_at": null,
         "notes": ""
       },
       "user_flag": { "value": "", "status": "pending", "captured_at": null },
       "root_flag": { "value": "", "status": "pending", "captured_at": null },
       "custom_flags": []
     }
     ```
   - Retrocompatibilidad 100%: Mantiene las llaves `user_flag`, `root_flag` y `custom_flags` intactas para máquinas tradicionales (`subtype: "machine"`).
   - Sincronización bidireccional con `target.yaml`: Al actualizar o guardar las banderas desde el dashboard o CLI, los metadatos (`category`, `subtype`, `difficulty`, `points`) se sincronizan atómicamente en `target.yaml`.

3. **Interfaz de Usuario (Frontend)**:
   - **Vista de Lista (`EngagementsView.vue`)**:
     - Selector de formato de reto al crear: CTF Jeopardy vs Máquina Boot2Root.
     - Campos condicionales para categoría técnica, puntos iniciales y dificultad.
     - Barra de sub-filtros con badges por categoría técnica (`Web`, `Crypto`, `Pwn`, `Reversing`, `Forensics`, `Misc`, `OSINT`, `Máquinas`).
     - Insignias visuales de categoría, puntaje y estado resuelto en cada tarjeta de reto.
   - **Vista de Detalle (`EngagementDetailView.vue`)**:
     - Header con badges de categoría técnica, puntaje y estado `✓ RESUELTO`.
     - Pestaña de Banderas adaptativa:
       - Si `subtype === 'jeopardy'`: Muestra tarjeta de Bandera CTF Jeopardy (input de bandera, botón toggle de captura, selectores de categoría/dificultad, campo de puntos y área de texto para notas tácticas / writeup).
       - Si `subtype === 'machine'`: Muestra las tarjetas duales tradicionales de User Flag y Root Flag.

## Validación

- `dashboard/backend/tests/test_ctf_jeopardy.py`: 5 pruebas unitarias cubriendo:
  - Creación de retos Jeopardy con campos de categoría, dificultad y puntos en `target.yaml` y `flags.json`.
  - Guardado y recuperación de banderas de retos Jeopardy con timestamps y notas.
  - Cálculo de estado resuelto (`is_solved` / `solved`).
  - Retrocompatibilidad con retos tradicionales tipo máquina.
  - Endpoints de la API REST (`POST /api/v1/engagements`, `GET /api/v1/engagements/{id}/flags`, `POST /api/v1/engagements/{id}/flags`).
- `make dashboard-tests`: 55 pruebas en total ejecutadas en el contenedor del laboratorio sin red (todas verdes).
- `make verify`: 117 pruebas Python aprobadas sin errores.
- Frontend: 7 pruebas DOM en `npm --prefix dashboard/frontend test` pasando correctamente; build de producción Vite exitoso; `npm audit` reporta 0 vulnerabilidades.
