# Fase 61: Repositorio Offline de Post-Explotación & Staging de Payloads

## 1. Contexto y Objetivos

Durante operaciones de pentesting y resolución de laboratorios (TryHackMe, HackTheBox, evaluaciones autorizadas), las máquinas víctimas frecuentemente carecen de acceso a internet directo hacia repositorios públicos como GitHub o proveedores de paquetes. En consonancia con las mejores prácticas de entornos de alto rendimiento como Exegol (`/opt/resources`):

1. **Repositorio Local Inmutable de Post-Explotación**:
   - Ubicación centralizada en `/usr/local/share/seclab/payloads/post-exploit/`.
   - Provisto durante la construcción de la imagen y verificado criptográficamente por hash SHA-256 antes de instalarse.
   - Scripts y ejecutables listos para su transferencia inmediata a máquinas comprometidas:
     - **`linpeas.sh` (`20261003-ea9b2e92`)**: Script de auditoría y búsqueda de vectores de escalada de privilegios en Linux (PEASS-ng).
     - **`winPEAS.bat` (`20261003-ea9b2e92`)**: Script batch ligero para escalada en Windows.
     - **`winPEASany.exe` (`20261003-ea9b2e92`)**: Binario PE compilado standalone de PEASS-ng para arquitecturas Windows.
     - **`socat_linux_amd64` / `socat_linux_arm64` (`v1.7.4.4`)**: Binarios estáticos de `socat` compilados sin dependencias externas por ERNW Research (con symlink `socat` adaptado a la arquitectura del contenedor), ideales para port-forwarding y estabilización de TTY.
     - **`nc.exe` / `nc64.exe` (`v1.12`)**: Netcat para Windows (x86 y x64) compilado por `int0x33` con soporte nativo de la bandera `-e` para reverse/bind shells.

2. **Helper Zsh Ergonomico (`pt-serv-payloads`)**:
   - Permite lanzar instantáneamente un servidor web HTTP (por defecto en el puerto 8000 con `python3 -m http.server -d`) o un servidor SMB (puerto 445 mediante `smbserver.py` de Impacket/NetExec) apuntando directamente al directorio de payloads.
   - Muestra en consola la lista detallada de archivos disponibles junto con ejemplos listos para copiar y pegar según el sistema operativo objetivo (Linux `curl | sh`, Windows PowerShell `iwr`, o `certutil`).
   - Aliases ergonomicos: `servpayloads` y `payloadserver`.

---

## 2. Decisiones de Arquitectura y Seguridad

- **Integridad y Cadena de Suministro**:
  - Todos los artefactos están fijados con su versión, origen, commit y hash SHA-256 inmutable en `supply-chain/tools.lock.yaml` bajo la sección `post_exploit_payloads`.
  - La instalación en `scripts/install-toolkit-packages.sh` descarga cada recurso a través de TLS 1.2+ y valida el hash contra `sha256sum -c -` antes de moverlo a su destino.
  - Se asignan permisos estrictos de solo lectura y ejecución (`0555` en archivos, `0755` en directorio) para evitar cualquier manipulación en runtime.

- **Invariantes del Contenedor**:
  - `read_only: true`: El directorio `/usr/local/share/seclab/payloads/post-exploit/` forma parte del rootfs de solo lectura.
  - `cap_drop: ALL`: El servidor web o SMB se ejecuta dentro del espacio de usuario no privilegiado `tester`.
  - Los payloads están concebidos exclusivamente para staging y transferencia hacia máquinas remotas auditadas; no se ejecutan como parte del host del laboratorio.

---

## 3. Verificaciones y Calidad

- **Pruebas Unitarias Python**:
  - `test_tools_lock_tracks_post_exploit_payloads` añadido a `scripts/verify/check-python-units.py`, validando que todos los archivos y sus checksums SHA-256 exactos están registrados.
  - `test_pentest_lab_plugin_helpers_and_aliases` actualizado para verificar `pt-serv-payloads`, sus aliases (`servpayloads`, `payloadserver`) y su integración en `pt-help`.
  - Suite unitaria pasando al 100% (52/52 pruebas en verde).
- **Herramientas de Calidad**:
  - `shellcheck scripts/install-toolkit-packages.sh` limpio.
  - `zsh -n shell/pentest-lab/pentest-lab.plugin.zsh` limpio.
  - `make verify` y `make compose-config ENV_FILE=.env.example` validados satisfactoriamente.
