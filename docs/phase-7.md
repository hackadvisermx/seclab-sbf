# Fase 7 — Imagen full

## Estado

Imagen `full` construida desde `light` para VM dedicada y desechable:
Metasploit 6.5.5 (Ruby 3.3.8 compilado desde tarball oficial),
John, Hashcat CPU (pocl), rockyou, PayloadsAllTheThings y Exploit-DB
con `searchsploit`. Ghidra y reversing quedan diferidos.

## Artefactos

- `images/full/Dockerfile`: stage `msf-builder` (Ruby + `bundle install`
  con `Gemfile.lock` del upstream, grupos dev/test excluidos) y stage
  final desde `light` con APT, datos y symlinks `msf*`.
- `scripts/install-full-packages.sh`: john, hashcat, pocl-opencl-icd,
  librerías runtime de Ruby/gemas, PAT, exploitdb y rockyou verificado.
- `Makefile`: `build-full` (requiere `build-light`; `FULL_BASE`
  seleccionable por arquitectura).
- `shell/tools.json`: perfil `full` con 36 herramientas y categorías
  nuevas `exploit` y `crack` (banner actualizado).

## Versiones fijadas

- Ruby 3.3.8 (tarball oficial, SHA-256), bundler 2.5.22 (BUNDLED WITH).
- metasploit-framework 6.5.5 commit `ec3cfbbf`.
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

## Verificación realizada

- Build ARM64 y AMD64; `msfconsole --version` 6.5.5 en build.
- `john` reporta jumbo (ver smoke); `hashcat --version`; `searchsploit`
  contra exploitdb local; `feroxbuster`/`dalfox` intactos de light.
- `pt-tools` con `PENTEST_PROFILE=full` lista 36 herramientas.
- Scout sin Critical/High en ambas arquitecturas.
