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
LAB_SSH_HOST ?= 127.0.0.1
LAB_IMAGE ?= seclab-sbf:light
LAB_IMAGE_NORMALIZED = $(if $(filter seclab-sbf:%,$(LAB_IMAGE)),$(LAB_IMAGE),seclab-sbf:$(LAB_IMAGE))
# El perfil lo determina la imagen: es lo que decide que herramientas
# estan instaladas. Sin esto, PENTEST_PROFILE del .env se queda en light
# aunque la imagen sea full y el banner no refleta lo que hay.
LAB_PROFILE = $(if $(filter seclab-sbf:full,$(LAB_IMAGE_NORMALIZED)),full,light)
COMPOSE_BASE := WORKSPACE_DIR="$(WORKSPACE_DIR)" LAB_ENV_FILE="$(ENV_FILE)" SECRETS_DIR="$(SECRETS_DIR)" LAB_IMAGE="$(LAB_IMAGE_NORMALIZED)" PENTEST_PROFILE="$(LAB_PROFILE)" docker compose -f compose.yaml -f compose.local.yaml
COMPOSE_VPN := VPN_MODE="$(VPN_MODE)" VPN_DIR="$(VPN_DIR)" WORKSPACE_DIR="$(WORKSPACE_DIR)" LAB_ENV_FILE="$(ENV_FILE)" SECRETS_DIR="$(SECRETS_DIR)" LAB_IMAGE="$(LAB_IMAGE_NORMALIZED)" PENTEST_PROFILE="$(LAB_PROFILE)" docker compose $(VPN_COMPOSE)

help:
	@printf '%s\n' 'Verificacion:' '  verify            Verificaciones locales (secretos, docker, shell)' '  verify-secrets    Gitleaks' '  lint-docker       Hadolint base/light/full' '  lint-shell        ShellCheck scripts' 'Imagenes:' '  build-base        Imagen base' '  build-light       Imagen light' '  build-full        Imagen full (VM desechable)' 'Laboratorio (todo make objetivo-con-guiones):' '  compose-config    Valida compose.yaml' '  compose-up        Levanta tester, daemon VPN y tun0; no conecta tunel' '  compose-down      Detiene tester y daemon VPN' '  compose-shell     Bash como tester (depuracion)' '  compose-zsh       Zsh efimero (previsualizacion)' '  compose-tmux      Sesion tmux del servicio activo' '  lab-ssh           SSH a tester en un comando (LAB_IMAGE=light|full)' '  lab-ssh-cloud     SSH al contenedor del host cloud (CLOUD_HOST o TF_HOST)' '  lab-ssh-full      Atajo local para la imagen full' '  lab-ssh-cloud-full   Atajo cloud: recrea en full y entra' '  base-check        Healthcheck efimero de la imagen base' 'VPN inside:' '  vpn-up            Asegura daemon/control VPN y tun0' '  vpn-tun-check     Comprueba /dev/net/tun, tun0, NET_ADMIN' '  vpn-down          Detiene el daemon VPN' '  vpn-list          Lista perfiles' '  vpn-status        Estado de la VPN' '  vpn-connect       Conecta VPN_PROFILE a demanda' '  vpn-disconnect    Desconecta la VPN' '  vpn-switch        Cambia al perfil VPN_PROFILE' '  vpn-doctor        Valida perfiles y capacidades' 'Proxy:' '  proxy-status      Estado de pt-forward' '  proxy-doctor      Valida route guard' '  proxy-stop        Detiene pt-forward y SOCKS5' '  proxy-bridge      Puente host-only (SERVICE=tcp|socks|web)' 'Seguridad:' '  security-check    Sintaxis nftables (Linux)' '  tailscale-check   Tailscale host-only (Linux)' 'Nube (TF_HOST=... para env-copy):' '  tf-fmt            Formato Terraform' '  tf-plan-*         Plan (oci|azure|do)' '  tf-apply-*        Aplica' '  tf-destroy-*      Destruye' '  env-copy-*        Copia .env por tailnet' '  vpn-copy          Copia perfiles .ovpn al host por tailnet' 'Variables: ENV_FILE WORKSPACE_DIR LAB_IMAGE VPN_* LAB_SSH_PORT LAB_SSH_KEY LAB_SSH_HOST HOST_SSH_KEY CLOUD_HOST CLOUD_SSH_PORT CLOUD_REPO_DIR CLOUD_WORKSPACE_DIR TF_HOST'

verify: verify-secrets lint-docker lint-shell

verify-secrets:
	gitleaks dir . --redact --no-banner --config .gitleaks.toml

lint-docker:
	hadolint images/base/Dockerfile images/light/Dockerfile images/full/Dockerfile

lint-shell:
	@for file in scripts/*.sh scripts/entrypoint/*.sh scripts/health/*.sh scripts/security/*.sh scripts/host/*.sh scripts/cloud/*.sh; do \
		if [ -f "$$file" ]; then shellcheck "$$file"; fi; \
	done

build-base:
	BUILDKIT_PROGRESS=plain docker buildx build --progress=plain --pull --file images/base/Dockerfile --tag seclab-sbf:base --load .

build-light: build-base
	BUILDKIT_PROGRESS=plain docker buildx build --progress=plain --build-arg BASE_IMAGE=seclab-sbf:base --file images/light/Dockerfile --tag seclab-sbf:light --load .

FULL_BASE ?= seclab-sbf:light

build-full: build-light
	BUILDKIT_PROGRESS=plain docker buildx build --progress=plain --build-arg FULL_BASE="$(FULL_BASE)" --file images/full/Dockerfile --label seclab.base=$$(docker image inspect -f "{{.Id}}" "$(FULL_BASE)") --tag seclab-sbf:full --load .

env-init:
	@if [ -e "$(ENV_FILE)" ]; then \
		printf '%s ya existe; no se sobrescribió\n' "$(ENV_FILE)" >&2; \
		exit 1; \
	fi
	@cp .env.example "$(ENV_FILE)"
	@chmod 600 "$(ENV_FILE)"
	@case "$(ENV_FILE)" in *.example) ;; *) SECLAB_ENV_FILE="$(ENV_FILE)" /bin/sh scripts/generate-keys.sh ;; esac
	@printf 'creado %s desde .env.example\n' "$(ENV_FILE)"

ensure-env:
	@if [ ! -e "$(ENV_FILE)" ]; then \
		cp .env.example "$(ENV_FILE)"; \
		chmod 600 "$(ENV_FILE)"; \
		printf 'creado %s desde .env.example\n' "$(ENV_FILE)"; \
	fi
	@if [ "$(ENV_FILE)" = ".env" ]; then chmod 600 "$(ENV_FILE)"; fi
	@case "$(ENV_FILE)" in *.example) ;; *) SECLAB_ENV_FILE="$(ENV_FILE)" /bin/sh scripts/generate-keys.sh ;; esac

keys: ensure-env

# Copia el archivo de secretos a un directorio montado en el contenedor.
# Se monta el directorio y no el archivo porque un editor que guarda de
# forma atomica (escribe temporal y renombra) cambia el inode del
# archivo y deja colgando cualquier bind mount de un archivo suelto.
sync-secrets:
	@case "$(ENV_FILE)" in \
		*.example) exit 0 ;; \
	esac
	@mkdir -p "$(SECRETS_DIR)"
	@chmod 700 "$(SECRETS_DIR)"
	@cp "$(ENV_FILE)" "$(SECRETS_DIR)/lab.env"
	@chmod 600 "$(SECRETS_DIR)/lab.env"
	@awk -v profile="$(LAB_PROFILE)" '/^PENTEST_PROFILE=/ { print "PENTEST_PROFILE=" profile; seen = 1; next } { print } END { if (!seen) print "PENTEST_PROFILE=" profile }' "$(SECRETS_DIR)/lab.env" > "$(SECRETS_DIR)/lab.env.tmp"
	@chmod 600 "$(SECRETS_DIR)/lab.env.tmp"
	@mv "$(SECRETS_DIR)/lab.env.tmp" "$(SECRETS_DIR)/lab.env"

compose:
	@:

# Forma canonica con guiones; 'up', 'down', 'shell', 'zsh', 'tmux' y
# 'config' se conservan como alias para compatibilidad.
config: compose-config

compose-config: ensure-env vpn-require-dir
	$(COMPOSE_BASE) config --quiet
	$(COMPOSE_VPN) config --quiet

up: compose-up

compose-up: ensure-env vpn-require-dir ensure-image sync-secrets
	$(COMPOSE_VPN) up -d

down: compose-down

compose-down: ensure-env
	$(COMPOSE_VPN) down --remove-orphans


shell: compose-shell

compose-shell: ensure-env ensure-image sync-secrets
	$(COMPOSE_BASE) run --rm --user 1000:1000 --entrypoint /bin/bash lab

zsh: compose-zsh

compose-zsh: ensure-env ensure-image sync-secrets
	$(COMPOSE_BASE) run --rm -it --user 1000:1000 --entrypoint /usr/bin/zsh lab -il

tmux: compose-tmux

compose-tmux: ensure-env sync-secrets
	$(COMPOSE_BASE) exec -it --user 1000:1000 lab env SECLAB_TMUX=1 TERM=xterm-256color /usr/bin/tmux new-session -A -s pentest-lab /usr/bin/zsh -il

# SSH al contenedor en un comando: publica 127.0.0.1:LAB_SSH_PORT
# via override temporal en tmp/ (ignorado, sin tocar compose.yaml)
# y entra como tester. LAB_IMAGE elige base/light/full (default light)
# y solo construye si la imagen no existe. En el host cloud antepone
# WORKSPACE_DIR=/opt/seclab-sbf/workspace.
# SSH al contenedor en un comando: publica 127.0.0.1:LAB_SSH_PORT
# via override temporal en tmp/ (ignorado, sin tocar compose.yaml)
# y entra como tester. LAB_IMAGE elige base|light|full (default light)
# y solo construye si la imagen no existe. En el host cloud antepone
# WORKSPACE_DIR=/opt/seclab-sbf/workspace.
ensure-image:
	@IMG="$(LAB_IMAGE_NORMALIZED)"; \
	if docker image inspect "$$IMG" >/dev/null 2>&1; then \
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
	WORKSPACE_DIR="$(WORKSPACE_DIR)" LAB_ENV_FILE="$(ENV_FILE)" SECRETS_DIR="$(SECRETS_DIR)" LAB_IMAGE="$(LAB_IMAGE_NORMALIZED)" PENTEST_PROFILE="$(LAB_PROFILE)" docker compose -f compose.yaml -f compose.local.yaml -f tmp/compose.ssh.yaml up -d lab
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
	@printf 'recreando el lab en el host con %s (puede tardar si hay que construir)\n' "$(LAB_IMAGE_NORMALIZED)"
	ssh -o StrictHostKeyChecking=accept-new -i "$(HOST_SSH_KEY)" "$(TF_ADMIN)@$(CLOUD_HOST)" \
		'cd '"$(CLOUD_REPO_DIR)"' && WORKSPACE_DIR='"$(CLOUD_WORKSPACE_DIR)"' make compose-up LAB_IMAGE='"$(LAB_IMAGE_NORMALIZED)"
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
