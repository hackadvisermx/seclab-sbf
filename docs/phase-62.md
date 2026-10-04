# Fase 62: Fuzzing de Parámetros de Próxima Generación (x8 y gau)

## 1. Contexto y Objetivos

Continuando con la optimización de metodologías de reconocimiento y auditoría de aplicaciones web basadas en frameworks modernos (patrón reconFTW):

1. **`x8` (`v4.3.0`)**:
   - Fuzzer de parámetros ocultos (GET, POST, JSON, Headers) de última generación escrito en Rust.
   - Entre 10x y 50x más rápido que soluciones tradicionales como Arjun (Python), eliminando colisiones de dependencias en Python 3.14.
   - Algoritmo de detección heurística basado en comparación diferencial línea por línea de respuestas HTTP, códigos de estado, reflexiones y anomalías dinámicas.
   - Helper interactivo en shell: `pt-fuzz-params <URL> [wordlist]` y alias `fuzzparams`.

2. **`gau` (GetAllUrls `v2.2.4`)**:
   - Herramienta concurrente de alto rendimiento escrita en Go por Corben Leo (`lc`).
   - Extrae URLs pasivas de múltiples fuentes de inteligencia pública: AlienVault Open Threat Exchange (OTX), Wayback Machine, Common Crawl y URLScan.
   - Se integra directamente en la etapa 3 de `pt-recon` complementando a `waybackurls`, ampliando la cobertura de activos históricos, endpoints JavaScript (`js_files.txt`) y filtrado con `gf`.

---

## 2. Decisiones de Arquitectura y Seguridad

- **Cadena de Suministro y Verificación Criptográfica**:
   - `gau`: Binarios oficiales precompilados de Go consumidos desde GitHub releases (`lc/gau` v2.2.4), verificados con doble hash SHA-256 (tanto del archivo comprimido `.tar.gz` como del ejecutable extraído) para `linux/amd64` y `linux/arm64`.
   - `x8`: Binario oficial precompilado en Rust para `linux/amd64` (`x86_64-linux-x8.gz` de Sh1Yo/x8), y paquete verificado de BlackArch Linux para `linux/arm64` (`aarch64.pkg.tar.zst`), ambos validados por hash SHA-256 antes de instalarse con permisos estrictos `0555` en `/usr/bin/x8`.
   - `zstd`: Incorporado como paquete nativo del snapshot de Ubuntu (`resolute`, versión `1.5.7+dfsg-3`) en `supply-chain/tools.lock.yaml` para descompresión reproducible sin librerías externas no controladas.

- **Invariantes del Contenedor**:
   - `read_only: true`: Ni `x8` ni `gau` requieren escribir en el rootfs; operan consumiendo y produciendo datos en el directorio de trabajo persistente del laboratorio (`/workspace`).
   - `cap_drop: ALL`: Operan íntegramente en espacio de usuario sin capacidades `root` ni privilegios especiales.

- **Pipeline Unificado de Reconocimiento (`pt-recon`)**:
   - Etapa 1/4: Subdominios con `subfinder` + `assetfinder` + `findomain` piped a `anew`.
   - Etapa 2/4: Sondeo web de hosts vivos con `httpx` / `httprobe`.
   - Etapa 3/4: Recolección y deduplicación concurrente de URLs pasivas con `waybackurls` + `gau` hacia `wayback_urls.txt`, extrayendo automáticamente endpoints `.js` a `js_files.txt`.
   - Etapa 4/4: Clasificación heurística de parámetros con `gf` y patrones especializados.

---

## 3. Verificaciones y Calidad

- Registrados en `shell/tools.json` dentro del catálogo `tools` y el array `installed` (98 herramientas sincronizadas).
- Test unitario `test_tools_lock_tracks_x8_and_gau` añadido a `scripts/verify/check-python-units.py` (53/53 pruebas superadas).
- `make verify` 100% en verde (Gitleaks, Hadolint, ShellCheck, verify-pins, makefile-check, compose-security, check-python-units).
- `actionlint` y `make compose-config` validados satisfactoriamente.
