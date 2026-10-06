# Fase 93 — soporte de modo oscuro y modo claro (Dark Mode / Light Mode)

Soporte nativo y persistente para alternar entre **Modo Oscuro** (predeterminado) y **Modo Claro** en toda la interfaz del SecLab Dashboard, preservando la identidad visual táctica "Evidence-First", la alta legibilidad de código y la retrocompatibilidad con las pruebas automatizadas del proyecto.

## Diseño y arquitectura de temas

1. **Dark-First con Anti-Flicker**:
   - Por defecto el dashboard mantiene su identidad visual táctica oscura (`#070b14`, `#0d1322`, texto `slate-100`).
   - La preferencia se persiste en `localStorage.getItem('seclab_theme')` (`'dark'` o `'light'`).
   - Un script inline en el `<head>` de `index.html` evalúa la preferencia y asigna la clase `light` o `dark` en `<html>` antes del montaje del DOM, evitando cualquier destello o parpadeo visual al cargar o recargar la página.

2. **Gestor de Tema Reactivo (`src/theme.js`)**:
   - Expone `useTheme()` con ref reactivo `theme`.
   - `toggleTheme()` alterna fluidamente entre `'dark'` y `'light'`, actualiza las clases en `document.documentElement` y almacena la elección en `localStorage`.
   - `initTheme()` sincroniza el estado al iniciar la aplicación Vue en `main.js`.

3. **Conmutación Visual en la Interfaz**:
   - **Barra de Navegación (`Navbar.vue`)**: Botón táctico situado en la cabecera junto al acceso a la terminal, con icono interactivo (`☀️` para cambiar a claro / `🌙` para oscuro) e indicación textual táctica.
   - **Pantalla de Inicio de Sesión (`App.vue`)**: Botón accesible en la esquina superior derecha para permitir al operador elegir su tema antes de autenticarse.

4. **Sistema de Estilos Adaptativos (`src/style.css`)**:
   - Se conservan las declaraciones base de `body` y `.tactical-card` para garantizar que las pruebas existentes de PostCSS/Tailwind continúen pasando al 100%.
   - Se implementa el bloque `html.light` para transformar los componentes en un entorno claro táctico y de alto contraste:
     - **Fondo general**: `#f8fafc` (slate-50).
     - **Tarjetas tácticas (`.tactical-card`)**: Fondo `#ffffff` con borde `#e2e8f0` y sombra sutil.
     - **Cabecera y dropdowns**: Fondo `#ffffff` con borde `#e2e8f0`.
     - **Campos de formulario**: Inputs, selects y textareas con fondo `#ffffff`, texto `#0f172a` y borde `#cbd5e1`.
     - **Jerarquía de texto**: Títulos `#0f172a` (slate-900), cuerpo `#1e293b` (slate-800), textos secundarios `#475569` (slate-600).
     - **Insignias e indicadores tácticos**: Ajuste de contraste para cian, esmeralda, ámbar, púrpura y rosa sobre superficies claras.
     - **Scrollbar**: Pista en `#f1f5f9` con tirador en `#cbd5e1` y hover en cian táctico.

## Validación

- `dashboard/frontend/tests/theme.test.js`: 4 pruebas unitarias cubriendo valor por defecto dark, persistencia en localStorage, alternancia con `toggleTheme()` y reactividad en `useTheme()`.
- `dashboard/frontend/tests/styles.test.js`: prueba añadida para validar la compilación de reglas `html.light` para `body` y `.tactical-card`, manteniendo verdes las pruebas previas.
- Total tests de frontend: 12 pruebas pasando exitosamente en `node --test tests/*.test.js`.
- `npm run build`: compilación de producción con Vite limpia.
- `npm run audit`: 0 vulnerabilidades.
- `make dashboard-tests`: 55 pruebas en contenedor efímero sin red aprobadas.
- `make verify`: 117 pruebas Python aprobadas.
