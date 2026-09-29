SHELL := /bin/sh

.PHONY: sync-secrets base-check scan-image sbom profile-info help verify verify-secrets lint-docker lint-shell build-base build-light build-full env-init keys ensure-env ensure-image compose config up down shell zsh tmux compose-config compose-up compose-down compose-shell compose-zsh compose-tmux lab-ssh lab-ssh-cloud lab-ssh-cloud-image lab-ssh-full lab-ssh-cloud-full rebuild-image vpn-require-dir vpn-up vpn-tun-check vpn-down vpn-list vpn-status vpn-connect vpn-disconnect vpn-switch vpn-doctor proxy-status proxy-doctor proxy-stop proxy-bridge security-check tailscale-check fail2ban-check tf-fmt tf-render-check tflint-check fail2ban-jail-check tf-plan-oci tf-apply-oci tf-destroy-oci tf-plan-azure tf-apply-azure tf-destroy-azure tf-plan-do tf-apply-do tf-destroy-do env-copy-oci env-copy-azure env-copy-do vpn-copy

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
# Todas las imagenes se construyen en caliente en la maquina que las usa:
# no hay registry, asi que no existe el caso de una referencia remota que
# haya que traer con docker pull. Un nombre sin prefijo se expande a la
# imagen local de ese perfil.
LAB_IMAGE_RESOLVED = $(if $(filter seclab-sbf:%,$(LAB_IMAGE)),$(LAB_IMAGE),seclab-sbf:$(LAB_IMAGE))
# El perfil lo determina la imagen: es lo que decide que herramientas
# estan instaladas. Sin esto, PENTEST_PROFILE del .env se queda en light
# aunque la imagen sea full y el banner no refleta lo que hay.
#
# Se deduce del nombre, y se puede pasar explicito para que tenga prioridad.
LAB_PROFILE ?= $(if $(filter %:full,$(LAB_IMAGE_RESOLVED)),full,light)
# $(origin) devuelve "command line" y "environment file" con espacio, asi que
# no se puede filtrar por esa cadena: el unico origen que NO es del usuario es
# "file" (esta misma asignacion del Makefile), asi que se descarta ese.
LAB_PROFILE_DADO = $(if $(filter-out file,$(origin LAB_PROFILE)),si,)
COMPOSE_BASE := WORKSPACE_DIR="$(WORKSPACE_DIR)" LAB_ENV_FILE="$(ENV_FILE)" SECRETS_DIR="$(SECRETS_DIR)" LAB_IMAGE="$(LAB_IMAGE_RESOLVED)" PENTEST_PROFILE="$(LAB_PROFILE)" docker compose -f compose.yaml -f compose.local.yaml
COMPOSE_VPN := VPN_MODE="$(VPN_MODE)" VPN_DIR="$(VPN_DIR)" WORKSPACE_DIR="$(WORKSPACE_DIR)" LAB_ENV_FILE="$(ENV_FILE)" SECRETS_DIR="$(SECRETS_DIR)" LAB_IMAGE="$(LAB_IMAGE_RESOLVED)" PENTEST_PROFILE="$(LAB_PROFILE)" docker compose $(VPN_COMPOSE)

help:
	@printf '%s\n' 'Verificacion:' '  verify            Verificaciones locales (secretos, docker, shell)' '  verify-secrets    Gitleaks' '  lint-docker       Hadolint base/light/full' '  lint-shell        ShellCheck scripts' '  verify-pins      Cada uses: de los workflows apunta a un commit real' '  profile-info     Imagen y perfil efectivos, y si el perfil es deducible' '  scan-image        Escaneo local de CVEs de una imagen (SCAN_IMAGE, por defecto LAB_IMAGE)' '  sbom              SBOM CycloneDX de la imagen, ligado a su hash de insumos' 'Imagenes:' '  build-base        Imagen base' '  build-light       Imagen light' '  build-full        Imagen full (VM desechable)' 'Laboratorio (todo make objetivo-con-guiones):' '  compose-config    Valida compose.yaml' '  compose-up        Levanta tester, daemon VPN y tun0; no conecta tunel' '  compose-down      Detiene tester y daemon VPN' '  compose-shell     Bash como tester (depuracion)' '  compose-zsh       Zsh efimero (previsualizacion)' '  compose-tmux      Sesion tmux del servicio activo' '  lab-ssh           SSH a tester en un comando (LAB_IMAGE=light|full)' '  lab-ssh-cloud     SSH al contenedor del host cloud (CLOUD_HOST o TF_HOST)' '  lab-ssh-full      Atajo local para la imagen full' '  lab-ssh-cloud-image Atajo cloud: construye en el host la imagen pedida y entra' '  base-check        Healthcheck efimero de la imagen base' 'VPN inside:' '  vpn-up            Asegura daemon/control VPN y tun0' '  vpn-tun-check     Comprueba /dev/net/tun, tun0, NET_ADMIN' '  vpn-down          Detiene el daemon VPN' '  vpn-list          Lista perfiles' '  vpn-status        Estado de la VPN' '  vpn-connect       Conecta VPN_PROFILE a demanda' '  vpn-disconnect    Desconecta la VPN' '  vpn-switch        Cambia al perfil VPN_PROFILE' '  vpn-doctor        Valida perfiles y capacidades' 'Proxy:' '  proxy-status      Estado de pt-forward' '  proxy-doctor      Valida route guard' '  proxy-stop        Detiene pt-forward y SOCKS5' '  proxy-bridge      Puente host-only (SERVICE=tcp|socks|web)' 'Seguridad:' '  security-check    Sintaxis nftables (Linux)' '  tailscale-check   Tailscale host-only (Linux)' '  fail2ban-check    Jail de sshd del host (Linux)' 'Nube (TF_HOST=... para env-copy):' '  tf-fmt            Formato Terraform' '  tf-render-check   Renderiza el cloud-init y valida el YAML' '  tflint-check      Linter de Terraform (requiere tflint)' '  fail2ban-jail-check  Jail de sshd validada con fail2ban (requiere Docker)' '  tf-plan-*         Plan (oci|azure|do)' '  tf-apply-*        Aplica' '  tf-destroy-*      Destruye' '  env-copy-*        Copia .env por tailnet' '  vpn-copy          Copia perfiles .ovpn al host por tailnet' 'Variables: ENV_FILE WORKSPACE_DIR LAB_IMAGE VPN_* LAB_SSH_PORT LAB_SSH_KEY LAB_SSH_HOST HOST_SSH_KEY CLOUD_HOST CLOUD_SSH_PORT CLOUD_REPO_DIR CLOUD_WORKSPACE_DIR TF_HOST'

verify: verify-secrets lint-docker lint-shell verify-pins

verify-secrets:
	gitleaks dir . --redact --no-banner --config .gitleaks.toml

# Trivy 0.74.0, la misma version que usaba el gate de release.
TRIVY_IMAGE := aquasec/trivy@sha256:62b1e65e8869bc4b4c6aa4fa2b21595256c7c2f6018a9d9ad61caf87187c1969
SCAN_IMAGE ?= $(LAB_IMAGE)
SCAN_SEVERITY ?= HIGH,CRITICAL
SCAN_IGNORE_UNFIXED ?= true
# El default de Trivy son 5 min por operacion, y con full se queda corto: las
# capas de SecLists, wordlists y exploitdb tardan mas y el scan muere con
# "context deadline exceeded", que parece un fallo de CVEs pero no lo es.
SCAN_TIMEOUT ?= 45m

verify-pins:
	@GH_TOKEN="$$(gh auth token 2>/dev/null || true)" ./scripts/verify/check-action-pins.sh

lint-docker:
	hadolint images/base/Dockerfile images/light/Dockerfile images/full/Dockerfile

lint-shell:
	@for file in scripts/*.sh scripts/entrypoint/*.sh scripts/health/*.sh scripts/security/*.sh scripts/host/*.sh scripts/cloud/*.sh scripts/verify/*.sh; do \
		if [ -f "$$file" ]; then shellcheck "$$file"; fi; \
	done

build-base:
	BUILDKIT_PROGRESS=plain docker buildx build --progress=plain --pull --file images/base/Dockerfile --label seclab.build-inputs=$(BUILD_INPUTS) --tag seclab-sbf:base --load .

build-light: build-base
	BUILDKIT_PROGRESS=plain docker buildx build --progress=plain --build-arg BASE_IMAGE=seclab-sbf:base --file images/light/Dockerfile --label seclab.build-inputs=$(BUILD_INPUTS) --tag seclab-sbf:light --load .

FULL_BASE ?= seclab-sbf:light

build-full: build-light
	BUILDKIT_PROGRESS=plain docker buildx build --progress=plain --build-arg FULL_BASE="$(FULL_BASE)" --file images/full/Dockerfile --label seclab.base=$$(docker image inspect -f "{{.Id}}" "$(FULL_BASE)") --label seclab.build-inputs=$(BUILD_INPUTS) --tag seclab-sbf:full --load .

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
# Diagnostico: que imagen y perfil entran, y de donde sale el perfil. Util
# cuando algo arranca sin las herramientas esperadas.
profile-info:
	@echo "LAB_IMAGE          = $(LAB_IMAGE)"
	@echo "LAB_IMAGE_RESOLVED = $(LAB_IMAGE_RESOLVED)"
	@echo "origen             = local (build en caliente)"
	@echo "LAB_PROFILE        = $(LAB_PROFILE)"
	@echo "perfil             = $(if $(LAB_PROFILE_DADO),pasado a mano,deducido del nombre de la imagen)"

TRIVY_IMAGE := aquasec/trivy@sha256:62b1e65e8869bc4b4c6aa4fa2b21595256c7c2f6018a9d9ad61caf87187c1969

# Escaneo local de una imagen con el gate de CVEs. Sin registry, esta es la
# unica puerta de CVEs del proyecto: cada imagen se revisa aqui despues de
# construirse en caliente y antes de usarse. Por defecto la imagen local.
#   make scan-image
#   SCAN_IMAGE=seclab-sbf:light make scan-image
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
	  --timeout "$(SCAN_TIMEOUT)" \
	  --format "$(SCAN_FORMAT)" \
	  --exit-code 1
	@if [ "$(SCAN_KEEP_TAR)" != "1" ]; then rm -f "$(SCAN_TAR)"; fi


# SBOM de la imagen local en CycloneDX, con Trivy y el mismo digest
# pinneado que el gate de CVEs. El hash de insumos va en el nombre del
# artefacto: asi el SBOM queda ligado al codigo del que salio la imagen
# y no solo a su nombre, que se puede reutilizar. Sin la etiqueta
# seclab.build-inputs no se genera nada, porque un SBOM sin trazabilidad
# de insumos no cumple el criterio de plan.md.
#
# El directorio es tmp/, que esta en .gitignore: un SBOM de full pesa
# varios MB y no tiene sentido versionarlo.
SBOM_DIR ?= $(CURDIR)/tmp/sbom
SBOM_FORMAT ?= cyclonedx

sbom:
	@inputs="$$(docker image inspect -f '{{ index .Config.Labels "seclab.build-inputs" }}' "$(SCAN_IMAGE)" 2>/dev/null)"; \
	if [ -z "$$inputs" ]; then \
		printf 'sbom: la imagen %s no tiene la etiqueta seclab.build-inputs; reconstruir con make build-*\n' "$(SCAN_IMAGE)" >&2; \
		exit 1; \
	fi; \
	name="$$(printf '%s' "$(SCAN_IMAGE)" | tr ':/' '--')-$$inputs.json"; \
	mkdir -p "$(SBOM_DIR)"; \
	rm -f "$(SBOM_DIR)/$$name"; \
	docker save -o "$(SCAN_TAR)" "$(SCAN_IMAGE)"; \
	docker run --rm \
	  -v "$(dir $(SCAN_TAR))":/scan:ro \
	  -v "$(SBOM_DIR)":/sbom \
	  -v seclab-trivy-cache:/root/.cache/trivy \
	  $(TRIVY_IMAGE) image \
	  --input /scan/$(notdir $(SCAN_TAR)) \
	  --scanners vuln \
	  --format "$(SBOM_FORMAT)" \
	  --output "/sbom/$$name" \
	  --timeout "$(SCAN_TIMEOUT)"; \
	st=$$?; \
	rm -f "$(SCAN_TAR)"; \
	if [ "$$st" -ne 0 ]; then exit "$$st"; fi; \
	image_id="$$(docker image inspect -f '{{.Id}}' "$(SCAN_IMAGE)")"; \
	sum="$$(shasum -a 256 "$(SBOM_DIR)/$$name" | cut -d' ' -f1)"; \
	if command -v python3 >/dev/null 2>&1; then \
		python3 -c 'import json,sys; json.load(open(sys.argv[1]))' "$(SBOM_DIR)/$$name" \
		  || { printf 'sbom: %s no es JSON valido\n' "$(SBOM_DIR)/$$name" >&2; exit 1; }; \
		parsed=ok; \
	else \
		parsed=skipped; \
	fi; \
	printf 'sbom: %s\n  imagen=%s\n  image_id=%s\n  build_inputs=%s\n  sha256=%s\n  json=%s\n' \
	  "$(SBOM_DIR)/$$name" "$(SCAN_IMAGE)" "$$image_id" "$$inputs" "$$sum" "$$parsed"


# Hash de los ficheros que entran en la imagen. Se graba como etiqueta al
# construir, y ensure-image lo compara con el de la imagen que hay en disco.
# Si no coinciden, el codigo cambio desde la ultima build y hay que
# reconstruir. Sin esto, sincronizar el repo e invocar un target reutilizaba
# en silencio la imagen anterior: con full son 4 GB de diferencia.
# Se pasan a proposito todos los directorios que可以在 el contexto, para
# errar hacia reconstruir de mas antes que hacia dejar una imagen vieja.
BUILD_INPUT_DIRS = images scripts shell security supply-chain
BUILD_INPUT_FILES = .tmux.conf
BUILD_INPUTS = $(shell { find $(BUILD_INPUT_DIRS) -type f 2>/dev/null; echo $(BUILD_INPUT_FILES); } | sort | xargs shasum -a 256 2>/dev/null | shasum -a 256 | cut -c1-16)

# Reconstruye la imagen local indicada. Lo usan ensure-image cuando falta o
# cuando el codigo ha cambiado, para no repetir el case en dos sitios.
rebuild-image:
	@case "$(LAB_IMAGE_RESOLVED)" in \
		seclab-sbf:base) $(MAKE) build-base ;; \
		seclab-sbf:light) $(MAKE) build-light ;; \
		seclab-sbf:full) $(MAKE) build-full ;; \
		*) printf 'LAB_IMAGE desconocida: %s (usa base|light|full)\n' "$(LAB_IMAGE_RESOLVED)" >&2; exit 2 ;; \
	esac

ensure-image:
	@IMG="$(LAB_IMAGE_RESOLVED)"; \
	if docker image inspect "$$IMG" >/dev/null 2>&1; then \
		built_inputs=$$(docker image inspect -f '{{index .Config.Labels "seclab.build-inputs"}}' "$$IMG" 2>/dev/null || true); \
		if [ -z "$$built_inputs" ] || [ "$$built_inputs" = "<no value>" ]; then \
			printf 'imagen sin etiqueta de insumos, se reconstruye: %s\n' "$$IMG"; \
			$(MAKE) rebuild-image; \
		elif [ "$$built_inputs" != "$(BUILD_INPUTS)" ]; then \
			printf 'el codigo cambio desde la build ($$built_inputs -> $(BUILD_INPUTS)), se reconstruye: %s\n' "$$IMG"; \
			$(MAKE) rebuild-image; \
		else \
		printf 'imagen lista: %s\n' "$$IMG"; \
		fi; \
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
		$(MAKE) rebuild-image; \
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

fail2ban-check:
	/bin/sh scripts/security/check-fail2ban.sh

TF_STACK ?= oci
TF_HOST ?=
TF_ADMIN ?= ubuntu

tf-fmt:
	terraform fmt -check -recursive terraform/

tf-render-check:
	/bin/sh scripts/verify/check-tf-render.sh

# Solo el ruleset terraform que va embebido en el binario, sin plugins
# del registro. Sin tflint instalado se sale con 78 y el comando para
# obtenerlo, como el resto de checks.
tflint-check:
	@command -v tflint >/dev/null 2>&1 || { \
	  printf '%s\n' 'tflint_check=unavailable command=tflint (brew install tflint)'; \
	  exit 78; \
	}
	@for stack in oci azure digitalocean; do \
	  printf '== %s ==\n' "$$stack"; \
	  tflint --chdir="terraform/stacks/$$stack" || exit 1; \
	done
	@printf '%s\n' 'tflint_check=ok config=.tflint.hcl'

# Valida la jail de fail2ban con el propio fail2ban, en un contenedor
# desechable. No levanta ninguna jail ni toca nftables: solo parsea la
# configuracion y pasa dos logs por el filtro de sshd. El ban efectivo
# sigue siendo cosa del host, con make fail2ban-check.
fail2ban-jail-check:
	/bin/sh scripts/verify/check-fail2ban-jail.sh

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
# por el tailnet igual que el .env y nunca se hornean en la imagen: cada
# maquina construye la suya y el perfil se monta en /vpn.
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
