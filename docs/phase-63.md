# Fase 63: Cheatsheet Interactivo Ofensivo en Terminal (`pt-cheat` con `fzf`)

## 1. Contexto y Objetivos

En operaciones de pentesting, pruebas de penetración autorizadas y resolución de entornos de laboratorio (HackTheBox, TryHackMe), los auditores frecuentemente deben recordar o buscar comandos complejos con múltiples banderas específicas (como peticiones Kerberos con Impacket, túneles reversos con Chisel o Ligolo-ng, estabilización de shells PTY o transferencias de archivos vía SMB/HTTP).

Inspirado en el patrón ergonómico de herramientas como Arsenal y Navi:

1. **Catálogo Centralizado de Comandos (`cheatsheet.tsv`)**:
   - Ubicación en `shell/pentest-lab/cheatsheet.tsv`, empaquetado junto al plugin Oh My Zsh del laboratorio.
   - Estructura tabular de 4 columnas separadas por tabuladores: `categoria \t titulo \t comando \t descripcion`.
   - Más de 45 comandos organizados en 7 categorías operacionales clave:
     - **`ad` (Active Directory & Kerberos)**: Comandos para Kerberoasting (`GetUserSPNs`), AS-REP Roasting (`GetNPUsers`), DCSync (`secretsdump`), Pass-the-Hash (`nxc smb` y `nxc winrm`), ejecución WMI/SMB remota y auditoría global con `enum4linux-ng`.
     - **`pivot` (Pivoting & Port-Forwarding)**: Listeners y agentes de Ligolo-ng, servidores y clientes inversos de Chisel, túneles dinámicos SSH (SOCKS5), remote port forwarding, proxychains y redirecciones con `socat`.
     - **`tty` (Estabilización TTY & Shells)**: Spawning interactivo PTY (`python3 pty.spawn`, `script`), configuración de terminal (`stty raw -echo; fg; reset`, variables `TERM`/`SHELL`, ajuste de filas/columnas) y listeners socat TTY.
     - **`web` (Web Recon, Fuzzing & Parámetros)**: Parámetros para `ffuf`, `feroxbuster`, `x8`, `pt-fuzz-params`, `pt-recon`, `gau` y escaneo con Nikto.
     - **`staging` (Transferencia & Payloads)**: Servidores HTTP y SMB con `pt-serv-payloads` (para el staging offline de `linpeas`/`winPEAS`), transferencias rápidas y comandos de descarga nativa en Windows (`certutil`, PowerShell `iwr`).
     - **`crack` (Cracking & Hashes)**: Modos específicos de Hashcat para NTLM (`-m 1000`), Kerberos TGS (`-m 13100`), Kerberos AS-REP (`-m 18200`), NetNTLMv2 (`-m 5600`) y John the Ripper.
     - **`net` (Escaneo de Red & Descubrimiento)**: Escaneos en 2 fases con `pt-nmp`, extracción de puertos con `pt-extractports` y descubrimiento de hosts SMB con `nxc`.

2. **Comando Interactivo `pt-cheat` con `fzf`**:
   - Integrado directamente en Zsh mediante el plugin `pentest-lab`.
   - Soporta filtrado directo por categoría o término de búsqueda (`pt-cheat ad`, `pt-cheat pivot`, `pt-cheat chisel`).
   - Búsqueda difusa interactiva con `fzf`:
     - Visualización limpia: columna de categoría, título y descripción.
     - Ventana de previsualización (`--preview`) que resalta el comando sugerido en color cyan/verde antes de seleccionarlo.
   - **Inyección en Buffer de Zsh (`print -z`)**:
     - Al presionar Enter, el comando seleccionado **no se ejecuta a ciegas**, sino que se inserta directamente en la línea de edición de Zsh.
     - El operador puede inspeccionar y sustituir cómodamente las variables (`<TARGET>`, `<DC_IP>`, `<USER>`, etc.) antes de presionar Enter.
   - **Fallback No Interactivo**:
     - Si `fzf` no está disponible o la entrada estándar no es una terminal (`! -t 0`), muestra un listado formateado en texto plano filtrado por la categoría o palabra clave especificada.

3. **Aliases Ergonómicos**:
   - `alias ptcheat="pt-cheat"`
   - `alias cheat="pt-cheat"`
   - Documentado en el banner y menú de ayuda de `pt-help`.

---

## 2. Decisiones de Arquitectura y Seguridad

- **Seguridad en la Ejecución**:
  - Los comandos del cheatsheet son plantillas seguras con placeholders explícitos (e.g. `<TARGET>`, `<DOMAIN>`, `<USER>`).
  - El uso de `print -z` evita cualquier ejecución involuntaria de comandos al seleccionarlos en `fzf`.
- **Integridad y Cadena de Suministro**:
  - `cheatsheet.tsv` es inmutable y se valida en tiempo de prueba unitaria mediante `test_cheatsheet_dataset_integrity`.
  - No requiere binarios externos no verificados ni dependencias runtime adicionales.

---

## 3. Verificaciones y Calidad

- **Pruebas Unitarias Python**:
  - `test_cheatsheet_dataset_integrity` añadido a `scripts/verify/check-python-units.py`, validando que `cheatsheet.tsv` existe, tiene al menos 40 comandos, exactamente 4 columnas TSV por registro y categorías permitidas.
  - `test_pentest_lab_plugin_helpers_and_aliases` actualizado para verificar `pt-cheat()`, aliases `ptcheat`/`cheat` y referencia en `pt-help`.
  - Suite completa: 54/54 pruebas pasando al 100%.
- **Herramientas de Calidad**:
  - `zsh -n shell/pentest-lab/pentest-lab.plugin.zsh` limpio.
  - `make verify` pasando al 100% (Gitleaks, Hadolint, Makefile, Compose refs, Compose security, Python units).
  - `make compose-config ENV_FILE=.env.example` limpio en todas las configuraciones.
