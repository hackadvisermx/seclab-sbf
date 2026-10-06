# Fase 97 — Visualización de IP Local y VPN en la Barra Principal y Telemetría Táctica

Implementación de visualización táctica en tiempo real para la IP Local (LAN/Docker) y la IP de la VPN en la barra de navegación principal ([`Navbar.vue`](file:///Users/castr/tmp/t01/dashboard/frontend/src/components/Navbar.vue)) y en la tarjeta de telemetría de mando ([`DashboardView.vue`](file:///Users/castr/tmp/t01/dashboard/frontend/src/views/DashboardView.vue)), con funciones de copiado rápido al portapapeles en un solo clic.

## Diagnóstico y Requisitos

1. **Ausencia de IP Local en el Servicio de Telemetría**:
   - [`dashboard/backend/app/services/telemetry.py`](file:///Users/castr/tmp/t01/dashboard/backend/app/services/telemetry.py) obtenía `hostname` vía `socket.gethostname()`, pero no calculaba ni retornaba la IP local asignada al contenedor/host.
   - En auditorías y pruebas de intrusión es fundamental conocer de forma inmediata tanto la dirección de la interfaz de red local (ej. `eth0` / red Docker para transferencias internas o proxying) como la dirección del túnel VPN activo (ej. `tun0` para `LHOST` en Metasploit, callbacks inversos o pruebas de alcance).

2. **Visualización de VPN en la Barra de Navegación**:
   - Anteriormente, el botón de VPN en la barra superior mostraba textos contextuales cortos (`THM: 10.10.x.x` o `VPN: offline`), lo cual no identificaba explícitamente "IP VPN" ni proveía una acción rápida de copiado directo desde la barra superior sin tener que entrar al dropdown o abrir una terminal.

## Solución Técnica

1. **Detección Determinista y Segura de la IP Local (`telemetry.py`)**:
   - Se añadió el método `TelemetryService.get_local_ip()` con resolución jerárquica defensiva:
     1. Parseo de `ip -4 addr show` identificando la interfaz IPv4 activa y descartando loopback (`lo`), interfaces VPN (`tun*`, `tap*`), Tailscale (`tailscale*`, `100.x`), WireGuard (`wg*`) y puentes (`docker*`, `br-*`).
     2. Fallback a `hostname -I` extrayendo la primera dirección no loopback.
     3. Fallback a socket UDP `10.255.255.255:1` (sin emitir paquetes a la red) dentro de un context manager `with socket.socket(...)` para garantizar el cierre inmediato y prevenir `ResourceWarning`.
     4. Fallback a `socket.gethostbyname(hostname)`.
     5. Fallback seguro a `"127.0.0.1"`.
   - Se incorporó `local_ip` en la respuesta estructurada de `get_system_telemetry()`.

2. **Componentes Visuales Tácticos en la Barra Principal (`Navbar.vue`)**:
   - **Chip IP Local**:
     - Badge táctico interactivo: `IP LOCAL: <ip>` (o `LOCAL: <ip>` en móviles).
     - Indicador cian y botón de copiado integrado `📋`.
     - Copiado al portapapeles con confirmación visual instantánea (`✓`) en 1 clic.
   - **Widget IP VPN**:
     - Estado explícito: `IP VPN: <ip>` cuando está conectada y `IP VPN: Desconectada` (o `Conectando…`) cuando está inactiva.
     - Badge identificador del perfil activo (`THM`, `HTB`, `CLI`) en pantallas de escritorio.
     - Botón de copiado directo `📋` en la barra junto al menú desplegable cuando el túnel está arriba.
     - Botón de copiado adicional dentro de la sección "IP Asignada" del dropdown táctico.
   - **Modo Oscuro / Claro**: Integración fluida con las clases de superficie `bg-[#0d1322]`, bordes y contrastes cian/esmeralda adaptativos.

3. **Consistencia en Vista de Mando (`DashboardView.vue`)**:
   - Se incorporó el indicador `IP Local (LAN/Docker)` en la lista de Conexiones de Red de la tarjeta "📡 Telemetría del Entorno", ubicándolo junto al estado de `VPN Activa (tun0)` y `Tailscale Nodo`.

4. **Montura de Desarrollo en Makefile**:
   - Se actualizó el objetivo `dashboard-tests` en `Makefile` para montar `-v "$(ROOT)/dashboard/backend:/usr/local/share/seclab/dashboard/backend:ro"`, permitiendo que la suite de pruebas unitarias en contenedor ejecute directamente los archivos del backend de la rama activa sin reconstrucciones pesadas de capas intermedias.

## Pruebas y Validación

- **Backend**:
  - `test_network_telemetry.py` con 4 pruebas unitarias:
    - Validación de formato IPv4 válido en `get_local_ip()`.
    - Validación de `local_ip`, `vpn`, `hostname` en `get_system_telemetry()`.
    - Validación de resiliencia y fallback cuando falla el comando de sistema `ip`.
    - Validación del endpoint HTTP autenticado `GET /api/v1/system/telemetry`.
  - `make dashboard-tests`: **65 pruebas superadas exitosamente** (4 nuevas) en 9.0s dentro de contenedor aislado sin red, con 0 advertencias.
- **Frontend**:
  - `navbar-network-ips.test.js` con 3 pruebas DOM reactivas:
    - Verificación del renderizado de `IP LOCAL:` y dirección IP recibida de la telemetría.
    - Verificación del estado desconectado `IP VPN: Desconectada`.
    - Verificación del estado conectado con IP de túnel, badge de perfil y botón de copiado.
  - `npm --prefix dashboard/frontend test`: **15 pruebas superadas exitosamente** (3 nuevas) con 0 fallos.
  - `npm --prefix dashboard/frontend run audit`: 0 vulnerabilidades.
  - `npm --prefix dashboard/frontend run build`: Compilación limpia en Vite (301ms).
- **Integridad y Seguridad**:
  - `make verify`: **117 pruebas Python aprobadas**.
  - `gitleaks dir . --no-banner --config .gitleaks.toml`: 0 leaks encontrados.
  - `git diff --check`: 0 errores de espacios en blanco.
