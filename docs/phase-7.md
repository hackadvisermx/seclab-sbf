# Fase 7 — Imagen full

## Estado

Imagen `full` construida desde `light` para VM dedicada y desechable:
Metasploit 6.5.5 (Ruby 3.3.8 compilado desde tarball oficial),
NetExec 1.5.1 (commit `c7dc286b`, con `nxc`), John, Hashcat CPU
(pocl), rockyou, PayloadsAllTheThings y Exploit-DB con
`searchsploit`. Ghidra y reversing quedan diferidos.

## Artefactos

- `images/full/Dockerfile`: stages `msf-builder` (Ruby + `bundle install`
  con `Gemfile.lock` del upstream, grupos dev/test excluidos) y
  `nxc-builder` (NetExec desde git fijado al commit), y stage final
  desde `light` con APT, datos y symlinks `msf*`, `nxc*`.
- `~/.msf4` y `~/.nxc` son symlinks a `/var/lib/seclab/tester/` porque
  el home es de solo lectura; el entrypoint crea los destinos.
- `scripts/install-full-packages.sh`: john, hashcat, pocl-opencl-icd,
  librerías runtime de Ruby/gemas, PAT, exploitdb y rockyou verificado.
- `Makefile`: `build-full` (requiere `build-light`; `FULL_BASE`
  seleccionable por arquitectura).
- `shell/tools.json`: perfil `full` con 38 herramientas y categorías
  nuevas `exploit` y `crack` (banner actualizado).

## Versiones fijadas

- Ruby 3.3.8 (tarball oficial, SHA-256), bundler 2.5.22 (BUNDLED WITH).
- metasploit-framework 6.5.5 tag `ec3cfbbf` (commit `c5429ba8`).
- NetExec 1.5.1 tag `v1.5.1` (commit `c7dc286b`); no esta en PyPI, se
  instala desde git. Sus 91 paquetes resueltos quedan en `tools.lock.yaml`
  bajo `python_packages_full`, porque varias dependencias se compilan
  desde fuente y no se pueden fijar con hashes por arquitectura.
- PayloadsAllTheThings commit `3ac27901`, exploitdb commit `150aef0e`.
- rockyou SecLists commit `eccfbd40` con SHA-256.
- john/hashcat/pocl y runtime desde snapshot Ubuntu (ver lockfile).

## Límites

- Sin base de datos PostgreSQL: `msfconsole` funciona, `db_*` requiere
  PG externo (fuera de alcance).
- Sin GPU: hashcat es CPU vía pocl.
- Rizin diferido: sin binario arm64 del upstream; exige build nativo
  por arquitectura aún no implementado.
- Ghidra/reversing diferidos según plan.
- La imagen supera 2 GB; solo para VM desechable, nunca host compartido.

## Verificación realizada (2026-09-25, ARM64 local)

- Build ARM64 OK (`seclab-sbf:full`, 3.93 GB); `msfconsole --version`
  6.5.5-dev en build. AMD64 pendiente (emulación lenta en Mac; queda
  para CI/VM).
- `msfconsole -q` responde `Framework: 6.5.5-dev` y `msfvenom` genera
  payload; `nxc --version` responde `1.5.1 - Yippie-Ki-Yay - c7dc286b`.
- `john` 1.9.0 (paquete Ubuntu, sin etiqueta jumbo en el banner);
  `hashcat --version` v6.2.6; `searchsploit --help` OK;
  `feroxbuster`/`dalfox` intactos de light; `rockyou.txt` 14 344 391
  líneas; Ruby 3.3.8.
- `pt-tools` con `PENTEST_PROFILE=full` lista 38 herramientas (plugin
  desbloqueado; banner con categorías crack/exploit).
- Scout Critical/High bloqueado: 2 intentos fallan en indexado por
  `trivy-java-db: unexpected EOF` (infra de red, no resultado de CVEs).
- El lockfile `supply-chain/tools.lock.yaml` cubre ya `full`, no solo
  `light` (cierre de la Fase 17).
