# Fase 60: Integración de Findomain y Pipeline de Endpoints JavaScript

## 1. Contexto y Objetivos

Continuando con la adopción de herramientas y flujos de trabajo de alto rendimiento identificados en `pentestdocker`:
1. **`findomain` (`v10.0.1`)**:
   - Enumerador de subdominios multi-hilo de alto rendimiento escrito en Rust.
   - Diseñado para extraer subdominios a través de múltiples APIs públicas y registros de Certificate Transparency (CT logs) en cuestión de segundos.
   - En `pentestdocker`, `findomain` constituía la primera herramienta invocada en la función `get_subdomains`.
2. **Triada Canónica de Subdominios**:
   - `subfinder` (ProjectDiscovery, APIs y resolución pasiva/activa).
   - `assetfinder` (Tomnomnom, fuentes OSINT pasivas).
   - `findomain` (Findomain Rust, CT logs de alta concurrencia).
   - Las tres herramientas operan en conjunto dentro de `pt-recon`, deduplicando sus resultados en tiempo real mediante `anew` en `subdomains.txt`.
3. **Extracción y Clasificación de Endpoints JavaScript**:
   - A partir de las URLs históricas recolectadas por `waybackurls`, se extraen automáticamente todos los endpoints con extensión `.js` en `js_files.txt`.
   - Permite enfocar auditorías de análisis estático de frontend, búsqueda de llaves de API, credenciales expuestas y rutas de endpoints no documentadas.

---

## 2. Decisiones de Arquitectura y Seguridad

- **Consumo de binarios oficiales verificados por SHA-256**:
  - `findomain` publica binarios oficiales precompilados para Linux `amd64` y `arm64`.
  - Se fijan los hashes SHA-256 tanto de los archivos comprimidos `.zip` como de los ejecutables extraídos en `supply-chain/tools.lock.yaml`.
  - Se descargan e instalan en `scripts/install-toolkit-packages.sh` con permisos estrictos `0555` en `/usr/bin/findomain`.
- **Invariantes de Contenedor**:
  - `read_only: true`: La herramienta no requiere escritura en el sistema de archivos raíz; opera escribiendo en el directorio de trabajo local (`/workspace/recon_...`).
  - `cap_drop: ALL`: No requiere capacidades especiales de red ni privilegios de root; opera como el usuario estándar `tester`.
- **Integración con `pt-recon`**:
  - **Fase 1/4**: `subfinder` + `assetfinder` + `findomain` piped a `anew`.
  - **Fase 2/4**: Sondeo web de hosts vivos con `httpx` (o fallback a `httprobe`).
  - **Fase 3/4**: URLs históricas con `waybackurls` + extracción de endpoints JavaScript en `js_files.txt`.
  - **Fase 4/4**: Clasificación de parámetros sensibles con `gf`.

---

## 3. Verificaciones y Calidad

- Registrado en `shell/tools.json` dentro de `tools` e `installed`.
- Test unitario `test_tools_lock_tracks_findomain` añadido a `scripts/verify/check-python-units.py` (51/51 pruebas superadas).
- `make verify` en verde (Gitleaks, Hadolint, ShellCheck, verify-pins, makefile-check, compose-security, check-python-units).
- `actionlint` y `make compose-config` validados satisfactoriamente.
