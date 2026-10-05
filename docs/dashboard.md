# Dashboard Táctico & API Vault de SecLab-SBF

Estación de control web unificada para la gestión operativa y técnica de auditorías de ciberseguridad ética (Bug Bounty, Retos CTF en TryHackMe / HackTheBox y Pruebas de Penetración autorizadas).

---

## 1. Principios de Diseño y Seguridad

1. **Filesystem-First**:
   El sistema de archivos `/workspace` (`target.yaml`, `evidence/*.md`, `terminal.log`, `notes.md`, `loot/`, `recon/`, `exports/`) es la **fuente de verdad editable y auditable**. El backend sincroniza y refleja este estado sin crear dependencias externas rígidas.
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

# Pruebas de autenticación, WebSocket, archivos, claves y API
make dashboard-tests

# Pruebas de sanitización de reportes
npm --prefix dashboard/frontend test
```

El backend y el frontend compilado viven dentro de `seclab-sbf:full`. `make compose-up` también inicia el dashboard y publica sus puertos solo en loopback. `make dashboard-build` recompila el frontend; después se necesita `make build-full` y recrear el contenedor para aplicar cambios. La etiqueta `seclab.build-inputs` incluye las fuentes y el frontend compilado del dashboard, excluyendo datos del Vault y cachés de Python.

---

### Acceso del operador

Al abrir `http://localhost:8080`, inicia sesión como **tester** con la contraseña configurada en `TTYD_PASSWORD`. Se puede definir una contraseña separada con `DASHBOARD_PASSWORD` en el archivo de secretos, sin valores por defecto. La sesión dura ocho horas; **Cerrar sesión** revoca el token y desconecta el streaming de logs. La cookie es HttpOnly y SameSite Strict, y usa Secure cuando se accede por HTTPS. Las descargas usan la misma sesión. Los tokens antiguos de localStorage dejan de funcionar.

La API, incluido el control VPN y la bóveda, responde 401 sin sesión. La entrada admite cinco intentos por minuto para el único operador. Los orígenes y hosts por defecto son localhost y 127.0.0.1 en el puerto 8080. Para un puerto distinto, configura `DASHBOARD_CORS_ORIGINS`; para un nombre privado, configura también `DASHBOARD_ALLOWED_HOSTS`, siempre sin comodines. El acceso remoto sigue pasando por un túnel del host sobre Tailscale. Estos ajustes no publican puertos.

Los proyectos con enlaces simbólicos no aparecen en la lista y sus operaciones son rechazadas. Los hallazgos requieren identificadores de hasta 128 caracteres alfanuméricos, punto, guion o guion bajo, empezando por letra, número o guion. Crear un proyecto con un nombre existente conserva sus archivos y devuelve un error.

La bóveda no regenera una clave inválida o ausente si ya contiene datos cifrados. Restaura la pareja `vault.db` y `.vault.key` desde un respaldo consistente; no borres la clave para intentar corregir un error. Esta protección y el login no aíslan la bóveda de herramientas que se ejecuten bajo el mismo usuario Unix `tester`.

## 4. Módulos y Capacidades Operativas

La lista de auditorías y retos y la cabecera de cada proyecto incluyen **Eliminar**. La confirmación muestra el nombre del proyecto y avisa que se borrará su carpeta completa, incluidas notas, evidencias, botín, reportes y archivos, sin recuperación desde el dashboard. **Cancelar** conserva el proyecto. Tras eliminar, la tarjeta desaparece de la lista o se vuelve a la lista desde el detalle. Si el reconocimiento está en curso, se debe esperar a que termine. Un reto y una auditoría con el mismo nombre se eliminan de forma independiente.

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
  - `probe`: Sondeo controlado de HTTP/HTTPS en 80/443, con `GET /`, IP fijada y TLS verificado. Registra redirecciones sin seguirlas.
  - `urls`: Cosecha pasiva de URLs y endpoints JavaScript (`gau`).
  - `patterns`: Clasificación de parámetros y patrones de riesgo (`gf xss`, `sqli`, `ssrf`, `idor`).
* **Modo Dry-Run**: Previsualiza el alcance y las etapas sin ejecutar herramientas ni emitir tráfico. El motor no modifica artefactos, `summary.json` ni `terminal.log`; el dashboard conserva únicamente la bitácora del lanzamiento. El estado es **SIMULADO** y las métricas existentes no se presentan como resultados nuevos.
* **Consola en Vivo**: Streaming en tiempo real de `recon/recon.log`.
* **Auditoría de Descartados**: Registro de cada objetivo bloqueado con su causa de exclusión.

El validador `pt-scope` y el pipeline usan las mismas reglas en `seclab_scope.py`. Un dominio exacto autoriza solo ese nombre; `*.example.com` autoriza sus descendientes, pero no `example.com`. Para ambos, incluye las dos entradas. Las exclusiones tienen prioridad; los endpoints comparan esquema, host, puerto y límite de segmento de ruta. Un YAML inválido, duplicado o con claves de alcance desconocidas detiene el flujo. El sondeo de raíz requiere autorización del dominio o IP: una lista de endpoints aislados no autoriza explorar el resto del host.

Antes de conectar, se comprueba el alcance y se resuelve el host una vez. Todas las direcciones DNS deben ser permitidas; se fija una de ellas para los intentos HTTP y HTTPS manteniendo Host y SNI. Se bloquean loopback, metadata cloud, Tailscale/CGNAT, interfaces y gateway del laboratorio. Las direcciones privadas requieren además una IP o CIDR explícito en alcance. Un certificado no confiable queda registrado como `tls_untrusted`, sin inventar un servicio HTTPS activo. El flujo no sustituye pruebas autenticadas de una auditoría.

El bloqueo incluye los endpoints de metadata IPv6 documentados por [AWS (`fd00:ec2::254`)](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/instancedata-data-retrieval.html) y [Google Cloud (`fd20:ce::254`)](https://docs.cloud.google.com/compute/docs/metadata/overview), incluso si se declara un CIDR amplio.

Los límites de **sondeo HTTP activo** se leen de `operational_limits` en `target.yaml`:

| Campo | Por defecto | Rango permitido |
| --- | --- | --- |
| `max_requests_per_second` | 1 | 0.1–100 intentos/s, compartidos entre tareas |
| `max_parallel_threads` | 1 | 1–32, entero |
| `max_probe_targets` | 1000 | 1–10000, entero; se verifica antes del sondeo |
| `probe_timeout_seconds` | 8 | 1–30 segundos por intento HTTP, incluyendo conexión, TLS y cabeceras |

La resolución DNS usa el resolver del sistema. Las consultas **pasivas a proveedores** se ejecutan por herramienta de forma secuencial, con timeout de 180 segundos: subfinder recibe su límite de tasa y gau usa una tarea sin reintentos. No se afirma un límite global sobre solicitudes internas de esos proveedores. No se ejecutan pruebas DoS, fuerza bruta ni explotación en estas etapas.

Las plantillas y los proyectos nuevos usan estos valores conservadores. Los proyectos existentes conservan sus límites configurados.

Los fallos de herramientas (ausencia, timeout o salida distinta de cero) detienen las etapas siguientes, devuelven código CLI 1 y marcan el trabajo **FALLIDO**. No se usan stdout parcial ni respuestas ficticias. Los archivos anteriores de la etapa fallida se conservan y el resumen avisa `metrics_source: previous_artifacts`; una ejecución puede haber actualizado etapas anteriores. `recon/probe_observations.jsonl` conserva respuestas y fallos del sondeo; `probe_discarded.txt` conserva los candidatos rechazados por alcance. Consultar `pt-recon status` no escribe archivos.

Las regresiones se ejecutan con `make python-units-check` (incluye `scripts/verify/test_recon_safety.py`); `make dashboard-tests` prueba el runner instalado dentro de la imagen, sin red.

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
