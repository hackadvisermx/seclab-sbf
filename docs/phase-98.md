# Fase 98 — Cierre y Descarte Rápido del Panel Táctico de VPN (Botón ✕, Backdrop y Tecla Escape)

Resolución del bloqueo de interfaz y falta de controles de descarte en el panel desplegable de la VPN táctica en la barra de navegación principal ([`Navbar.vue`](file:///Users/castr/tmp/t01/dashboard/frontend/src/components/Navbar.vue)).

## Diagnóstico del Problema

- Al hacer clic en el botón de la VPN en la barra de navegación superior, se abre el panel flotante de gestión de túneles y credenciales.
- Sin embargo, el componente carecía de:
  1. Un botón visible de cierre (`✕`) en la cabecera del cuadro.
  2. Detección de la tecla `Escape` (`Esc`) para descarte rápido con teclado.
  3. Un fondo interactivo (*backdrop* / *click outside*) para cerrar el cuadro al hacer clic en cualquier área externa de la pantalla.
  4. Un botón de cierre accesible en el pie del panel.
- Como resultado, el cuadro flotante permanecía bloqueando la vista de la barra y de la página hasta que el usuario volvía a pulsar con precisión el botón disparador.

## Solución Técnica

1. **Botón de Cierre en Cabecera (`Navbar.vue`)**:
   - Se añadió un botón táctico `✕` con `aria-label="Cerrar panel VPN"` y tooltip `Cerrar panel VPN (Esc)` en la barra de estado superior del cuadro flotante.

2. **Cierre al Hacer Clic Fuera (*Backdrop Overlay*)**:
   - Se incorporó un backdrop semitransparente (`fixed inset-0 z-40 bg-black/20`) que se activa únicamente mientras `vpnDropdownOpen` es `true`.
   - Cualquier clic fuera del menú flotante dispara `@click="vpnDropdownOpen = false"`.

3. **Control por Teclado (`Escape`)**:
   - Se implementó `handleGlobalKeydown(e)` escuchando el evento `keydown` en `window`.
   - Si `e.key === 'Escape'` y el panel está abierto, se cierra de inmediato.
   - Registro limpio en `onMounted` y remoción en `onUnmounted` para prevenir fugas de memoria.

4. **Acción de Cierre en Pie de Página**:
   - En el pie del cuadro táctico se añadió el botón de texto `Cerrar (Esc)` junto a las referencias de comandos CLI (`vpntry`, `vpnhtb`, `vpncli`).

5. **Alineación Geométrica Segura**:
   - Se añadió la clase `top-full mt-1.5` al contenedor del menú para fijar su anclaje justo debajo del chip de la barra de navegación.

## Validación y Cobertura

- **Frontend Tests**: 18 pruebas superadas (+3 nuevas en [`navbar-network-ips.test.js`](file:///Users/castr/tmp/t01/dashboard/frontend/tests/navbar-network-ips.test.js)):
  - Cierre mediante botón `✕`.
  - Cierre mediante clic en backdrop exterior.
  - Cierre mediante pulsación de tecla `Escape`.
- **npm audit**: 0 vulnerabilidades.
- **npm run build**: Compilación limpia en Vite (330ms).
- **Backend Tests (`make dashboard-tests`)**: 65 pruebas superadas.
- **Regresión Completa (`make verify`)**: 117 pruebas aprobadas.
- **Seguridad (`gitleaks`)**: 0 leaks encontrados.
