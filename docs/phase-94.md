# Fase 94 — Multi-Tab Handoff y Desconexión Automática de Terminal Integrada

Resolución del bloqueo de sesiones concurrentes en la terminal web (`ttyd`) y optimización de la experiencia multi-pestaña entre el dashboard integrado de SecLab y pestañas externas de navegador.

## Diagnóstico del problema raíz

1. **Parámetro `--max-clients` (`-m 1`) en `ttyd`**:
   - [`scripts/entrypoint/ttyd-as-tester.sh`](file:///Users/castr/tmp/t01/scripts/entrypoint/ttyd-as-tester.sh) ejecutaba `ttyd` con la opción `-m 1`.
   - Cuando el operador visitaba la vista `/terminal` del dashboard, el iframe embebido abría un socket WebSocket hacia `:7681`.
   - Al intentar abrir la terminal en una nueva pestaña (haciendo clic en "Nueva Pestaña" o en el acceso rápido de la barra de navegación), `ttyd` rechazaba la nueva conexión hasta que la primera pestaña o el iframe fuese cerrado.

2. **Deseo de handoff inteligente y ergonomía táctica**:
   - Además de permitir múltiples conexiones en el servidor (`ttyd` + `tmux` adjuntan múltiples clientes a la misma sesión compartida `pentest-lab`), el operador requiere que, al abrir la terminal en una pestaña independiente para trabajar con pantalla completa, la terminal integrada no compita ni genere problemas de redimensionamiento de PTY (`resize` de tmux).
   - Si se abre la pestaña externa, la vista integrada debe pausarse automáticamente y ofrecer un botón claro de reconexión cuando se desee volver al frame integrado.

## Solución implementada

1. **Soporte de múltiples clientes en `ttyd`**:
   - Se removió el parámetro `-m 1` en `scripts/entrypoint/ttyd-as-tester.sh`.
   - `ttyd` opera con su comportamiento estándar (sin límite artificial de 1 cliente), permitiendo que el túnel de tmux gestione los clientes concurrentes.

2. **Gestión de ciclo de vida en `TerminalView.vue`**:
   - **Estado de conexión (`isConnected`)**: Control reactivo del renderizado del iframe `ttyd`.
   - **Handoff al abrir nueva pestaña**: El botón "↗ Nueva Pestaña" abre la URL en una nueva pestaña del navegador y automáticamente desconecta el iframe integrado (`isConnected = false`), mostrando un mensaje táctico explicativo.
   - **Tarjeta táctica de espera (Standby UI)**: Cuando la terminal integrada está desconectada, se muestra una tarjeta con estado táctico, motivo de desconexión y botones de acción rápida:
     - `🔄 Reconectar Terminal Integrada`: Reactiva el iframe de inmediato.
     - `↗ Ir a Pestaña Externa (:7681)`: Enlace directo a la pestaña completa.
   - **Controles manuales en la cabecera**: Se agregaron botones tácticos para "⏹ Desconectar" y "▶ Conectar Integrada", permitiendo pausar la conexión bajo demanda.
   - **Liberación de recursos al desmontar (`onUnmounted`)**: Al navegar a otra vista del dashboard, el iframe se desmonta y desconecta de inmediato para no retener sockets innecesarios.

3. **Comunicación entre componentes (`Navbar.vue` <-> `TerminalView.vue`)**:
   - El enlace "Terminal Web" en la barra de navegación dispara el evento de ventana `seclab-terminal-tab-opened`.
   - `TerminalView.vue` escucha dicho evento y, si está activo en segundo plano, pasa a estado pausado para ceder el control a la pestaña externa.

## Validación

- `npm --prefix dashboard/frontend test`: 12 pruebas pasando exitosamente.
- `npm --prefix dashboard/frontend run build`: Compilación de producción con Vite sin errores.
- `npm --prefix dashboard/frontend run audit`: 0 vulnerabilidades.
- `make verify`: 117 pruebas Python aprobadas.
- `make dashboard-tests`: 55 pruebas en contenedor efímero sin red aprobadas.
