# Fase 57 — Suite de Filtrado de URLs y Fuzzing Web (gf, gf-patterns, qsreplace)

## Estado

La fase 57 está implementada en código y verificada. Incorpora las utilidades `gf`, `qsreplace` y la colección de patrones `gf-patterns` en la imagen del laboratorio (`seclab-sbf:full`), cerrando la brecha de filtrado de parámetros y preparación de fuzzing web identificada en `pentestdocker`.

## Componentes

1. **`gf` (Tomnomnom, Go)**:
   - Commit fijado: `dcd4c361f9f5ba302294ed38b8ce278e8ba69006`
   - Wrapper de `grep` para análisis de URLs, código y texto con patrones JSON predefinidos.
   - Compilado en `upstream-builder` sin dependencias externas (biblioteca estándar de Go).
   - Binario instalado en `/usr/bin/gf` con permisos `0555`.

2. **`qsreplace` (Tomnomnom, Go)**:
   - Tag: `v0.0.3` (commit `320475befaf66d986400aa8c3ed9b43e0b6b5a02`)
   - Reemplazo masivo de valores de query parameters en URLs (`stdin` -> reemplazo -> `stdout`).
   - Compilado en `upstream-builder` sin dependencias externas (biblioteca estándar de Go).
   - Binario instalado en `/usr/bin/qsreplace` con permisos `0555`.

3. **`gf-patterns`**:
   - Commit fijado: `f686f06ae647726578920084c894100d702496cc` (`1ndianl33t/Gf-Patterns`)
   - Integrado junto con los patrones base de `tomnomnom/gf/examples/` (`aws-keys`, `s3-buckets`, `debug-pages`, `cors`, `takeovers`, etc.).
   - Instalado en la ruta compartida de solo lectura: `/usr/local/share/seclab/gf-patterns` con permisos `0555`.
   - Symlinks creados en el home de `tester`: `/home/tester/.gf` y `/home/tester/.config/gf` apuntando a `/usr/local/share/seclab/gf-patterns`. Al ser el rootfs de solo lectura, `gf` puede resolver los patrones directamente sin intentar escribir en su home.

4. **Integración con `pt-recon`**:
   - `shell/pentest-lab/pentest-lab.plugin.zsh` añade la Fase 4 al comando `pt-recon`:
     Tras recolectar URLs con `waybackurls` y `anew`, evalúa automáticamente los patrones `xss`, `sqli`, `ssrf`, `rce`, `lfi`, `idor` y `redirect`, guardando los hallazgos en la subcarpeta `gf_patterns/`.

## Manifiestos y Supply Chain

- `supply-chain/tools.lock.yaml`: Registra `gf` y `qsreplace` en `built_binaries`, y `gf-patterns` en `templates`.
- `shell/tools.json`: Registra ambas herramientas en las secciones `tools` e `installed` (categoría `utilities`).

## Verificación

- `make verify`: Gitleaks (0 leaks), Hadolint, ShellCheck, verify-pins, makefile-check, compose-security y python-units todos en verde.
- `python3 scripts/verify/check-python-units.py`:
  - `test_tools_json_manifest_consistency`: sincronización de `tools` e `installed` al 100%.
  - `test_tools_lock_tracks_web_recon_artifacts`: validación de que el lockfile rastrea `gf`, `qsreplace` y `gf-patterns`.
- `actionlint`: Workflows de GitHub Actions validados.
