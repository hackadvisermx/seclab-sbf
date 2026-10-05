SHELL := /bin/sh

# --- arranque desde cualquier carpeta -------------------------------
#
# Make no puede cambiar su propio directorio: cada receta corre en una shell
# nueva y make sigue en el directorio desde el que se lanzo. Como todo el
# repo tiene rutas relativas (compose, scripts, Dockerfiles), `make` solo
# funcionaba desde la raiz.
#
# Cada receta empieza con `cd "$(ROOT)" &&`, y con eso da igual desde donde se
# llame: `make -f /ruta/al/Makefile compose-up` funciona igual que `make
# compose-up` en la raiz. Solo se prefijan los INICIOS de linea logica; las
# continuaciones con backslash son la misma orden de shell y no se tocan.
#
# Se descarto re-invocarse con `$(MAKE) -C` porque Make no deja reescribir
# la lista de objetivos: `MAKECMDGOALS :=` se ignora, asi que solounia el
# caso de `make` sin argumentos y no los `make compose-up`. Comprobado.
ROOT := $(patsubst %/,%,$(dir $(abspath $(lastword $(MAKEFILE_LIST)))))

.PHONY: workspace-dir workspace-list workspace-export workspace-backup workspace-restore compose-refs-check sync-secrets base-check scan-image sbom help verify verify-secrets lint-docker lint-shell build-base build-full env-init keys ensure-env ensure-image compose config up down shell zsh tmux compose-config compose-up compose-down compose-shell compose-zsh compose-tmux lab-ports lab-ssh lab-ssh-cloud host-ssh-cloud lab-ssh-azure host-ssh-azure lab-ssh-az host-ssh-az lab-ssh-oci host-ssh-oci vm-status-azure vm-status-az vm-stop-azure vm-stop-az vm-start-azure vm-start-az lab-ssh-cloud-image rebuild-image vpn-require-dir vpn-up vpn-tun-check vpn-down vpn-list vpn-status vpn-connect vpn-disconnect vpn-switch vpn-doctor proxy-status proxy-doctor proxy-stop proxy-bridge security-check tailscale-check fail2ban-check tf-fmt tf-render-check tflint-check fail2ban-jail-check doc-targets-check tf-destroy-check tf-plan-oci tf-apply-oci tf-destroy-oci tf-plan-azure tf-apply-azure tf-destroy-azure tf-plan-do tf-apply-do tf-destroy-do env-copy-oci env-copy-azure env-copy-do vpn-copy image-publish image-publish-checked image-pull image-tools-check smoke-test python-units-check py-test compose-security-check dashboard dashboard-build dashboard-up dashboard-daemon dashboard-stop dashboard-status

ENV_FILE ?= .env
SECRETS_DIR ?= ./.secrets/runtime
WORKSPACE_DIR ?= ./workspace
# Destino de `make workspace-export`. Fuera del repo a proposito: el
# workspace contiene notas de engagement y material de clientes, y no
# debe acabar en un directorio que alguien верa a versionar sin querer.
DEST ?= ./salida
BACKUP_DEST ?= ./backups
BACKUP ?=
FORCE ?= 0
VPN_DIR ?= ./vpn
VPN_MODE ?= inside
VPN_PROFILE ?= tryhackme
VPN_COMPOSE := -f compose.yaml -f compose.local.yaml
LAB_SSH_PORT ?= 2222
LAB_TTYD_PORT ?= 7681
LAB_DASHBOARD_PORT ?= 8080
LAB_SSH_KEY ?= .secrets/ssh/seclab_ed25519
HOST_SSH_KEY ?= .secrets/ssh/seclab_ed25519
# CLOUD_HOST se puede dejar fijo en el .env para no repetirlo en cada
# llamada; si no esta, se acepta TF_HOST en la linea de comandos.
CLOUD_HOST ?= $(or $(TF_HOST),$(shell sed -n 's/^CLOUD_HOST=//p' "$(ENV_FILE)" 2>/dev/null))
AZURE_HOST ?= $(or $(TF_HOST),$(shell sed -n 's/^AZURE_HOST=//p' "$(ENV_FILE)" 2>/dev/null),$(CLOUD_HOST))
OCI_HOST ?= $(or $(TF_HOST),$(shell sed -n 's/^OCI_HOST=//p' "$(ENV_FILE)" 2>/dev/null))
CLOUD_SSH_PORT ?= 2222
CLOUD_REPO_DIR ?= ~/seclab-sbf
CLOUD_WORKSPACE_DIR ?= /opt/seclab-sbf/workspace
LAB_SSH_HOST ?= 127.0.0.1
LAB_IMAGE ?= seclab-sbf:full
# Todas las imagenes se construyen en caliente en la maquina que las usa:
# no hay registry, asi que no existe el caso de una referencia remota que
# haya que traer con docker pull. Un nombre sin prefijo se expande a la
# imagen local de ese perfil.
LAB_IMAGE_RESOLVED = $(if $(filter seclab-sbf:%,$(LAB_IMAGE)),$(LAB_IMAGE),seclab-sbf:$(LAB_IMAGE))
COMPOSE_BASE := WORKSPACE_DIR="$(WORKSPACE_DIR)" LAB_ENV_FILE="$(ENV_FILE)" SECRETS_DIR="$(SECRETS_DIR)" LAB_IMAGE="$(LAB_IMAGE_RESOLVED)" docker compose -f compose.yaml -f compose.local.yaml
COMPOSE_VPN := VPN_MODE="$(VPN_MODE)" VPN_DIR="$(VPN_DIR)" WORKSPACE_DIR="$(WORKSPACE_DIR)" LAB_ENV_FILE="$(ENV_FILE)" SECRETS_DIR="$(SECRETS_DIR)" LAB_IMAGE="$(LAB_IMAGE_RESOLVED)" docker compose $(VPN_COMPOSE)

help:
	@cd "$(ROOT)" && printf '%s\n' 'Verificacion:' '  verify            Verificaciones locales (secretos, docker, shell)' '  verify-secrets    Gitleaks' '  lint-docker       Hadolint base y full' '  lint-shell        ShellCheck scripts' '  verify-pins      Cada uses: de los workflows apunta a un commit real' '  python-units-check Pruebas de seguridad proxy/VPN (py-test)' '  scan-image        Escaneo local de CVEs de una imagen (SCAN_IMAGE, por defecto LAB_IMAGE)' '  sbom              SBOM CycloneDX de la imagen, ligado a su hash de insumos' 'Imagenes:' '  build-base        Imagen base' '  build-full        Imagen del laboratorio (la unica)' '  image-publish    Publica la imagen en Docker Hub (no escanea)' '  image-publish-checked Publica despues de pasar el gate de CVEs' '  image-pull       Baja la imagen por digest (DOCKER_DIGEST) y la deja lista' 'Laboratorio (todo make objetivo-con-guiones):' '  compose-config    Valida compose.yaml' '  compose-up        Levanta tester, daemon VPN y tun0; no conecta tunel' '  compose-down      Detiene tester y daemon VPN' '  compose-shell     Bash como tester (depuracion)' '  compose-zsh       Zsh efimero (previsualizacion)' '  compose-tmux      Sesion tmux del servicio activo' '  workspace-dir    Crea la carpeta de trabajo y la siembra si esta vacia' '  workspace-list   Ver que hay en el workspace' '  workspace-export Saca material del workspace (RUTA= | ENG= | ALL=1)' '  workspace-backup Empaqueta el workspace con timestamp y checksum SHA-256' '  workspace-restore Restaura un respaldo en el workspace (BACKUP=... [FORCE=1])' '  lab-ssh           SSH a tester en un comando' '  lab-ssh-cloud     SSH al contenedor del host cloud (CLOUD_HOST o TF_HOST)' '  host-ssh-cloud    SSH al host cloud como ubuntu (CLOUD_HOST o TF_HOST)' '  lab-ssh-cloud-image Atajo cloud: construye en el host la imagen pedida y entra' '  base-check        Healthcheck efimero de la imagen base' '  smoke-test        Pruebas de humo funcionales en contenedor efimero' 'VPN inside:' '  vpn-up            Asegura daemon/control VPN y tun0' '  vpn-tun-check     Comprueba /dev/net/tun, tun0, NET_ADMIN' '  vpn-down          Detiene el daemon VPN' '  vpn-list          Lista perfiles' '  vpn-status        Estado de la VPN' '  vpn-connect       Conecta VPN_PROFILE a demanda' '  vpn-disconnect    Desconecta la VPN' '  vpn-switch        Cambia al perfil VPN_PROFILE' '  vpn-doctor        Valida perfiles y capacidades' 'Proxy:' '  proxy-status      Estado de pt-forward' '  proxy-doctor      Valida route guard' '  proxy-stop        Detiene pt-forward y SOCKS5' '  proxy-bridge      Puente host-only (SERVICE=tcp|socks|web)' 'Seguridad:' '  security-check    Sintaxis nftables (Linux)' '  tailscale-check   Tailscale host-only (Linux)' '  fail2ban-check    Jail de sshd del host (Linux)' 'Nube (TF_HOST=... para env-copy):' '  tf-fmt            Formato Terraform' '  tf-render-check   Renderiza el cloud-init y valida el YAML' '  tflint-check      Linter de Terraform (requiere tflint)' '  fail2ban-jail-check  Jail de sshd validada con fail2ban (requiere Docker)' '  makefile-check       Recetas del Makefile con comillas balanceadas' '  image-tools-check   Herramientas del manifiesto presentes en la imagen' '  compose-refs-check  Referencias de compose que existan (Dockerfile, imagen)' '  compose-security-check Auditor de seguridad Compose (puertos, privilegios)' '  doc-targets-check Comandos make citados que existan' '  tf-destroy-check  Avisa si el plan destruye algo (STACK=oci|azure|do)' '  tf-plan-*         Plan (oci|azure|do)' '  tf-apply-*        Aplica' '  tf-destroy-*      Destruye' '  env-copy-*        Copia .env por tailnet' '  vpn-copy          Copia perfiles .ovpn al host por tailnet' 'Variables: ENV_FILE IMAGE_SOURCE WORKSPACE_DIR DEST LAB_IMAGE VPN_* LAB_SSH_PORT LAB_SSH_KEY LAB_SSH_HOST HOST_SSH_KEY CLOUD_HOST CLOUD_SSH_PORT CLOUD_REPO_DIR CLOUD_WORKSPACE_DIR TF_HOST'

verify: verify-secrets lint-docker lint-shell verify-pins makefile-check compose-refs-check compose-security-check python-units-check

verify-secrets:
	cd "$(ROOT)" && gitleaks dir . --redact --no-banner --config .gitleaks.toml

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
	@cd "$(ROOT)" && GH_TOKEN="$$(gh auth token 2>/dev/null || true)" ./scripts/verify/check-action-pins.sh

lint-docker:
	cd "$(ROOT)" && hadolint images/base/Dockerfile images/full/Dockerfile

lint-shell:
	@cd "$(ROOT)" && for file in scripts/lab scripts/*.sh scripts/entrypoint/*.sh scripts/health/*.sh scripts/security/*.sh scripts/host/*.sh scripts/cloud/*.sh scripts/verify/*.sh; do \
		if [ -f "$$file" ]; then shellcheck "$$file"; fi; \
	done

# Por defecto cada maquina compila nativa y vacio significa "no fijar
# --platform", que es lo que quiere el diseno. BUILD_PLATFORM sirve para
# validar la otra arquitectura desde una maquina que no la tiene (una
# portatil arm64 comprobando el build del host OCI amd64, por ejemplo),
# y BUILD_TAG evita que esa imagen pise la nativa. El target sigue siendo
# parametrizado con TARGETOS/TARGETARCH: la cross-compilacion la decide
# el propio Dockerfile.
BUILD_PLATFORM ?=
BUILD_TAG ?=
BUILD_PLATFORM_ARG = $(if $(BUILD_PLATFORM),--platform $(BUILD_PLATFORM),)

# Publicacion de la imagen. El host de OCI NO compila: hace pull de lo
# publicado y lo escanea antes de usarlo. Misma logica que ya usa
# hackadvisermx/pentestdocker: construir aqui, publicar, y que el otro host
# baje el artefacto en vez de compilarlo.
#
# DOCKER_REPO es hackadvisermx/sec-lab, publico. El nombre es sec-lab, no
# seclab-sbf: es el repositorio que creo el owner en Docker Hub.
#
# DOCKER_TAG lleva la etiqueta de insumos, asi que el propio nombre dice de
# que codigo salio: 26.04-<hash>. Un tag distinto es una imagen distinta, y
# no se borran: saber que codigo produce cual imagen es el objetivo.
#
# DOCKER_ARCH va en el tag porque aqui NO hay tags multiarquitectura. Se
# construye en una sola arquitectura, la de la maquina que construye, y se publica
# con su nombre. El motivo esta medido, no es Preferences: en la Mac, un
# build --platform linux/amd64 falla al descomprimir el tarball de Ruby con
# "Function not implemented" en cientos de ficheros, y no es un problema de
# permisos ni del contexto: falla tambien en /tmp. Es la emulacion de
# Docker Desktop en Apple Silicon, que responde a un binario suelto pero no a
# un arbol de miles de ficheros. Consecuencia: un manifest multi-arch
# (buildx --platform arm64,amd64) no se puede generar aqui.
#
# Que el nombre lleve la arquitectura NO es solo informativo. El host de OCI
# corre VM.Standard.A1.Flex, que es ARM, asi que hoy un solo tag sirve para
# los dos. Si algun dia el host fuera x86, haria falta el tag amd64 y este
# repo no lo tiene, porque no se puede construir aqui.
#
# DOCKER_DIGEST es lo que hace que esto sea seguro de usar. El host NO hace
# pull de latest ni de un tag flotante, sino de un digest: sha256:... Si
# alguien republica el tag con otra imagen, el digest sigue siendo el mismo
# y el host sigue viendo exactamente lo que se publico. Sin esto, un tag
# mutable es solo confianza ciega en el registry.
DOCKER_REPO ?= hackadvisermx/sec-lab
DOCKER_ARCH ?= $(shell docker version --format '{{.Server.Arch}}')
DOCKER_TAG ?= 26.04-$(DOCKER_ARCH)-$(BUILD_INPUTS)
# La imagen base va al mismo repositorio, con sufijo aparte, porque el
# Dockerfile de full hace FROM seclab-sbf:base y al reconstruir en otro host
# tiene que encontrarla con ese nombre.
DOCKER_BASE_TAG ?= base-$(DOCKER_ARCH)-$(BUILD_INPUTS)
DOCKER_BASE_IMAGE ?= $(DOCKER_REPO):$(DOCKER_BASE_TAG)
DOCKER_IMAGE ?= $(DOCKER_REPO):$(DOCKER_TAG)


build-base:
	cd "$(ROOT)" && BUILDKIT_PROGRESS=plain docker buildx build --progress=plain --pull $(BUILD_PLATFORM_ARG) --file images/base/Dockerfile --label seclab.build-inputs=$(BUILD_INPUTS) --tag seclab-sbf:base$(BUILD_TAG) --load .

# Imagen unica del laboratorio. Antes habia light y full, con full haciendo
# FROM light: la imagen final contenia las dos. Se fusionaron el 2026-09-29 y
# base es lo unico que se construye antes.
build-full: build-base
	cd "$(ROOT)" && BUILDKIT_PROGRESS=plain docker buildx build $(BUILD_PLATFORM_ARG) --progress=plain --build-arg BASE_IMAGE=seclab-sbf:base$(BUILD_TAG) --file images/full/Dockerfile --label seclab.build-inputs=$(BUILD_INPUTS) --tag seclab-sbf:full$(BUILD_TAG) --load .

env-init:
	@cd "$(ROOT)" && if [ -e "$(ENV_FILE)" ]; then \
		printf '%s ya existe; no se sobrescribió\n' "$(ENV_FILE)" >&2; \
		exit 1; \
	fi
	@cd "$(ROOT)" && cp .env.example "$(ENV_FILE)"
	@cd "$(ROOT)" && chmod 600 "$(ENV_FILE)"
	@cd "$(ROOT)" && case "$(ENV_FILE)" in *.example) ;; *) SECLAB_ENV_FILE="$(ENV_FILE)" /bin/sh scripts/generate-keys.sh ;; esac
	@cd "$(ROOT)" && printf 'creado %s desde .env.example\n' "$(ENV_FILE)"

ensure-env:
	@cd "$(ROOT)" && if [ ! -e "$(ENV_FILE)" ]; then \
		cp .env.example "$(ENV_FILE)"; \
		chmod 600 "$(ENV_FILE)"; \
		printf 'creado %s desde .env.example\n' "$(ENV_FILE)"; \
	fi
	@cd "$(ROOT)" && if [ "$(ENV_FILE)" = ".env" ]; then chmod 600 "$(ENV_FILE)"; fi
	@cd "$(ROOT)" && case "$(ENV_FILE)" in *.example) ;; *) SECLAB_ENV_FILE="$(ENV_FILE)" /bin/sh scripts/generate-keys.sh ;; esac

keys: ensure-env

# Copia el archivo de secretos a un directorio montado en el contenedor.
# Se monta el directorio y no el archivo porque un editor que guarda de
# forma atomica (escribe temporal y renombra) cambia el inode del
# archivo y deja colgando cualquier bind mount de un archivo suelto.
sync-secrets:
	@cd "$(ROOT)" && case "$(ENV_FILE)" in \
		*.example) exit 0 ;; \
	esac
	@cd "$(ROOT)" && mkdir -p "$(SECRETS_DIR)"
	@cd "$(ROOT)" && chmod 700 "$(SECRETS_DIR)"
	@cd "$(ROOT)" && cp "$(ENV_FILE)" "$(SECRETS_DIR)/lab.env"
	@cd "$(ROOT)" && chmod 600 "$(SECRETS_DIR)/lab.env"

compose:
	@cd "$(ROOT)" && :

# Forma canonica con guiones; 'up', 'down', 'shell', 'zsh', 'tmux' y
# 'config' se conservan como alias para compatibilidad.
config: compose-config

# El compose declara `create_host_path: false` a proposito, para que un typo
# en WORKSPACE_DIR no cree un arbol de directorios vacio en cualquier sitio.
# Por eso el workspace lo crea make, no compose.
#
# La siembra desde workspace-seed/ solo ocurre si la carpeta esta vacia: en
# cuanto tester tiene notas dentro, make no vuelve a tocar nada. Con un bind
# mount lo que hay en la imagen en /workspace queda tapado por la carpeta del
# host, asi que sin esto las plantillas no se verian nunca.
workspace-dir:
	@cd "$(ROOT)" && mkdir -p "$(WORKSPACE_DIR)"
	@cd "$(ROOT)" && if [ -z "$$(ls -A "$(WORKSPACE_DIR)" 2>/dev/null)" ]; then \
		cp -R workspace-seed/. "$(WORKSPACE_DIR)/"; \
		chmod 755 "$(WORKSPACE_DIR)"; \
		printf '%s\n' "workspace creado y sembrado desde workspace-seed/ en $(WORKSPACE_DIR)"; \
	else \
		printf '%s\n' "workspace ya existe con contenido: no se toca ($(WORKSPACE_DIR))"; \
	fi

compose-config: ensure-env vpn-require-dir workspace-dir
	cd "$(ROOT)" && $(COMPOSE_BASE) config --quiet
	cd "$(ROOT)" && $(COMPOSE_VPN) config --quiet

up: compose-up

compose-up: ensure-env vpn-require-dir ensure-image sync-secrets workspace-dir
	@cd "$(ROOT)" && mkdir -p tmp
	@cd "$(ROOT)" && printf 'services:\n  lab:\n    ports:\n      - "127.0.0.1:%s:2222"\n      - "127.0.0.1:%s:7681"\n      - "127.0.0.1:%s:8080"\n' "$(LAB_SSH_PORT)" "$(LAB_TTYD_PORT)" "$(LAB_DASHBOARD_PORT)" > tmp/compose.ssh.yaml
	cd "$(ROOT)" && $(COMPOSE_VPN) -f tmp/compose.ssh.yaml up -d
	@printf '\n\033[32m✔ Laboratorio SecLab activo en loopback:\033[0m\n'
	@printf '   Dashboard Táctico: http://127.0.0.1:%s\n' "$(LAB_DASHBOARD_PORT)"
	@printf '   Terminal Web:      http://127.0.0.1:%s\n' "$(LAB_TTYD_PORT)"
	@printf '   SSH tester:        ssh -p %s tester@localhost\n\n' "$(LAB_SSH_PORT)"

down: compose-down

compose-down: ensure-env
	cd "$(ROOT)" && if [ -f tmp/compose.ssh.yaml ]; then \
		$(COMPOSE_VPN) -f tmp/compose.ssh.yaml down --remove-orphans; \
	else \
		$(COMPOSE_VPN) down --remove-orphans; \
	fi


shell: compose-shell

compose-shell: ensure-env ensure-image sync-secrets
	cd "$(ROOT)" && $(COMPOSE_BASE) run --rm --user 1000:1000 --entrypoint /bin/bash lab

zsh: compose-zsh

compose-zsh: ensure-env ensure-image sync-secrets
	cd "$(ROOT)" && $(COMPOSE_BASE) run --rm -it --user 1000:1000 --entrypoint /usr/bin/zsh lab -il

tmux: compose-tmux

compose-tmux: ensure-env sync-secrets
	cd "$(ROOT)" && $(COMPOSE_BASE) exec -it --user 1000:1000 lab env SECLAB_TMUX=1 TERM=xterm-256color /usr/bin/tmux new-session -A -s pentest-lab /usr/bin/zsh -il

# El workspace local es un volumen con nombre, no una carpeta del host, asi
# que no se ve desde Finder ni se copia con scp. Estos tres targets son la
# via para mirar lo que hay y para sacar material.
#
# WORKSPACE_VOLUME debe coincidir con el nombre que crea compose: se compone
# como <proyecto>_workspace.
workspace-list:
	@cd "$(ROOT)" && if [ ! -d "$(WORKSPACE_DIR)" ]; then \
		printf '%s\n' "no existe $(WORKSPACE_DIR): make compose-up lo crea"; exit 1; \
	else find "$(WORKSPACE_DIR)" -maxdepth 2 | sed "s|^$(WORKSPACE_DIR)|.|"; fi

# Copia material del workspace al host. Es un bind mount, asi que esto es un
# cp normal; el target existe para no tener que recordar la ruta ni el
# convenio de ENG=/RUTA=/ALL=1.
#   make workspace-export ENG=mi-engagement
#   make workspace-export RUTA=retos/mi-reto DEST=./salida
#   make workspace-export ALL=1
workspace-export:
	@cd "$(ROOT)" && if [ ! -d "$(WORKSPACE_DIR)" ]; then \
		printf '%s\n' "no existe $(WORKSPACE_DIR): make compose-up lo crea" >&2; exit 1; \
	fi; \
	if [ -z "$(ENG)" ] && [ -z "$(RUTA)" ] && [ -z "$(ALL)" ]; then \
		printf '%s\n' 'uso: make workspace-export RUTA=<ruta> | ENG=<engagement> DEST=<dir> | ALL=1' >&2; \
		exit 2; \
	fi; \
	mkdir -p "$(DEST)"; \
	if [ -n "$(ENG)" ]; then set -- "engagements/$(ENG)"; elif [ -n "$(ALL)" ]; then set -- .; else set -- "$(RUTA)"; fi; \
	for src in "$$@"; do \
		if [ ! -e "$(WORKSPACE_DIR)/$$src" ]; then \
			printf '%s\n' "no existe '$$src' en el workspace" >&2; \
			exit 1; \
		fi; \
		printf '%s\n' "exportando $$src -> $(DEST)"; \
		cp -R "$(WORKSPACE_DIR)/$$src" "$(DEST)/"; \
	done; \
	printf '%s\n' "listo en $(DEST)"

# Empaqueta y genera checksum SHA-256 del workspace en BACKUP_DEST (./backups por defecto).
workspace-backup:
	@cd "$(ROOT)" && /bin/sh scripts/host/workspace-backup.sh "$(WORKSPACE_DIR)" "$(BACKUP_DEST)"

# Restaura un respaldo en WORKSPACE_DIR verificando su checksum SHA-256 (FORCE=1 para sobreescribir).
workspace-restore:
	@cd "$(ROOT)" && /bin/sh scripts/host/workspace-restore.sh "$(WORKSPACE_DIR)" "$(BACKUP)" "$(FORCE)"

# SSH al contenedor en un comando: publica 127.0.0.1:LAB_SSH_PORT
# via override temporal en tmp/ (ignorado, sin tocar compose.yaml)
# y entra como tester. Solo construye si la imagen no existe. En el host
# cloud antepone WORKSPACE_DIR=/opt/seclab-sbf/workspace.
# Escaneo local de una imagen con el gate de CVEs. Sin registry, esta es la
# unica puerta de CVEs del proyecto: cada imagen se revisa aqui despues de
# construirse en caliente y antes de usarse. Por defecto la imagen local.
#   make scan-image
#   SCAN_IMAGE=seclab-sbf:base make scan-image
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
	@cd "$(ROOT)" && mkdir -p "$(dir $(SCAN_TAR))"
	cd "$(ROOT)" && docker save -o "$(SCAN_TAR)" "$(SCAN_IMAGE)"
	cd "$(ROOT)" && docker run --rm \
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
	@cd "$(ROOT)" && if [ "$(SCAN_KEEP_TAR)" != "1" ]; then rm -f "$(SCAN_TAR)"; fi


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
	@cd "$(ROOT)" && inputs="$$(docker image inspect -f '{{ index .Config.Labels "seclab.build-inputs" }}' "$(SCAN_IMAGE)" 2>/dev/null)"; \
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
# Se pasan a proposito todos los directorios que van en el contexto, para
# errar hacia reconstruir de mas antes que hacia dejar una imagen vieja.
BUILD_INPUT_DIRS = images scripts shell security supply-chain dashboard/backend/app dashboard/frontend/src dashboard/frontend/dist
BUILD_INPUT_FILES = .tmux.conf dashboard/backend/requirements.txt dashboard/frontend/package.json dashboard/frontend/package-lock.json
BUILD_INPUTS = $(shell { find $(BUILD_INPUT_DIRS) -type f ! -path '*/__pycache__/*' 2>/dev/null; echo $(BUILD_INPUT_FILES); } | sort | xargs shasum -a 256 2>/dev/null | shasum -a 256 | cut -c1-16)

# Reconstruye la imagen local indicada. Lo usan ensure-image cuando falta o
# cuando el codigo ha cambiado, para no repetir el case en dos sitios.
rebuild-image:
	@cd "$(ROOT)" && case "$(LAB_IMAGE_RESOLVED)" in \
		seclab-sbf:base) $(MAKE) build-base ;; \
		seclab-sbf:full) $(MAKE) build-full ;; \
		*) printf 'LAB_IMAGE desconocida: %s (usa base|full)\n' "$(LAB_IMAGE_RESOLVED)" >&2; exit 2 ;; \
	esac

# --- publicacion de la imagen -------------------------------------------
#
# El host de OCI no compila. Hace pull de lo que se publico aqui y lo escanea
# antes de usarlo, que es la misma garantia que antes pero sin 25 GB de disco
# ni hora y media de compilacion en un VPS de 4 GB.
#
# Lo que se publica son DOS tags: la imagen final y la base. El Dockerfile de
# full hace `FROM seclab-sbf:base`, asi que la base tiene que existir en el
# registry con el mismo nombre, o el build en otro host no encontraria el FROM.
#
# Se publica por tag y NO se sobreescribe nada: el tag lleva la etiqueta de
# insumos, y un tag distinto es una imagen distinta. Eso no es un gasto, es
# trazabilidad: dentro de seis meses se puede saber que codigo produce esa
# imagen con solo leer el nombre del tag.
#
# El digest es lo que se le pasa al host. Un tag se puede republicar con otro
# contenido; un digest no cambia nunca. Por eso el host no hace pull de un tag.
#
# El login se hace en la maquina del owner y NO se propaga. El host nunca tiene
# credenciales de escritura: aunque lo compromise, no puede publicar una imagen
# manipulada. Solo puede leer, y solo el digest exacto que le digamos.

# Publica la imagen local de LAB_IMAGE, con su base si es la final.
# No escanea: eso lo hace scan-image, y el gate se corre aparte a proposito,
# para poder publicar y escanear en orden explicito y no por accidente.
image-publish:
	@cd "$(ROOT)" && printf 'publicando %s como %s\n' "$(LAB_IMAGE_RESOLVED)" "$(DOCKER_IMAGE)"
	@cd "$(ROOT)" && case "$(LAB_IMAGE_RESOLVED)" in \
		seclab-sbf:base) docker tag seclab-sbf:base "$(DOCKER_BASE_IMAGE)" \
			&& docker push "$(DOCKER_BASE_IMAGE)" ;; \
		seclab-sbf:full) docker tag seclab-sbf:base "$(DOCKER_BASE_IMAGE)" \
			&& docker push "$(DOCKER_BASE_IMAGE)" \
			&& docker tag seclab-sbf:full "$(DOCKER_IMAGE)" \
			&& docker push "$(DOCKER_IMAGE)" ;; \
		*) printf 'LAB_IMAGE desconocida: %s (usa base|full)\n' "$(LAB_IMAGE_RESOLVED)" >&2; exit 2 ;; \
	esac
	@cd "$(ROOT)" && printf '%s\n' '--- digest publicado ---'
	@cd "$(ROOT)" && docker buildx imagetools inspect "$(DOCKER_IMAGE)" --format '{{.Manifest.Digest}}' 2>/dev/null \
		|| printf '%s\n' 'no se pudo leer el digest con imagetools; usa: docker buildx imagetools inspect IMAGE'

# Lo mismo, pero escaneando ANTES de publicar. Es el orden que se quiere
# siempre: primero el gate, despues la push. Se deja como target aparte para
# que el orden sea explicito y no dependa de acordarse.
image-publish-checked: scan-image image-publish

# Trae la imagen publicada al host, por digest, y la deja lista para compose-up.
# Se ejecuta en la maquina del host, no en la del owner: por eso es un shell
# aparte y no un target normal del Makefile del host cloud.
#
# El digest llega por parametro y NUNCA se deduce. Si no viene, sale con error:
# un pull de "lo que haya ahora" es justo lo que este diseno evita.
image-pull:
	@cd "$(ROOT)" && test -n "$(DOCKER_DIGEST)" || { printf 'DOCKER_DIGEST requerido: el pull es por digest, no por tag\n' >&2; exit 2; }
	@cd "$(ROOT)" && printf 'bajando %s@%s (puede tardar: son 4.9 GB)\n' "$(DOCKER_REPO)" "$(DOCKER_DIGEST)"
	@cd "$(ROOT)" && docker pull "$(DOCKER_REPO)@$(DOCKER_DIGEST)"
	@cd "$(ROOT)" && docker tag "$(DOCKER_REPO)@$(DOCKER_DIGEST)" seclab-sbf:full
	@cd "$(ROOT)" && printf '%s\n' 'imagen lista como seclab-sbf:full; ahora ejecuta scan-image antes de usarla'

# IMAGE_SOURCE decide de donde sale la imagen: local (se construye aqui) o
# remote (se baja de un digest ya publicado). Por defecto local, que es lo que
# quiere el portatil. En el host cloud se pone remote en su .env, y entonces
# ensure-image NUNCA compila: si falta la imagen dice que falta y como
# conseguirla, en vez de ponerse a compilar 4.9 GB en un VPS de 4 GB.
#
# Sin esto, el host seguiria reconstruyendo por su cuenta cada vez que el
# codigo no coincidiera con la etiqueta de insumos, que es justo el problema
# que el pull por digest viene a quitar.
IMAGE_SOURCE ?= local

ensure-image:
	@cd "$(ROOT)" && case "$(IMAGE_SOURCE)" in \
		local) : ;; \
		remote) : ;; \
		*) printf 'IMAGE_SOURCE desconocida: %s (usa local|remote)\n' "$(IMAGE_SOURCE)" >&2; exit 2 ;; \
	esac
	@cd "$(ROOT)" && IMG="$(LAB_IMAGE_RESOLVED)"; \
	if [ "$(IMAGE_SOURCE)" = "remote" ]; then \
		if docker image inspect "$$IMG" >/dev/null 2>&1; then \
			printf 'imagen remota ya presente: %s\n' "$$IMG"; \
		else \
			printf '%s\n' "imagen ausente y IMAGE_SOURCE=remote: NO se compila aqui." >&2; \
			printf '%s\n' "En la maquina que publica: make image-publish, y luego pasa el digest con" >&2; \
			printf '%s\n' "  DOCKER_DIGEST=sha256:... make image-pull" >&2; \
			exit 1; \
		fi; \
	elif docker image inspect "$$IMG" >/dev/null 2>&1; then \
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
	cd "$(ROOT)" && WORKSPACE_DIR="$(WORKSPACE_DIR)" LAB_ENV_FILE="$(ENV_FILE)" SECRETS_DIR="$(SECRETS_DIR)" LAB_IMAGE=seclab-sbf:base$(BUILD_TAG) docker compose -f compose.yaml -f compose.local.yaml run --rm --entrypoint /usr/local/bin/base-healthcheck lab

lab-ports: ensure-env vpn-require-dir ensure-image sync-secrets
	@cd "$(ROOT)" && mkdir -p tmp
	@cd "$(ROOT)" && printf 'services:\n  lab:\n    ports:\n      - "127.0.0.1:%s:2222"\n      - "127.0.0.1:%s:7681"\n      - "127.0.0.1:%s:8080"\n' "$(LAB_SSH_PORT)" "$(LAB_TTYD_PORT)" "$(LAB_DASHBOARD_PORT)" > tmp/compose.ssh.yaml
	cd "$(ROOT)" && WORKSPACE_DIR="$(WORKSPACE_DIR)" LAB_ENV_FILE="$(ENV_FILE)" SECRETS_DIR="$(SECRETS_DIR)" LAB_IMAGE="$(LAB_IMAGE_RESOLVED)" docker compose -f compose.yaml -f compose.local.yaml -f tmp/compose.ssh.yaml up -d lab
	@printf '%s\n' "puertos loopback listos: Dashboard=http://127.0.0.1:$(LAB_DASHBOARD_PORT) ttyd=http://127.0.0.1:$(LAB_TTYD_PORT) SSH=127.0.0.1:$(LAB_SSH_PORT)"

lab-ssh: lab-ports
	cd "$(ROOT)" && ssh -o StrictHostKeyChecking=accept-new -i "$(LAB_SSH_KEY)" -p "$(LAB_SSH_PORT)" tester@$(LAB_SSH_HOST)

# Entrada directa al contenedor del host cloud. Ahi el puente lo publica
# el servicio systemd seclab-ssh-tailnet en la IP Tailscale, asi que no
# hace falta aplicar ningun override de puertos.
lab-ssh-cloud:
	@cd "$(ROOT)" && test -n "$(CLOUD_HOST)" || (printf 'CLOUD_HOST requerido: tailnet del host (ej. make lab-ssh-cloud TF_HOST=100.x.y.z)\n' >&2; exit 2)
	cd "$(ROOT)" && ssh -o StrictHostKeyChecking=accept-new -i "$(LAB_SSH_KEY)" -p "$(CLOUD_SSH_PORT)" tester@"$(CLOUD_HOST)"

# Entrada directa al host cloud (usuario ubuntu, administracion del sistema, puerto 22).
host-ssh-cloud:
	@cd "$(ROOT)" && test -n "$(CLOUD_HOST)" || (printf 'CLOUD_HOST requerido: tailnet del host (ej. make host-ssh-cloud TF_HOST=100.x.y.z)\n' >&2; exit 2)
	cd "$(ROOT)" && ssh -o StrictHostKeyChecking=accept-new -i "$(HOST_SSH_KEY)" -p 22 "$(TF_ADMIN)@$(CLOUD_HOST)"

# Entradas especificas por proveedor (Azure / OCI)
lab-ssh-azure:
	@cd "$(ROOT)" && test -n "$(AZURE_HOST)" || (printf 'AZURE_HOST o TF_HOST requerido (ej. make lab-ssh-azure TF_HOST=100.x.y.z)\n' >&2; exit 2)
	cd "$(ROOT)" && ssh -o StrictHostKeyChecking=accept-new -i "$(LAB_SSH_KEY)" -p "$(CLOUD_SSH_PORT)" tester@"$(AZURE_HOST)"

lab-ssh-az: lab-ssh-azure

host-ssh-azure:
	@cd "$(ROOT)" && test -n "$(AZURE_HOST)" || (printf 'AZURE_HOST o TF_HOST requerido (ej. make host-ssh-azure TF_HOST=100.x.y.z)\n' >&2; exit 2)
	cd "$(ROOT)" && ssh -o StrictHostKeyChecking=accept-new -i "$(HOST_SSH_KEY)" -p 22 "$(TF_ADMIN)@$(AZURE_HOST)"

host-ssh-az: host-ssh-azure

lab-ssh-oci:
	@cd "$(ROOT)" && test -n "$(OCI_HOST)" || (printf 'OCI_HOST o TF_HOST requerido (ej. make lab-ssh-oci TF_HOST=100.x.y.z)\n' >&2; exit 2)
	cd "$(ROOT)" && ssh -o StrictHostKeyChecking=accept-new -i "$(LAB_SSH_KEY)" -p "$(CLOUD_SSH_PORT)" tester@"$(OCI_HOST)"

host-ssh-oci:
	@cd "$(ROOT)" && test -n "$(OCI_HOST)" || (printf 'OCI_HOST o TF_HOST requerido (ej. make host-ssh-oci TF_HOST=100.x.y.z)\n' >&2; exit 2)
	cd "$(ROOT)" && ssh -o StrictHostKeyChecking=accept-new -i "$(HOST_SSH_KEY)" -p 22 "$(TF_ADMIN)@$(OCI_HOST)"



# En el cloud la imagen no se elige al conectar: hay que recrear el
# contenedor en el host. Por eso el atajo remoto primero levanta el lab
# alla con la imagen pedida y despues entra.
lab-ssh-cloud-image:
	@cd "$(ROOT)" && test -n "$(CLOUD_HOST)" || (printf 'CLOUD_HOST requerido: tailnet del host\n' >&2; exit 2)
	@cd "$(ROOT)" && test -n "$(DOCKER_DIGEST)" || { printf 'DOCKER_DIGEST requerido: el host no compila, baja un digest\n' >&2; exit 2; }
	@cd "$(ROOT)" && printf 'bajando en el host %s@%s (son 4.9 GB, tarda)\n' "$(DOCKER_REPO)" "$(DOCKER_DIGEST)"
	@cd "$(ROOT)" && printf 'recreando el lab en el host con esa imagen y escaneandola antes de usarla\n'
	cd "$(ROOT)" && printf 'cd %s\nmake image-pull DOCKER_REPO=%s DOCKER_DIGEST=%s\nmake scan-image IMAGE_SOURCE=remote\nWORKSPACE_DIR=%s make compose-up IMAGE_SOURCE=remote\n' \
		"$(CLOUD_REPO_DIR)" "$(DOCKER_REPO)" "$(DOCKER_DIGEST)" "$(CLOUD_WORKSPACE_DIR)" \
		| ssh -o StrictHostKeyChecking=accept-new -i "$(HOST_SSH_KEY)" "$(TF_ADMIN)@$(CLOUD_HOST)" sh -s -e
	cd "$(ROOT)" && $(MAKE) lab-ssh-cloud

vpn-require-dir:
	@cd "$(ROOT)" && if [ ! -d "$(VPN_DIR)" ]; then \
		printf '%s\n' 'No existe $(VPN_DIR); crea el directorio y coloca perfiles .ovpn sanitizados.' >&2; \
		exit 1; \
	fi

# El daemon VPN vive dentro del contenedor lab (root, NET_ADMIN y
# /dev/net/tun). Las acciones de tester pasan por el socket Unix con
# vpn-control client; las comprobaciones que requieren root usan
# vpn-manager directamente.
VPN_CLIENT := $(COMPOSE_VPN) exec -T --user 1000:1000 lab /usr/local/bin/vpn-control client

vpn-up: ensure-env vpn-require-dir ensure-image sync-secrets
	cd "$(ROOT)" && $(COMPOSE_VPN) up -d lab
	cd "$(ROOT)" && $(COMPOSE_VPN) exec -T lab /bin/sh -c 'test -S /var/lib/seclab/vpn-control/control.sock && test -e /sys/class/net/tun0 && printf "%s\n" "vpn=ready tun0=present"'

vpn-tun-check: vpn-up
	cd "$(ROOT)" && $(COMPOSE_VPN) exec -T lab /bin/sh -c 'test -c /dev/net/tun && test -e /sys/class/net/tun0 && /usr/local/bin/vpn-manager status'

vpn-down: ensure-env
	cd "$(ROOT)" && $(VPN_CLIENT) disconnect

vpn-list: vpn-up
	cd "$(ROOT)" && $(VPN_CLIENT) list

vpn-status: vpn-up
	cd "$(ROOT)" && $(VPN_CLIENT) status

vpn-connect: vpn-up
	cd "$(ROOT)" && $(VPN_CLIENT) connect "$(VPN_PROFILE)"

vpn-disconnect: vpn-up
	cd "$(ROOT)" && $(VPN_CLIENT) disconnect

vpn-switch: vpn-up
	cd "$(ROOT)" && $(VPN_CLIENT) switch "$(VPN_PROFILE)"

vpn-doctor: vpn-up
	cd "$(ROOT)" && $(COMPOSE_VPN) exec -T lab /usr/local/bin/vpn-manager doctor

proxy-status: ensure-env
	cd "$(ROOT)" && $(COMPOSE_BASE) exec -T --user 1000:1000 lab /usr/local/bin/pt-forward status

proxy-doctor: ensure-env
	cd "$(ROOT)" && $(COMPOSE_BASE) exec -T --user 1000:1000 lab /usr/local/bin/pt-forward doctor

proxy-stop: ensure-env
	cd "$(ROOT)" && $(COMPOSE_BASE) exec -T --user 1000:1000 lab /usr/local/bin/pt-forward stop

proxy-bridge:
	cd "$(ROOT)" && /bin/sh scripts/host/pt-proxy-bridge.sh "$(SERVICE)" "$(HOST_PORT)" "$(CONTAINER_PORT)"

security-check:
	cd "$(ROOT)" && /bin/sh scripts/security/check-isolation.sh

tailscale-check:
	cd "$(ROOT)" && /bin/sh scripts/security/check-tailscale.sh

fail2ban-check:
	cd "$(ROOT)" && /bin/sh scripts/security/check-fail2ban.sh

TF_STACK ?= oci
TF_HOST ?=
TF_ADMIN ?= ubuntu
AZURE_RG ?= seclab-sbf-prod
AZURE_VM ?= seclab-sbf-prod-lab

tf-fmt:
	cd "$(ROOT)" && terraform fmt -check -recursive terraform/

tf-render-check:
	cd "$(ROOT)" && /bin/sh scripts/verify/check-tf-render.sh

# Solo el ruleset terraform que va embebido en el binario, sin plugins
# del registro. Sin tflint instalado se sale con 78 y el comando para
# obtenerlo, como el resto de checks.
tflint-check:
	@cd "$(ROOT)" && command -v tflint >/dev/null 2>&1 || { \
	  printf '%s\n' 'tflint_check=unavailable command=tflint (brew install tflint)'; \
	  exit 78; \
	}
	@cd "$(ROOT)" && for stack in oci azure digitalocean; do \
	  printf '== %s ==\n' "$$stack"; \
	  tflint --chdir="terraform/stacks/$$stack" || exit 1; \
	done
	@cd "$(ROOT)" && printf '%s\n' 'tflint_check=ok config=.tflint.hcl'

# Avisa antes de un apply cuando el plan va a DESTRUIR algo. No decide ni
# aplica nada: imprime el plan y sale con codigo 1 si ve una destruccion.
# Existe porque el stack de OCI tiene la instancia con metadata, que el
# provider trata como inmutable: cualquier cambio en el cloud-init la
# reemplaza. STACK=oci|azure|digitalocean.
tf-destroy-check:
	cd "$(ROOT)" && /bin/sh scripts/verify/check-tf-destroy.sh "$(STACK)"

# Los comandos make citados en la documentación tienen que existir. Se
# colaron seis que no, todos en el Inicio rapido del README.
# Recetas de un solo tabulador y comillas simples balanceadas. El fallo
# que vigila solo se ve con GNU Make 4.x: en macOS el 3.81 lo tolera.
makefile-check:
	cd "$(ROOT)" && /bin/sh scripts/verify/check-makefile.sh Makefile

# La imagen puede construir bien y aun asi faltar un binario. IMAGE_TOOLS
# permite comprobar una imagen distinta de la que produce el Makefile.
image-tools-check:
	cd "$(ROOT)" && /bin/sh scripts/verify/check-image-tools.sh "$(SCAN_IMAGE)"

# Smoke test funcional del contenedor sin servicios en background ni .env.
# Valida permisos de workspace, carga limpia de Zsh/pt-help, runtimes y tools clave.
smoke-test:
	cd "$(ROOT)" && /bin/sh scripts/verify/smoke-test.sh "$(SCAN_IMAGE)"

compose-refs-check:
	cd "$(ROOT)" && /bin/sh scripts/verify/check-compose-refs.sh compose.yaml compose.local.yaml compose.vpn-inside.yaml

compose-security-check: ensure-env vpn-require-dir workspace-dir
	@cd "$(ROOT)" && $(COMPOSE_BASE) config --format json | python3 scripts/verify/check-compose-security.py --name "compose.local"
	@cd "$(ROOT)" && $(COMPOSE_VPN) config --format json | python3 scripts/verify/check-compose-security.py --name "compose.vpn-inside"

doc-targets-check:
	cd "$(ROOT)" && /bin/sh scripts/verify/check-doc-targets.sh README.md AGENTS.md docs/runbooks.md docs/backups.md docs/phase-8.md

python-units-check:
	cd "$(ROOT)" && python3 scripts/verify/check-python-units.py

py-test: python-units-check

# Valida la jail de fail2ban con el propio fail2ban, en un contenedor
# desechable. No levanta ninguna jail ni toca nftables: solo parsea la
# configuracion y pasa dos logs por el filtro de sshd. El ban efectivo
# sigue siendo cosa del host, con make fail2ban-check.
fail2ban-jail-check:
	cd "$(ROOT)" && /bin/sh scripts/verify/check-fail2ban-jail.sh

tf-plan-oci:
	cd "$(ROOT)" && /bin/sh scripts/cloud/tf.sh oci plan

tf-apply-oci:
	cd "$(ROOT)" && /bin/sh scripts/cloud/tf.sh oci apply

tf-destroy-oci:
	cd "$(ROOT)" && /bin/sh scripts/cloud/tf.sh oci destroy

tf-plan-azure:
	cd "$(ROOT)" && /bin/sh scripts/cloud/tf.sh azure plan

tf-apply-azure:
	cd "$(ROOT)" && /bin/sh scripts/cloud/tf.sh azure apply

tf-destroy-azure:
	cd "$(ROOT)" && /bin/sh scripts/cloud/tf.sh azure destroy

# Gestion de energia de la VM en Azure:
# vm-stop-azure ejecuta `deallocate`, lo cual libera vCPU y RAM deteniendo
# por completo el cobro por hora de computo ($0.00/h). `az vm stop` solo
# pararia el SO pero seguiria cobrando.
vm-status-azure:
	@az vm get-instance-view --resource-group "$(AZURE_RG)" --name "$(AZURE_VM)" --query "instanceView.statuses[?starts_with(code, 'PowerState/')].displayStatus" -o tsv 2>/dev/null || printf 'No se pudo consultar el estado de %s\n' "$(AZURE_VM)"

vm-status-az: vm-status-azure

vm-stop-azure:
	@printf 'Desasignando VM %s en %s (deallocate libera vCPU/RAM y detiene costos de computo)...\n' "$(AZURE_VM)" "$(AZURE_RG)"
	az vm deallocate --resource-group "$(AZURE_RG)" --name "$(AZURE_VM)"
	@printf 'VM desasignada correctamente. Estado: Deallocated (computo = $$0.00/h).\n'

vm-stop-az: vm-stop-azure

vm-start-azure:
	@printf 'Iniciando VM %s en %s...\n' "$(AZURE_VM)" "$(AZURE_RG)"
	az vm start --resource-group "$(AZURE_RG)" --name "$(AZURE_VM)"
	@printf 'VM iniciada correctamente. Tailnet: %s\n' "$(AZURE_HOST)"

vm-start-az: vm-start-azure

tf-plan-do:
	cd "$(ROOT)" && /bin/sh scripts/cloud/tf.sh digitalocean plan

tf-apply-do:
	cd "$(ROOT)" && /bin/sh scripts/cloud/tf.sh digitalocean apply

tf-destroy-do:
	cd "$(ROOT)" && /bin/sh scripts/cloud/tf.sh digitalocean destroy

env-copy-oci:
	@cd "$(ROOT)" && test -n "$(TF_HOST)" || (printf 'TF_HOST requerido: tailnet del host\n' >&2; exit 2)
	cd "$(ROOT)" && scp -o StrictHostKeyChecking=accept-new -i "$(HOST_SSH_KEY)" "$(ENV_FILE)" "$(TF_ADMIN)@$(TF_HOST):~/seclab-sbf/.env"

env-copy-azure:
	@cd "$(ROOT)" && test -n "$(TF_HOST)" || (printf 'TF_HOST requerido: tailnet del host\n' >&2; exit 2)
	cd "$(ROOT)" && scp -o StrictHostKeyChecking=accept-new -i "$(HOST_SSH_KEY)" "$(ENV_FILE)" "$(TF_ADMIN)@$(TF_HOST):~/seclab-sbf/.env"

env-copy-do:
	@cd "$(ROOT)" && test -n "$(TF_HOST)" || (printf 'TF_HOST requerido: tailnet del host\n' >&2; exit 2)
	cd "$(ROOT)" && scp -o StrictHostKeyChecking=accept-new -i "$(HOST_SSH_KEY)" "$(ENV_FILE)" "$(TF_ADMIN)@$(TF_HOST):~/seclab-sbf/.env"

# Los .ovpn pueden traer usuario y contrasena en linea, asi que viajan
# por el tailnet igual que el .env y nunca se hornean en la imagen: cada
# maquina construye la suya y el perfil se monta en /vpn.
vpn-copy:
	@cd "$(ROOT)" && test -n "$(TF_HOST)" || (printf 'TF_HOST requerido: tailnet del host\n' >&2; exit 2)
	@cd "$(ROOT)" && set -e; \
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

# ==============================================================================
# Tactical Dashboard & API Vault
# ==============================================================================
DASHBOARD_PORT ?= 8080

dashboard-build:
	@cd "$(ROOT)/dashboard/frontend" && npm ci && npm run build

.PHONY: dashboard-tests
dashboard-tests: ensure-image
	@cd "$(ROOT)" && docker run --rm --network none --entrypoint /opt/nxc/bin/python3 -e PYTHONPATH=/usr/local/share/seclab/dashboard/backend -e DASHBOARD_PASSWORD=dashboard-test-fixture-only -e DASHBOARD_ALLOWED_HOSTS=localhost,127.0.0.1,testserver -v "$(ROOT)/dashboard/backend/tests:/tests:ro" "$(LAB_IMAGE_RESOLVED)" -m unittest discover -s /tests -v

dashboard: dashboard-up

dashboard-up:
	@cd "$(ROOT)" && if docker ps --format '{{.Names}}' 2>/dev/null | grep -q 'seclab-sbf-lab-1'; then \
		$(MAKE) lab-ports; \
	else \
		$(MAKE) compose-up; \
	fi

dashboard-daemon: dashboard-up

dashboard-stop:
	@cd "$(ROOT)" && if [ -f ./dashboard/dashboard.pid ]; then ./dashboard/run.sh stop; fi
	@cd "$(ROOT)" && $(MAKE) compose-down

dashboard-status:
	@cd "$(ROOT)" && if curl -s -I -m 1 "http://127.0.0.1:$(LAB_DASHBOARD_PORT)/" >/dev/null 2>&1; then \
		printf 'Dashboard: ACTIVO en http://127.0.0.1:%s (Terminal en http://127.0.0.1:%s)\n' "$(LAB_DASHBOARD_PORT)" "$(LAB_TTYD_PORT)"; \
	else \
		printf 'Dashboard: INACTIVO (ejecute make up o make dashboard-up)\n'; \
	fi
