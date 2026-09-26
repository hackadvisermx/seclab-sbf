SHELL := /bin/sh

.PHONY: sync-secrets base-check help verify verify-secrets lint-docker lint-shell build-base build-light build-full env-init keys ensure-env ensure-image compose config up down shell zsh tmux compose-config compose-up compose-down compose-shell compose-zsh compose-tmux lab-ssh vpn-require-dir vpn-up vpn-tun-check vpn-down vpn-list vpn-status vpn-connect vpn-disconnect vpn-switch vpn-doctor proxy-status proxy-doctor proxy-stop proxy-bridge security-check tailscale-check tf-fmt tf-plan-oci tf-apply-oci tf-destroy-oci tf-plan-azure tf-apply-azure tf-destroy-azure tf-plan-do tf-apply-do tf-destroy-do env-copy-oci env-copy-azure env-copy-do vpn-copy

ENV_FILE ?= .env
SECRETS_DIR ?= ./.secrets/runtime
WORKSPACE_DIR ?= ./workspace
VPN_DIR ?= ./vpn
VPN_MODE ?= inside
VPN_PROFILE ?= tryhackme
VPN_COMPOSE := -f compose.yaml -f compose.local.yaml
LAB_SSH_PORT ?= 2222
LAB_SSH_KEY ?= .secrets/ssh/seclab_ed25519
HOST_SSH_KEY ?= .secrets/ssh/seclab_ed25519
# CLOUD_HOST se puede dejar fijo en el .env para no repetirlo en cada
# llamada; si no esta, se acepta TF_HOST en la linea de comandos.
CLOUD_HOST ?= $(or $(TF_HOST),$(shell sed -n 's/^CLOUD_HOST=//p' "$(ENV_FILE)" 2>/dev/null))
CLOUD_SSH_PORT ?= 2222
CLOUD_REPO_DIR ?= ~/seclab-sbf
CLOUD_WORKSPACE_DIR ?= /opt/seclab-sbf/workspace
# Imagen publicada que usa el host cloud. Vacia = construye en el host.
# Recomendado: el digest inmutable que publica release.yml, por ejemplo
# ghcr.io/hackadvisermx/seclab-sbf@sha256:...
CLOUD_IMAGE ?=
LAB_SSH_HOST ?= 127.0.0.1
LAB_IMAGE ?= seclab-sbf:light
# Una referencia con "/" es un repositorio remoto (ghcr.io/host/repo:tag o
# @sha256:digest): esa se trae con docker pull, nunca se construye. Sin "/"
# es una imagen local y se construye como siempre.
LAB_IMAGE_REMOTE = $(if $(findstring /,$(LAB_IMAGE)),$(LAB_IMAGE))
LAB_IMAGE_LOCAL = $(if $(LAB_IMAGE_REMOTE),,$(if $(filter seclab-sbf:%,$(LAB_IMAGE)),$(LAB_IMAGE),seclab-sbf:$(LAB_IMAGE)))
LAB_IMAGE_RESOLVED = $(if $(LAB_IMAGE_REMOTE),$(LAB_IMAGE_REMOTE),$(LAB_IMAGE_LOCAL))
# El perfil lo determina la imagen: es lo que decide que herramientas
# estan instaladas. Sin esto, PENTEST_PROFILE del .env se queda en light
# aunque la imagen sea full y el banner no refleta lo que hay.
#
# Se deduce del nombre, y se puede pasar explicito para que tenga prioridad.
# Un digest remoto (ghcr.io/host/repo@sha256:...) no lleva el nombre del
# perfil, asi que no hay nada que deducir de el. Antes de adivinar light y
# perder Metasploit en silencio, check-profile lo corta.
LAB_PROFILE ?= $(if $(filter %:full %:full@sha256:%,$(LAB_IMAGE_RESOLVED)),full,light)
# $(origin) devuelve "command line" con espacio, asi que no se puede filtrar por
# esa cadena. Se da por pasado a mano cuando su origen no es el Makefile.
LAB_PROFILE_DADO = $(if $(filter environment file override,$(origin LAB_PROFILE)),,si)
# Digest remoto sin perfil deducible y sin perfil pasado a mano.
LAB_PROFILE_OPACO = $(and $(LAB_IMAGE_REMOTE),$(findstring @sha256:,$(LAB_IMAGE_REMOTE)),$(if $(LAB_PROFILE_DADO),,si))
COMPOSE_BASE := WORKSPACE_DIR="$(WORKSPACE_DIR)" LAB_ENV_FILE="$(ENV_FILE)" SECRETS_DIR="$(SECRETS_DIR)" LAB_IMAGE="$(LAB_IMAGE_RESOLVED)" PENTEST_PROFILE="$(LAB_PROFILE)" docker compose -f compose.yaml -f compose.local.yaml
COMPOSE_VPN := VPN_MODE="$(VPN_MODE)" VPN_DIR="$(VPN_DIR)" WORKSPACE_DIR="$(WORKSPACE_DIR)" LAB_ENV_FILE="$(ENV_FILE)" SECRETS_DIR="$(SECRETS_DIR)" LAB_IMAGE="$(LAB_IMAGE_RESOLVED)" PENTEST_PROFILE="$(LAB_PROFILE)" docker compose $(VPN_COMPOSE)

help:
	@printf '%s\n' 'Verificacion:' '  verify            Verificaciones locales (secretos, docker, shell)' '  verify-secrets    Gitleaks' '  lint-docker       Hadolint base/light/full' '  lint-shell        ShellCheck scripts' '  verify-pins      Cada uses: de los workflows apunta a un commit real' '  profile-info     Imagen y perfil efectivos, y si el perfil es deducible' '  scan-image        Escaneo local de CVEs de una imagen (SCAN_IMAGE, por defecto seclab-sbf:full)' 'Imagenes:' '  build-base        Imagen base' '  build-light       Imagen light' '  build-full        Imagen full (VM desechable)' 'Laboratorio (todo make objetivo-con-guiones):' '  compose-config    Valida compose.yaml' '  compose-up        Levanta tester, daemon VPN y tun0; no conecta tunel' '  compose-down      Detiene tester y daemon VPN' '  compose-shell     Bash como tester (depuracion)' '  compose-zsh       Zsh efimero (previsualizacion)' '  compose-tmux      Sesion tmux del servicio activo' '  lab-ssh           SSH a tester en un comando (LAB_IMAGE=light|full)' '  lab-ssh-cloud     SSH al contenedor del host cloud (CLOUD_HOST o TF_HOST)' '  lab-ssh-full      Atajo local para la imagen full' '  lab-ssh-cloud-full   Atajo cloud: recrea en full y entra' '  (CLOUD_IMAGE=... hace que el host descargue del registry en vez de construir)' '  base-check        Healthcheck efimero de la imagen base' 'VPN inside:' '  vpn-up            Asegura daemon/control VPN y tun0' '  vpn-tun-check     Comprueba /dev/net/tun, tun0, NET_ADMIN' '  vpn-down          Detiene el daemon VPN' '  vpn-list          Lista perfiles' '  vpn-status        Estado de la VPN' '  vpn-connect       Conecta VPN_PROFILE a demanda' '  vpn-disconnect    Desconecta la VPN' '  vpn-switch        Cambia al perfil VPN_PROFILE' '  vpn-doctor        Valida perfiles y capacidades' 'Proxy:' '  proxy-status      Estado de pt-forward' '  proxy-doctor      Valida route guard' '  proxy-stop        Detiene pt-forward y SOCKS5' '  proxy-bridge      Puente host-only (SERVICE=tcp|socks|web)' 'Seguridad:' '  security-check    Sintaxis nftables (Linux)' '  tailscale-check   Tailscale host-only (Linux)' 'Nube (TF_HOST=... para env-copy):' '  tf-fmt            Formato Terraform' '  tf-plan-*         Plan (oci|azure|do)' '  tf-apply-*        Aplica' '  tf-destroy-*      Destruye' '  env-copy-*        Copia .env por tailnet' '  vpn-copy          Copia perfiles .ovpn al host por tailnet' 'Variables: ENV_FILE WORKSPACE_DIR LAB_IMAGE VPN_* LAB_SSH_PORT LAB_SSH_KEY LAB_SSH_HOST HOST_SSH_KEY CLOUD_HOST CLOUD_SSH_PORT CLOUD_REPO_DIR CLOUD_WORKSPACE_DIR CLOUD_IMAGE TF_HOST'

verify: verify-secrets lint-docker lint-shell verify-pins

verify-secrets:
	gitleaks dir . --redact --no-banner --config .gitleaks.toml

# Trivy 0.74.0, la misma version que usaba el gate de release.
TRIVY_IMAGE := aquasec/trivy@sha256:62b1e65e8869bc4b4c6aa4fa2b21595256c7c2f6018a9d9ad61caf87187c1969
SCAN_IMAGE ?= $(LAB_IMAGE)
SCAN_SEVERITY ?= HIGH,CRITICAL
SCAN_IGNORE_UNFIXED ?= true

# Escaneo local de una imagen con el gate de CVEs. Cubre lo que ya no cubre
# CI: full no se publica en release.yml y se compila en el host, asi que su
# unica puerta de CVEs es esta. Por defecto la imagen local de full.
#   make scan-image
#   SCAN_IMAGE=ghcr.io/hackadvisermx/seclab-sbf@sha256:... make scan-image
#
# La imagen entra como tar por --input en vez de por stdin: trivy 0.74.0
# interpreta un "-" literal como nombre de fichero y falla. Y no se monta el
# socket de Docker en un contenedor, que el proyecto no permite.
# El tar pesa lo mismo que la imagen, asi que va a un directorio temporal
# configurable y se borra al terminar.
SCAN_TAR ?= $(CURDIR)/tmp/scan-image.tar
SCAN_KEEP_TAR ?= 0
SCAN_FORMAT ?= table

scan-image:
	@mkdir -p "$(dir $(SCAN_TAR))"
	docker save -o "$(SCAN_TAR)" "$(SCAN_IMAGE)"
	docker run --rm \
	  -v "$(dir $(SCAN_TAR))":/scan:ro \
	  -v "$(CURDIR)/security/trivy/.trivyignore.yaml:/ignore.yaml:ro" \
	  -v seclab-trivy-cache:/root/.cache/trivy \
	  $(TRIVY_IMAGE) image \
	  --input /scan/$(notdir $(SCAN_TAR)) \
	  --ignorefile /ignore.yaml \
	  --scanners vuln \
	  --severity "$(SCAN_SEVERITY)" \
	  --ignore-unfixed "$(SCAN_IGNORE_UNFIXED)" \
	  --format "$(SCAN_FORMAT)" \
	  --exit-code 1
	@if [ "$(SCAN_KEEP_TAR)" != "1" ]; then rm -f "$(SCAN_TAR)"; fi


# Un digest remoto no revela si la imagen es full o light. Adivinar light
# arrancaria el laboratorio sin Metasploit y sin avisar, que es peor que
# parar aqui. Se pide el perfil explicito.
check-profile:
	@if [ -n "$(LAB_PROFILE_OPACO)" ]; then \
		echo "ERROR: no se deduce el perfil de un digest remoto." >&2; \
		echo "       $(LAB_IMAGE_REMOTE)" >&2; \
		echo "       Si la imagen es full y se queda en light, el laboratorio" >&2; \
		echo "       arranca sin Metasploit y sin NetExec, sin ningun aviso." >&2; \
		echo "       Pasalo explicito:" >&2; \
		echo "         make compose-up LAB_IMAGE='$(LAB_IMAGE_REMOTE)' LAB_PROFILE=full" >&2; \
		exit 1; \
	fi

ensure-image: check-profile
	@IMG="$(LAB_IMAGE_RESOLVED)"; \
	if [ -n "$(LAB_IMAGE_REMOTE)" ]; then \
		if docker image inspect "$$IMG" >/dev/null 2>&1; then \
			printf 'imagen remota lista: %s\n' "$$IMG"; \
		else \
			printf 'descargando del registry: %s\n' "$$IMG"; \
			if ! docker pull "$$IMG"; then \
				printf 'no se pudo descargar %s. Si es una imagen propia, comprueba que este publicada y que el host tenga acceso.\n' "$$IMG" >&2; \
				exit 1; \
			fi; \
		fi; \
	elif docker image inspect "$$IMG" >/dev/null 2>&1; then \
		printf 'imagen lista: %s\n' "$$IMG"; \
		if [ "$$IMG" = "seclab-sbf:full" ]; then \
			base_id=$$(docker image inspect -f '{{.Id}}' "$(FULL_BASE)" 2>/dev/null || true); \
			built_from=$$(docker image inspect -f '{{index .Config.Labels "seclab.base"}}' "$$IMG" 2>/dev/null || true); \
			if [ -n "$$base_id" ] && [ "$$base_id" != "$$built_from" ]; then \
				printf 'aviso: %s se construyo sobre una base anterior; se reconstruye.\n' "$$IMG"; \
				$(MAKE) build-full; \
			fi; \
		fi; \
	else \
		printf 'imagen ausente, construyendo: %s\n' "$$IMG"; \
		case "$$IMG" in \
			seclab-sbf:base) $(MAKE) build-base ;; \
			seclab-sbf:light) $(MAKE) build-light ;; \
			seclab-sbf:full) $(MAKE) build-full ;; \
			*) printf 'LAB_IMAGE desconocida: %s (usa base|light|full)\n' "$$IMG" >&2; exit 2 ;; \
		esac; \
	fi

# La imagen base no trae sshd, ttyd ni usuario tester, asi que no admite
# sesion interactiva: se valida de forma efimera con su healthcheck.
base-check: ensure-image
	WORKSPACE_DIR="$(WORKSPACE_DIR)" LAB_ENV_FILE="$(ENV_FILE)" SECRETS_DIR="$(SECRETS_DIR)" LAB_IMAGE=seclab-sbf:base docker compose -f compose.yaml -f compose.local.yaml run --rm --entrypoint /usr/local/bin/base-healthcheck lab

lab-ssh: ensure-env vpn-require-dir ensure-image sync-secrets
	@mkdir -p tmp
	@printf 'services:\n  lab:\n    ports:\n      - "127.0.0.1:%s:2222"\n' "$(LAB_SSH_PORT)" > tmp/compose.ssh.yaml
	WORKSPACE_DIR="$(WORKSPACE_DIR)" LAB_ENV_FILE="$(ENV_FILE)" SECRETS_DIR="$(SECRETS_DIR)" LAB_IMAGE="$(LAB_IMAGE_RESOLVED)" PENTEST_PROFILE="$(LAB_PROFILE)" docker compose -f compose.yaml -f compose.local.yaml -f tmp/compose.ssh.yaml up -d lab
	ssh -o StrictHostKeyChecking=accept-new -i "$(LAB_SSH_KEY)" -p "$(LAB_SSH_PORT)" tester@$(LAB_SSH_HOST)

# Entrada directa al contenedor del host cloud. Ahi el puente lo publica
# el servicio systemd seclab-ssh-tailnet en la IP Tailscale, asi que no
# hace falta aplicar ningun override de puertos.
lab-ssh-cloud:
	@test -n "$(CLOUD_HOST)" || (printf 'CLOUD_HOST requerido: tailnet del host (ej. make lab-ssh-cloud TF_HOST=100.x.y.z)\n' >&2; exit 2)
	ssh -o StrictHostKeyChecking=accept-new -i "$(LAB_SSH_KEY)" -p "$(CLOUD_SSH_PORT)" tester@"$(CLOUD_HOST)"

# En el cloud la imagen no se elige al conectar: hay que recrear el
# contenedor en el host. Por eso el atajo remoto primero levanta el lab
# alla con la imagen pedida y despues entra.
lab-ssh-cloud-image:
	@test -n "$(CLOUD_HOST)" || (printf 'CLOUD_HOST requerido: tailnet del host\n' >&2; exit 2)
	@printf 'recreando el lab en el host con %s (puede tardar si hay que construir)\n' "$(LAB_IMAGE_RESOLVED)"
	ssh -o StrictHostKeyChecking=accept-new -i "$(HOST_SSH_KEY)" "$(TF_ADMIN)@$(CLOUD_HOST)" \
		'cd '"$(CLOUD_REPO_DIR)"' && WORKSPACE_DIR='"$(CLOUD_WORKSPACE_DIR)"' make compose-up LAB_IMAGE='"$(LAB_IMAGE_RESOLVED)"
	$(MAKE) lab-ssh-cloud

lab-ssh-full:
	@$(MAKE) lab-ssh LAB_IMAGE=seclab-sbf:full

lab-ssh-cloud-full:
	@$(MAKE) lab-ssh-cloud-image LAB_IMAGE=seclab-sbf:full

vpn-require-dir:
	@if [ ! -d "$(VPN_DIR)" ]; then \
		printf '%s\n' 'No existe $(VPN_DIR); crea el directorio y coloca perfiles .ovpn sanitizados.' >&2; \
		exit 1; \
	fi

# El daemon VPN vive dentro del contenedor lab (root, NET_ADMIN y
# /dev/net/tun). Las acciones de tester pasan por el socket Unix con
# vpn-control client; las comprobaciones que requieren root usan
# vpn-manager directamente.
VPN_CLIENT := $(COMPOSE_VPN) exec -T --user 1000:1000 lab /usr/local/bin/vpn-control client

vpn-up: ensure-env vpn-require-dir ensure-image sync-secrets
	$(COMPOSE_VPN) up -d lab
	$(COMPOSE_VPN) exec -T lab /bin/sh -c 'test -S /var/lib/seclab/vpn-control/control.sock && test -e /sys/class/net/tun0 && printf "%s\n" "vpn=ready tun0=present"'

vpn-tun-check: vpn-up
	$(COMPOSE_VPN) exec -T lab /bin/sh -c 'test -c /dev/net/tun && test -e /sys/class/net/tun0 && /usr/local/bin/vpn-manager status'

vpn-down: ensure-env
	$(VPN_CLIENT) disconnect

vpn-list: vpn-up
	$(VPN_CLIENT) list

vpn-status: vpn-up
	$(VPN_CLIENT) status

vpn-connect: vpn-up
	$(VPN_CLIENT) connect "$(VPN_PROFILE)"

vpn-disconnect: vpn-up
	$(VPN_CLIENT) disconnect

vpn-switch: vpn-up
	$(VPN_CLIENT) switch "$(VPN_PROFILE)"

vpn-doctor: vpn-up
	$(COMPOSE_VPN) exec -T lab /usr/local/bin/vpn-manager doctor

proxy-status: ensure-env
	$(COMPOSE_BASE) exec -T --user 1000:1000 lab /usr/local/bin/pt-forward status

proxy-doctor: ensure-env
	$(COMPOSE_BASE) exec -T --user 1000:1000 lab /usr/local/bin/pt-forward doctor

proxy-stop: ensure-env
	$(COMPOSE_BASE) exec -T --user 1000:1000 lab /usr/local/bin/pt-forward stop

proxy-bridge:
	/bin/sh scripts/host/pt-proxy-bridge.sh "$(SERVICE)" "$(HOST_PORT)" "$(CONTAINER_PORT)"

security-check:
	/bin/sh scripts/security/check-isolation.sh

tailscale-check:
	/bin/sh scripts/security/check-tailscale.sh

TF_STACK ?= oci
TF_HOST ?=
TF_ADMIN ?= ubuntu

tf-fmt:
	terraform fmt -check -recursive terraform/

tf-plan-oci:
	/bin/sh scripts/cloud/tf.sh oci plan

tf-apply-oci:
	/bin/sh scripts/cloud/tf.sh oci apply

tf-destroy-oci:
	/bin/sh scripts/cloud/tf.sh oci destroy

tf-plan-azure:
	/bin/sh scripts/cloud/tf.sh azure plan

tf-apply-azure:
	/bin/sh scripts/cloud/tf.sh azure apply

tf-destroy-azure:
	/bin/sh scripts/cloud/tf.sh azure destroy

tf-plan-do:
	/bin/sh scripts/cloud/tf.sh digitalocean plan

tf-apply-do:
	/bin/sh scripts/cloud/tf.sh digitalocean apply

tf-destroy-do:
	/bin/sh scripts/cloud/tf.sh digitalocean destroy

env-copy-oci:
	@test -n "$(TF_HOST)" || (printf 'TF_HOST requerido: tailnet del host\n' >&2; exit 2)
	scp -o StrictHostKeyChecking=accept-new -i "$(HOST_SSH_KEY)" "$(ENV_FILE)" "$(TF_ADMIN)@$(TF_HOST):~/seclab-sbf/.env"

env-copy-azure:
	@test -n "$(TF_HOST)" || (printf 'TF_HOST requerido: tailnet del host\n' >&2; exit 2)
	scp -o StrictHostKeyChecking=accept-new -i "$(HOST_SSH_KEY)" "$(ENV_FILE)" "$(TF_ADMIN)@$(TF_HOST):~/seclab-sbf/.env"

env-copy-do:
	@test -n "$(TF_HOST)" || (printf 'TF_HOST requerido: tailnet del host\n' >&2; exit 2)
	scp -o StrictHostKeyChecking=accept-new -i "$(HOST_SSH_KEY)" "$(ENV_FILE)" "$(TF_ADMIN)@$(TF_HOST):~/seclab-sbf/.env"

# Los .ovpn pueden traer usuario y contrasena en linea, asi que viajan
# por el tailnet igual que el .env y nunca se hornean en la imagen:
# release.yml publica las imagenes en ghcr.io.
vpn-copy:
	@test -n "$(TF_HOST)" || (printf 'TF_HOST requerido: tailnet del host\n' >&2; exit 2)
	@set -e; \
	profiles=$$(ls "$(VPN_DIR)"/*.ovpn 2>/dev/null || true); \
	if [ -z "$$profiles" ]; then \
		printf 'no hay perfiles .ovpn en %s\n' "$(VPN_DIR)" >&2; \
		exit 66; \
	fi; \
	for profile in $$profiles; do \
		if [ ! -s "$$profile" ]; then \
			printf 'perfil vacio, no se copia: %s\n' "$$profile" >&2; \
			exit 65; \
		fi; \
	done; \
	ssh -o StrictHostKeyChecking=accept-new -i "$(HOST_SSH_KEY)" "$(TF_ADMIN)@$(TF_HOST)" 'mkdir -p ~/seclab-sbf/vpn && chmod 700 ~/seclab-sbf/vpn'; \
	for profile in $$profiles; do \
		scp -o StrictHostKeyChecking=accept-new -i "$(HOST_SSH_KEY)" "$$profile" "$(TF_ADMIN)@$(TF_HOST):~/seclab-sbf/vpn/"; \
	done; \
	ssh -o StrictHostKeyChecking=accept-new -i "$(HOST_SSH_KEY)" "$(TF_ADMIN)@$(TF_HOST)" 'chmod 600 ~/seclab-sbf/vpn/*.ovpn; ls -l ~/seclab-sbf/vpn'
