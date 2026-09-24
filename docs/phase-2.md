# Fase 2 — Compose local y workspace

## Estado

La fase 2 está implementada y verificada en Docker Desktop para macOS con arquitectura `linux/arm64`. Esta fase todavía no instala ttyd, SSH, shell interactiva ni herramientas de pentest; esas capacidades pertenecen a las fases siguientes.

## Artefactos

- `compose.yaml`: servicio local `lab`, sin puertos publicados, rootfs read-only, `cap_drop: ALL`, `no-new-privileges`, límites de CPU/memoria/PIDs y tmpfs.
- `compose.local.yaml`: override local para construir y etiquetar `seclab-sbf:base`.
- `scripts/entrypoint/base-entrypoint.sh`: valida perfil y workspace antes de ejecutar el comando.
- `scripts/health/base-healthcheck.sh`: comprueba workspace, sistema base y entrypoint.
- `images/base/Dockerfile`: copia los scripts, establece entrypoint y healthcheck.
- `scripts/generate-keys.sh` genera un par local Ed25519 en `.secrets/ssh/`, ignorado por Git, para el usuario `tester`.
- `Makefile`: agrega `compose config`, `compose up`, `compose down`, `compose shell` y `keys`.

## Seguridad de la configuración

- No existe `ports:`; el contenedor no publica ttyd, SSH ni otro servicio.
- `${WORKSPACE_DIR:-./workspace}` se monta como bind mount en `/workspace` y no se crea automáticamente.
- `${LAB_ENV_FILE:-.env}` se monta como lectura en `/run/secrets/lab.env`; los secretos no se inyectan como `environment`.
- Las claves privadas locales viven en `.secrets/ssh/` con permisos `600` y nunca se montan en el contenedor; la clave pública se escribe en `.env` para `tester`.
- El filesystem raíz es read-only; `/tmp`, `/run` y `/var/tmp` son tmpfs.
- `PENTEST_PROFILE` solo acepta `light` o `full`.
- El healthcheck no ejecuta red ni herramientas de pentest.

## Verificación local

Para validar Compose sin usar credenciales reales:

```text
make compose config ENV_FILE=.env.example
make compose up ENV_FILE=.env.example
docker compose -f compose.yaml -f compose.local.yaml ps
make compose down ENV_FILE=.env.example
```

Para usar el laboratorio con secretos, `make compose up` crea `.env` desde `.env.example` si no existe y aplica permisos `600`; después debes completar las credenciales:

```text
make compose up
make compose shell
```

`make keys` genera automáticamente la clave local de `tester` y completa `SSH_PUBLIC_KEY` sin imprimir el contenido. `make compose up` ejecuta esa preparación cuando usa `.env`.

`make compose shell` abre una shell interactiva en el servicio `lab`. La carpeta `workspace/` permanece vacía hasta que el usuario la use.

## Smoke test verificado

- `make compose config ENV_FILE=.env.example`: correcto.
- `make compose up ENV_FILE=.env.example`: correcto.
- Contenedor: `healthy`.
- Bind mount: lectura y escritura verificadas.
- `read_only=true`.
- `CapDrop=["ALL"]`.
- `no-new-privileges=true`.
- `NetworkSettings.Ports={}`.

## Límites

- `.env` está ignorado por Git; el archivo local puede existir con valores vacíos y debe completarse antes de habilitar ttyd o SSH.
- La imagen actual es únicamente la base mínima.
- Tailscale, VPN, capacidad de proxy, SSH, ttyd y Oh My Zsh se implementarán en fases posteriores.
