# Fase 59: Suite de Reconocimiento Web Tomnomnom (Assetfinder & Httprobe)

## 1. Contexto y Motivación

A partir del análisis del entorno de referencia `pentestdocker` (`/Users/castr/Library/CloudStorage/GoogleDrive-chcramirez@gmail.com/Mi unidad/2026/hacking-2026/pentestdocker`), se identificaron herramientas fundamentales del pipeline de reconocimiento web creadas por Tomnomnom que complementan de forma ideal el ecosistema de `seclab-sbf`:

1. **`assetfinder` (`v0.1.1` / commit `4e95d8701aae8cff1c27af2626eb22ba110ad583`)**:
   - Descubrimiento pasivo de dominios y subdominios relacionados a través de múltiples fuentes OSINT externas (crt.sh, Certspotter, HackerTarget, ThreatCrowd, URLScan, VirusTotal, Wayback Machine).
   - Complementa a `subfinder` descubriendo activos adicionales sin requerir llaves de API obligatorias.
2. **`httprobe` (`v0.2` / commit `7e8abdb4096ab224f21616478b699b4dfda9d409`)**:
   - Sondeo concurrente de servidores web activos (`http://` y `https://`) a partir de listas de dominios o subdominios descubiertos.
   - Provee una alternativa rápida y ligera a `httpx`.

Con esta integración, `seclab-sbf` completa de forma canónica el **ecosistema completo de herramientas de reconocimiento de Tomnomnom**:
- `anew`: Deduplicación en streaming y almacenamiento diferencial.
- `assetfinder`: Enumeración de subdominios y activos OSINT.
- `httprobe`: Verificación rápida de servicios web activos.
- `waybackurls`: Extracción masiva de URLs históricas y endpoints.
- `qsreplace`: Reemplazo masivo de parámetros de consulta para fuzzing de inyecciones.
- `gf`: Filtrado avanzado por expresiones regulares con la suite de 24 patrones precompilados en `/usr/local/share/seclab/gf-patterns/`.

---

## 2. Decisiones de Arquitectura y Seguridad

- **Compilación determinista en Go**:
  Ambas herramientas están escritas en Go puro y utilizan exclusivamente la biblioteca estándar de Go. Se compilan en la etapa `upstream-builder` de `images/full/Dockerfile` con:
  - `CGO_ENABLED=0`: Garantiza binarios estáticos sin dependencias dinámicas contra `glibc` ni librerías de build.
  - `-trimpath`: Elimina rutas del sistema de archivos local de los metadatos del ejecutable.
  - `-ldflags "-s -w"`: Elimina símbolos de depuración y tablas DWARF para optimizar el tamaño.
- **Invariante de inmutabilidad y permisos de ejecución**:
  Los binarios se copian en `/usr/bin/` con permisos `0555` (sólo lectura y ejecución).
  Cumplen al 100% con la restricción de rootfs de sólo lectura (`read_only: true`) y el principio de mínimo privilegio (`cap_drop: ALL`, usuario no-root `tester`).
- **Cadena de suministro (Supply Chain Integrity)**:
  Tanto `assetfinder` como `httprobe` están fijados por versión y commit exacto en `supply-chain/tools.lock.yaml`.
- **Evolución del pipeline `pt-recon`**:
  Se actualizó la función `pt-recon` en `shell/pentest-lab/pentest-lab.plugin.zsh`:
  - **Fase 1/4**: Ejecuta `subfinder` y `assetfinder` en paralelo/secuencia, deduplicando los subdominios descubiertos mediante `anew` en `subdomains.txt`.
  - **Fase 2/4**: Prueba la disponibilidad de servicios web activos mediante `httpx` (o fallback a `httprobe`) generando `live_hosts.txt`.
  - **Fase 3/4**: Extrae URLs históricas con `waybackurls` deduplicadas mediante `anew` en `wayback_urls.txt`.
  - **Fase 4/4**: Filtra y clasifica parámetros sensibles en `gf_patterns/` utilizando `gf`.

---

## 3. Registro en Manifiestos y Verificaciones

- Registrados en `shell/tools.json` dentro del diccionario `tools` y en el array `installed` (garantizando consistencia con la prueba unitaria `test_tools_json_manifest_consistency`).
- Se incorporó la prueba unitaria `test_tools_lock_tracks_assetfinder_and_httprobe` en `scripts/verify/check-python-units.py` (50/50 pruebas superadas).
- `make verify` en verde (Gitleaks, Hadolint, ShellCheck, verify-pins, makefile-check, compose-security, check-python-units).
- `actionlint` y `make compose-config` en verde sin advertencias.
