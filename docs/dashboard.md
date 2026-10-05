# Dashboard Táctico & API Vault de SecLab-SBF

Estación de control web unificada para la gestión operativa y técnica de auditorías de ciberseguridad ética (Bug Bounty, Retos CTF en TryHackMe / HackTheBox y Pruebas de Penetración autorizadas).

---

## 1. Principios de Diseño y Seguridad

1. **Filesystem-First**:
   El sistema de archivos `/workspace` (`target.yaml`, `evidence/*.md`, `terminal.log`, `notes.md`, `loot/`, `recon/`, `exports/`) es la **fuente de verdad inmutable y auditable**. El backend sincroniza y refleja este estado sin crear dependencias externas rígidas.
2. **Zero Plaintext Leakage**:
   Las claves API de reconocimiento y LLMs se almacenan cifradas en SQLite con **AES-256-GCM**. La inyección en herramientas de auditoría (`shodan`, `findomain`, `nuclei`, `x8`) se realiza estrictamente en memoria mediante `pt-vault run <comando>` o subprocesos controlados, sin escribir secretos en disco ni en el historial de comandos.
3. **Evidence-First & Scope Guard**:
   Cada hallazgo técnico requiere evidencia reproducible (petición/respuesta HTTP o comando terminal con hash de integridad). Las validaciones de alcance son evaluadas por el motor estricto de `pt-scope` antes de emitir tráfico de red.
4. **Zero Public Ingress**:
   El servicio expone el puerto `8080` exclusivamente en loopback local o red privada de Tailscale (`100.x.y.z`), preservando el aislamiento estricto de red del laboratorio.

---

## 2. Arquitectura de Componentes

```
+--------------------------------------------------------------------------+
|                        SPA Vue 3 + Tailwind CSS                          |
|  (Barra Táctica, Navbar con VPN, Alcance, Hallazgos, Loot, Recon, Vault) |
+--------------------------------------------------------------------------+
       |                                                    |
  REST API (:8080)                                      Iframe (:7681)
       v                                                    v
+--------------------------------------+           +-----------------------+
|        Backend FastAPI (Python 3.14) |           | Web Terminal (ttyd)   |
|  - Sincronizador de Workspace        |           | Shell tester / Zsh    |
|  - API Key Vault (AES-256-GCM)       |           +-----------------------+
|  - Tactical Proxy Gateway            |
|  - Orquestador Recon (Scope Guard)   |
|  - Gestor de VPN (Control & Socket)  |
+--------------------------------------+
       |                   |                   |
       v                   v                   v
+--------------+   +---------------+   +-----------------------------+
| SQLite (WAL) |   |  /workspace   |   | Herramientas CLI SecLab     |
| vault.db     |   | target.yaml   |   | pt-vault, pt-scope, pt-eng  |
|              |   | evidence/     |   | pt-recon-pipeline, pt-report|
+--------------+   | loot/, recon/ |   +-----------------------------+
                   +---------------+
```

---

## 3. Comandos Operativos del Makefile

El ciclo de vida del dashboard se controla mediante recetas nativas del `Makefile`:

```bash
# Iniciar el laboratorio con el dashboard integrado en segundo plano
make dashboard

# Iniciar como demonio en segundo plano (background)
make dashboard-daemon

# Consultar estado del demonio y puerto
make dashboard-status

# Detener todo el laboratorio, incluido el dashboard y la VPN
make dashboard-stop

# Recompilar la interfaz SPA frontend
make dashboard-build

# Ejecutar la suite completa de pruebas unitarias
make python-units-check
```

El backend y el frontend compilado viven dentro de `seclab-sbf:full`. `make compose-up` también inicia el dashboard y publica sus puertos solo en loopback. `make dashboard-build` recompila el frontend; después se necesita `make build-full` y recrear el contenedor para aplicar cambios. La etiqueta `seclab.build-inputs` incluye las fuentes y el frontend compilado del dashboard, excluyendo datos del Vault y cachés de Python.

---

## 4. Módulos y Capacidades Operativas

### 4.1. Control Táctico de VPN (Encendido, Apagado y Credenciales)

Ubicado en la barra superior (`Navbar.vue`):
* **Telemetría en Vivo**: Indicador reactivo con pulso que identifica el estado (`tun0`) y el perfil conectado:
  - 🟢 **THM** (`TryHackMe`): Red esmeralda.
  - 🟠 **HTB** (`HackTheBox`): Ámbar táctico.
  - 🔵 **CLI** (`Cliente`): Azul corporativo.
  - ⚪ **OFFLINE**: Gris cuando no hay túnel activo.
* **Encendido y Apagado**: Botones directos para encender o apagar la VPN con un clic.
  El dashboard ejecuta `/usr/local/bin/vpn-control client` como `tester` y consulta el estado por el socket Unix del daemon. El perfil y el PID proceden del controlador; la mera existencia de `tun0` no significa que haya una VPN conectada. La interfaz distingue `APAGADO`, `CONECTANDO` y `ENCENDIDO`.
* **Modos de Autenticación**:
  - **Conexión Directa**: Para perfiles con certificados y claves embebidos (TryHackMe, HackTheBox).
  - **Usuario / Contraseña**: Soporte para ingresar usuario y contraseña opcionales, con la capacidad de persistirlos cifrados en el Vault (AES-256-GCM) o utilizarlos de forma efímera durante la sesión.

### 4.2. SecLab API Key Vault & Tactical Proxy Gateway

Gestión centralizada de credenciales ofensivas y de inteligencia:
* **Proveedores Soportados**: Shodan, Censys, VirusTotal, Chaos/PDCP, OpenAI, Anthropic, Gemini, HTB y THM.
* **Inyección en Memoria (`pt-vault run`)**:
  ```bash
  # Listar servicios configurados en el Vault
  pt-vault list

  # Ejecutar herramientas inyectando credenciales en el entorno del subproceso
  pt-vault run shodan myinfo
  pt-vault run findomain -t objetivo.com
  ```
* **Tactical Proxy**: Conmutación por error (failover) ante límites de tasa (429) o fallos (5xx) con registro continuo de auditoría.

### 4.3. Pipeline de Reconocimiento con Scope Guard (`pt-recon`)

Disponible en la pestaña **📡 Reconocimiento** de cada auditoría:
* **Scope Guard Preventivo**: Valida los objetivos contra las listas autorizadas de `target.yaml` antes de emitir tráfico de red.
* **Etapas Seleccionables**:
  - `all`: Pipeline completo (Subdominios -> Sondeo Web -> URLs -> Patrones GF).
  - `subdomains`: Enumeración de subdominios (`subfinder`, `assetfinder`, `findomain`).
  - `probe`: Sondeo de puertos y servicios HTTP/HTTPS (`httpx`, `httprobe`).
  - `urls`: Cosecha pasiva de URLs y endpoints JavaScript (`gau`).
  - `patterns`: Clasificación de parámetros y patrones de riesgo (`gf xss`, `sqli`, `ssrf`, `idor`).
* **Modo Dry-Run**: Simulación completa sin tráfico real para validar el alcance.
* **Consola en Vivo**: Streaming en tiempo real de `recon/recon.log`.
* **Auditoría de Descartados**: Registro de cada objetivo bloqueado con su causa de exclusión.

### 4.4. Modo CTF, Banderas y Botín (Loot)

* **Banderas**: Seguimiento de `user_flag` y `root_flag` con registro automático de fecha y hora en `flags.json`.
* **Loot de Credenciales**: Almacenamiento estructurado en `loot/credentials.json` (servicio, host, puerto, usuario, hash/password, notas).
* **Explorador de Artefactos**: Navegación segura con protección estricta contra Path Traversal por las carpetas `recon/`, `fuzzing/`, `loot/`, `screenshots/` y `evidence/`.

### 4.5. Reportes Ejecutivos y Descarga Automática (`pt-eng pack`)

* **Vista Ejecutiva**: Resumen visual de severidades (Crítica, Alta, Media, Baja, Informativa).
* **Exportación a PDF**: Reglas `@media print` optimizadas para generar informes listos para cliente mediante `Ctrl+P` o `Imprimir Reporte`.
* **Empaquetado y Cierre**:
  - El botón **📦 Empaquetar y Descargar (.tar.gz)** compila todas las evidencias, notas y bitácoras, sanitiza secretos (JWTs, tokens Bearer, passwords) y genera el manifiesto criptográfico `manifest.sha256`.
  - Descarga automáticamente el archivo `.tar.gz` al navegador del operador.

---

## 5. Matriz de Puertos y Servicios

| Puerto | Protocolo | Servicio | Acceso Autorizado |
| :--- | :--- | :--- | :--- |
| `8080` | HTTP | SecLab Tactical Dashboard & REST API | Loopback (`127.0.0.1`) o Tailscale |
| `7681` | HTTP | Web Terminal (`ttyd`) con autenticación | Loopback (`127.0.0.1`) o Tailscale |
| `2222` | SSH | Contenedor SecLab (`tester`) con tmux | Loopback (`127.0.0.1`) o Tailscale |
| `22`   | SSH | Host de la VM (`ubuntu`) con fail2ban | Tailscale exclusivamente |

---

## 6. Procedimientos de Diagnóstico

### El dashboard no responde en el puerto 8080
1. Comprobar estado:
   ```bash
   make dashboard-status
   ```
2. Inspeccionar registros de arranque:
   ```bash
   docker logs --tail 50 seclab-sbf-lab-1
   ```
3. Reiniciar el servicio:
   ```bash
   make dashboard-stop
   make dashboard-daemon
   ```

### Pruebas de regresión y validación
Ejecutar antes de cualquier commit o despliegue:
```bash
make python-units-check
make makefile-check
make compose-refs-check
```

La reparación del control VPN de la fase 81 se verificó localmente con 77 pruebas Python, `make verify`, el build nativo arm64, el gate `make scan-image` y un ciclo real de encendido/apagado desde los botones del navegador con TryHackMe. El perfil se obtiene del daemon como `tester`; al apagar, `tun0` puede permanecer presente sin mostrar una conexión activa. La ruta por defecto y el hash de `/etc/resolv.conf` permanecieron iguales durante el ciclo. Para pasar el gate fue necesario recompilar `gau` 2.2.4 desde su commit fijado con Go y dependencias parcheadas; se mantiene la política de excepciones de Trivy existente.
