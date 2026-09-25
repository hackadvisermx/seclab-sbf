SHELL := /bin/sh

.PHONY: help verify verify-secrets lint-docker lint-shell build-base build-light env-init keys ensure-env compose config up down shell zsh tmux vpn-require-dir vpn-up vpn-tun-check vpn-down vpn-list vpn-status vpn-connect vpn-disconnect vpn-switch vpn-doctor proxy-status proxy-doctor proxy-stop proxy-bridge security-check tailscale-check

ENV_FILE ?= .env
VPN_DIR ?= ./vpn
VPN_MODE ?= inside
VPN_IMAGE ?= seclab-sbf:light
VPN_PROFILE ?= tryhackme
VPN_COMPOSE := -f compose.yaml -f compose.local.yaml -f compose.vpn-inside.yaml

help:
	@printf '%s\n' 'verify         Ejecuta las verificaciones locales disponibles' 'verify-secrets Escanea secretos con Gitleaks' 'lint-docker    Ejecuta Hadolint sobre el Dockerfile base' 'lint-shell     Ejecuta ShellCheck sobre scripts versionados' 'build-base     Construye la imagen base' 'build-light    Construye la imagen light' 'env-init       Crea .env desde .env.example con permisos 600' 'keys           Genera una clave local para tester' 'compose config Valida compose.yaml' 'compose up     Levanta tester, daemon VPN y tun0; no conecta un túnel' 'compose down   Detiene tester y daemon VPN' 'compose shell  Abre Bash como tester para depuración' 'compose zsh    Abre Zsh efímero para previsualización' 'compose tmux   Entra a la sesión tmux del servicio activo' 'vpn-up         Asegura el daemon/control VPN y tun0; no conecta un túnel' 'vpn-tun-check  Comprueba /dev/net/tun, tun0, NET_ADMIN y estado inside' 'vpn-down       Detiene el daemon VPN interno' 'vpn-list       Lista perfiles VPN del modo inside' 'vpn-status     Muestra el estado de la VPN inside' 'vpn-connect    Conecta VPN_PROFILE a demanda dentro del contenedor' 'vpn-disconnect Desconecta la VPN activa' 'vpn-switch     Cambia al perfil VPN_PROFILE' 'vpn-doctor     Valida perfiles y capacidades VPN' 'proxy-status  Muestra el estado de pt-forward' 'proxy-doctor  Valida la route guard del proxy' 'proxy-stop    Detiene pt-forward y SOCKS5' 'proxy-bridge  Puente host-only 127.0.0.1 hacia pt-forward (SERVICE=tcp|socks|web)' 'security-check Valida la sintaxis nftables en Linux' 'tailscale-check Valida Tailscale host-only en Linux'

verify: verify-secrets lint-docker lint-shell

verify-secrets:
	gitleaks dir . --redact --no-banner --config .gitleaks.toml

lint-docker:
	hadolint images/base/Dockerfile images/light/Dockerfile

lint-shell:
	@for file in scripts/*.sh scripts/entrypoint/*.sh scripts/health/*.sh scripts/security/*.sh scripts/host/*.sh; do \
		if [ -f "$$file" ]; then shellcheck "$$file"; fi; \
	done

build-base:
	BUILDKIT_PROGRESS=plain docker buildx build --progress=plain --pull --file images/base/Dockerfile --tag seclab-sbf:base --load .

build-light: build-base
	BUILDKIT_PROGRESS=plain docker buildx build --progress=plain --build-arg BASE_IMAGE=seclab-sbf:base --file images/light/Dockerfile --tag seclab-sbf:light --load .

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

compose:
	@:

config: ensure-env vpn-require-dir
	LAB_ENV_FILE="$(ENV_FILE)" docker compose -f compose.yaml -f compose.local.yaml config --quiet
	VPN_IMAGE="$(VPN_IMAGE)" VPN_MODE="$(VPN_MODE)" VPN_DIR="$(VPN_DIR)" LAB_ENV_FILE="$(ENV_FILE)" docker compose $(VPN_COMPOSE) config --quiet

up: ensure-env vpn-require-dir build-light
	VPN_IMAGE="$(VPN_IMAGE)" VPN_MODE="$(VPN_MODE)" VPN_DIR="$(VPN_DIR)" LAB_ENV_FILE="$(ENV_FILE)" docker compose $(VPN_COMPOSE) up -d

down: ensure-env
	VPN_IMAGE="$(VPN_IMAGE)" VPN_MODE="$(VPN_MODE)" VPN_DIR="$(VPN_DIR)" LAB_ENV_FILE="$(ENV_FILE)" docker compose $(VPN_COMPOSE) down --remove-orphans


shell: ensure-env build-light
	LAB_ENV_FILE="$(ENV_FILE)" docker compose -f compose.yaml -f compose.local.yaml run --rm --user 1000:1000 --entrypoint /bin/bash lab

zsh: ensure-env build-light
	LAB_ENV_FILE="$(ENV_FILE)" docker compose -f compose.yaml -f compose.local.yaml run --rm -it --user 1000:1000 --entrypoint /usr/bin/zsh lab -il

tmux: ensure-env
	LAB_ENV_FILE="$(ENV_FILE)" docker compose -f compose.yaml -f compose.local.yaml exec -it --user 1000:1000 lab env SECLAB_TMUX=1 TERM=xterm-256color /usr/bin/tmux new-session -A -s pentest-lab /usr/bin/zsh -il

vpn-require-dir:
	@if [ ! -d "$(VPN_DIR)" ]; then \
		printf '%s\n' 'No existe $(VPN_DIR); crea el directorio y coloca perfiles .ovpn sanitizados.' >&2; \
		exit 1; \
	fi

vpn-up: ensure-env vpn-require-dir build-light
	VPN_IMAGE="$(VPN_IMAGE)" VPN_MODE="$(VPN_MODE)" VPN_DIR="$(VPN_DIR)" LAB_ENV_FILE="$(ENV_FILE)" docker compose $(VPN_COMPOSE) up -d vpn

vpn-tun-check: vpn-up
	VPN_IMAGE="$(VPN_IMAGE)" VPN_MODE="$(VPN_MODE)" VPN_DIR="$(VPN_DIR)" LAB_ENV_FILE="$(ENV_FILE)" docker compose $(VPN_COMPOSE) exec -T vpn /bin/sh -c 'test -c /dev/net/tun && test -e /sys/class/net/tun0 && /usr/local/bin/vpn-manager status'

vpn-down: ensure-env
	VPN_IMAGE="$(VPN_IMAGE)" VPN_MODE="$(VPN_MODE)" VPN_DIR="$(VPN_DIR)" LAB_ENV_FILE="$(ENV_FILE)" docker compose $(VPN_COMPOSE) rm -f -s vpn

vpn-list: vpn-up
	VPN_IMAGE="$(VPN_IMAGE)" VPN_MODE="$(VPN_MODE)" VPN_DIR="$(VPN_DIR)" LAB_ENV_FILE="$(ENV_FILE)" docker compose $(VPN_COMPOSE) exec -T vpn /usr/local/bin/vpn-manager list

vpn-status: vpn-up
	VPN_IMAGE="$(VPN_IMAGE)" VPN_MODE="$(VPN_MODE)" VPN_DIR="$(VPN_DIR)" LAB_ENV_FILE="$(ENV_FILE)" docker compose $(VPN_COMPOSE) exec -T vpn /usr/local/bin/vpn-manager status

vpn-connect: vpn-up
	VPN_IMAGE="$(VPN_IMAGE)" VPN_MODE="$(VPN_MODE)" VPN_DIR="$(VPN_DIR)" LAB_ENV_FILE="$(ENV_FILE)" docker compose $(VPN_COMPOSE) exec -T vpn /usr/local/bin/vpn-manager connect "$(VPN_PROFILE)"

vpn-disconnect: vpn-up
	VPN_IMAGE="$(VPN_IMAGE)" VPN_MODE="$(VPN_MODE)" VPN_DIR="$(VPN_DIR)" LAB_ENV_FILE="$(ENV_FILE)" docker compose $(VPN_COMPOSE) exec -T vpn /usr/local/bin/vpn-manager disconnect

vpn-switch: vpn-up
	VPN_IMAGE="$(VPN_IMAGE)" VPN_MODE="$(VPN_MODE)" VPN_DIR="$(VPN_DIR)" LAB_ENV_FILE="$(ENV_FILE)" docker compose $(VPN_COMPOSE) exec -T vpn /usr/local/bin/vpn-manager switch "$(VPN_PROFILE)"

vpn-doctor: vpn-up
	VPN_IMAGE="$(VPN_IMAGE)" VPN_MODE="$(VPN_MODE)" VPN_DIR="$(VPN_DIR)" LAB_ENV_FILE="$(ENV_FILE)" docker compose $(VPN_COMPOSE) exec -T vpn /usr/local/bin/vpn-manager doctor

proxy-status: ensure-env
	LAB_ENV_FILE="$(ENV_FILE)" docker compose -f compose.yaml -f compose.local.yaml exec -T --user 1000:1000 lab /usr/local/bin/pt-forward status

proxy-doctor: ensure-env
	LAB_ENV_FILE="$(ENV_FILE)" docker compose -f compose.yaml -f compose.local.yaml exec -T --user 1000:1000 lab /usr/local/bin/pt-forward doctor

proxy-stop: ensure-env
	LAB_ENV_FILE="$(ENV_FILE)" docker compose -f compose.yaml -f compose.local.yaml exec -T --user 1000:1000 lab /usr/local/bin/pt-forward stop

proxy-bridge:
	/bin/sh scripts/host/pt-proxy-bridge.sh "$(SERVICE)" "$(HOST_PORT)" "$(CONTAINER_PORT)"

security-check:
	/bin/sh scripts/security/check-isolation.sh

tailscale-check:
	/bin/sh scripts/security/check-tailscale.sh
