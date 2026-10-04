# Fase 58 — GEF (GDB Enhanced Features) para Reversing y Binary Exploitation

## Estado

La fase 58 está implementada en código y verificada. Incorpora la extensión **GEF (GDB Enhanced Features)** fijada por commit y checksum SHA-256 en la imagen del laboratorio (`seclab-sbf:full`), transformando `gdb` y `gdb-multiarch` en un entorno moderno de reversing y binary exploitation / PWN.

## Componentes

1. **`GEF` (GDB Enhanced Features)**:
   - Upstream: `https://github.com/hugsy/gef`
   - Versión: `2026.01`
   - Commit fijado: `18404074f469c70480aae071fbb77b75a2ed8507`
   - SHA-256 verificado: `04cdfe961f1e9151933d32cf6b548d9e6a76a1aef8b27c020c575b8d4264ed20`
   - Tipo: Script Python puro para GDB, sin dependencias externas fuera de la biblioteca estándar de Python 3.
   - Ubicación instalada: `/usr/local/share/seclab/gef/gef.py` con permisos de solo lectura (`0555`).

2. **Configuración de GDB e Integración en el Sistema**:
   - `/etc/gdb/gdbinit`: Archivo de configuración global (`0444`) que carga automáticamente GEF mediante:
     ```gdb
     source /usr/local/share/seclab/gef/gef.py
     ```
   - `/home/tester/.gdbinit`: Enlace simbólico inmutable que apunta a `/etc/gdb/gdbinit`, permitiendo que cualquier invocación de `gdb` o `gdb-multiarch` por parte del usuario `tester` cargue la extensión inmediatamente.
   - Directorio temporal: GEF crea sus archivos de contexto en `/tmp/gef`, que en `seclab-sbf` reside en un `tmpfs` con permisos de escritura efímeros, respetando el rootfs de solo lectura (`read_only: true`).

3. **Capacidades Habilitadas**:
   - Visualización estructurada y en color del contexto de ejecución: registros, instrucciones próximas (desensamblado interactivo), pila y memoria.
   - Comprobación de mitigaciones binarias nativa (`checksec`): NX, Canary, PIE, RELRO, Fortify.
   - Inspección y seguimiento de heap, búsqueda de patrones (`pattern create`, `pattern offset`), gadgets ROP y manejo de arquitecturas múltiples (x86/x64, ARM, AARCH64, MIPS, RISC-V) mediante `gdb-multiarch`.

## Manifiestos y Supply Chain

- `supply-chain/tools.lock.yaml`: Registra `gef` en `third_party_binaries` con su URL raw, commit exacto, hash SHA-256 e intérprete Python.
- `shell/tools.json`: Registra `gef` en `tools` (categoría `development`) y en `installed`.

## Verificación

- `make verify`: Gitleaks (0 leaks), Hadolint, ShellCheck, verify-pins, makefile-check, compose-security y python-units todos en verde.
- `python3 scripts/verify/check-python-units.py`:
  - `test_tools_lock_tracks_gef`: valida presencia e integridad de la entrada de GEF en `tools.lock.yaml`.
  - `test_tools_json_manifest_consistency`: sincronización de `tools` e `installed` al 100%.
- `actionlint`: Workflows de GitHub Actions validados.
