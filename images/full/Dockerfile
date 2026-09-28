ARG FULL_BASE=seclab-sbf:light
ARG UBUNTU_IMAGE=docker.io/library/ubuntu:24.04@sha256:008173c23f95b170204355c12626cb5a965d779a7e1283b09e9cffbb1bf33ca3
ARG UBUNTU_SNAPSHOT=20260925T000000Z
ARG RUBY_VERSION=3.3.8
ARG RUBY_SHA256=5ae28a87a59a3e4ad66bc2931d232dbab953d0aa8f6baf3bc4f8f80977c89cab
ARG MSF_VERSION=6.5.5
ARG MSF_COMMIT=c5429ba817d12d9d89069387142332435598e548
ARG GO_BUILDER=docker.io/library/golang:1.26.8@sha256:6c2a5538f964f1c82f97ad14988bf05de100d922d159d0e398b54c7b0ca0c6c9
ARG BETTERCAP_VERSION=2.41.7
ARG BETTERCAP_COMMIT=dfe56780bb342b6a6715c9557a2cefe1f13d805c
ARG S3SCANNER_VERSION=3.1.1
ARG S3SCANNER_COMMIT=9c61311a2f7610e523cfc8194abb98ab96c584d2
ARG PAT_COMMIT=3ac27901c711bdf3f5b65a7b1d1820a1f65bd09a
ARG EXPLOITDB_COMMIT=150aef0e7c4757c9dff33016c8352671cdc9b454
ARG NXC_VERSION=1.5.1
ARG NXC_COMMIT=c7dc286ba65daf10402cdc470e531b84e6d3d911

# NetExec no esta en PyPI (se instala desde git) y varias dependencias se
# compilan desde fuente, asi que se fija por commit igual que metasploit y
# las versiones transitivas quedan en supply-chain/tools.lock.yaml.
# Se compila para la arquitectura destino: no lleva --platform.
FROM ${UBUNTU_IMAGE} AS nxc-builder
ARG UBUNTU_SNAPSHOT
ARG NXC_VERSION
ARG NXC_COMMIT
ENV DEBIAN_FRONTEND=noninteractive
# Bootstrap de certificados: sale del archivo vivo porque todavia no hay CA con
# que verificar el snapshot. A partir de la linea siguiente todo se instala
# desde el snapshot, que es el pin real del proyecto; la version que resuelve
# queda registrada en supply-chain/tools.lock.yaml. El paquete no llega a la
# imagen final: light ya aporta el suyo, tambien desde el snapshot.
# hadolint ignore=DL3008
RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates \
 && sed -i "s|http://ports.ubuntu.com/ubuntu-ports/|https://snapshot.ubuntu.com/ubuntu/${UBUNTU_SNAPSHOT}/|g" /etc/apt/sources.list.d/ubuntu.sources \
 && sed -i '/^Snapshot:/d' /etc/apt/sources.list.d/ubuntu.sources \
 && apt-get update \
 && apt-get install -y --no-install-recommends \
      build-essential \
      cargo \
      git \
      libffi-dev \
      libssl-dev \
      pkg-config \
      python3-dev \
      python3-pip \
      python3-venv \
 && rm -rf /var/lib/apt/lists/*
RUN git init /src/nxc \
 && git -C /src/nxc remote add origin https://github.com/Pennyw0rth/NetExec.git \
 && git -C /src/nxc fetch --depth 1 origin "${NXC_COMMIT}" \
 && git -C /src/nxc checkout --detach FETCH_HEAD \
 && test "$(git -C /src/nxc rev-parse HEAD)" = "${NXC_COMMIT}" \
 && test "$(git -C /src/nxc describe --tags --exact-match 2>/dev/null || printf 'v%s' "${NXC_VERSION}")" = "v${NXC_VERSION}"
RUN python3 -m venv /opt/nxc \
 && /opt/nxc/bin/pip install --no-cache-dir --upgrade pip \
 && /opt/nxc/bin/pip install --no-cache-dir "git+https://github.com/Pennyw0rth/NetExec.git@${NXC_COMMIT}" \
 && /opt/nxc/bin/pip install --no-cache-dir --upgrade "cryptography>=46.0.5" "pyOpenSSL>=26.0.0" "setuptools>=78.1.1" \
 && /opt/nxc/bin/python -c 'import nxc.netexec, nxc.nxcdb, cryptography, OpenSSL' \
 && /opt/nxc/bin/python -c 'import cryptography, OpenSSL, setuptools; from importlib.metadata import version; m={"cryptography": "46.0.5", "pyOpenSSL": "26.0.0", "setuptools": "78.1.1"}; [(_ for _ in ()).throw(SystemExit("%s=%s por debajo de %s" % (k, version(k), v))) if tuple(int(x) for x in version(k).split(".")[:3]) < tuple(int(x) for x in v.split(".")) else None for k, v in m.items()]; print("nxc deps ok")' \
 && mkdir -p /out \
 && cp -r /opt/nxc /out/nxc \
 && printf '%s\n' "${NXC_VERSION}" > /out/version \
 && /opt/nxc/bin/pip freeze --all > /out/frozen.txt

# Sin --platform=$BUILDPLATFORM: Ruby y Metasploit no se pueden cross-compilar,
# asi que este stage tiene que compilar para la plataforma destino. Con
# $BUILDPLATFORM la imagen arm64 llevaba un Ruby amd64 dentro y msfconsole no
# arrancaba. Solo lo enmascara en builds locales, donde build platform y
# destino coinciden.
# bettercap y s3scanner si se compilan en la plataforma destino. bettercap
# depende de github.com/google/gousb, que es cgo puro y no tiene build tag que
# lo saque, asi que necesita cgo y libusb-1.0. Su release oficial solo trae
# linux_amd64, y aqui cada maquina compila la suya: para arm64 no hay binario
# que descargar, asi que el source build es la unica via igual que en naabu.
# s3scanner es Go puro y va con CGO_ENABLED=0.
# Los pines de este stage son de Debian (la imagen golang oficial es trixie),
# no de Ubuntu: gcc 4:14.2.0-1, libpcap-dev 1.10.5-2 y libusb 2:1.0.28-1. El
# runtime de la imagen final si es Ubuntu y usa sus propias versiones.
# bettercap necesita las dos cabeceras: libusb por gousb y libpcap por
# gopacket/pcap. En runtime el pcap ya lo aporta light (libpcap0.8t64).
FROM --platform=$BUILDPLATFORM ${GO_BUILDER} AS go-builder
ARG TARGETOS
ARG TARGETARCH
ARG BETTERCAP_VERSION
ARG BETTERCAP_COMMIT
ARG S3SCANNER_VERSION
ARG S3SCANNER_COMMIT
RUN apt-get update \
 && apt-get install -y --no-install-recommends gcc=4:14.2.0-1 libpcap-dev=1.10.5-2 libusb-1.0-0-dev=2:1.0.28-1 \
 && if [ "$(dpkg --print-architecture)" = "arm64" ] && [ "${TARGETARCH}" = "amd64" ]; then \
      dpkg --add-architecture amd64 && apt-get update \
      && apt-get install -y --no-install-recommends gcc-x86-64-linux-gnu=4:14.2.0-1 libpcap-dev:amd64=1.10.5-2 libusb-1.0-0-dev:amd64=2:1.0.28-1; \
    fi \
 && if [ "$(dpkg --print-architecture)" = "amd64" ] && [ "${TARGETARCH}" = "arm64" ]; then \
      dpkg --add-architecture arm64 && apt-get update \
      && apt-get install -y --no-install-recommends gcc-aarch64-linux-gnu=4:14.2.0-1 libpcap-dev:arm64=1.10.5-2 libusb-1.0-0-dev:arm64=2:1.0.28-1; \
    fi \
 && rm -rf /var/lib/apt/lists/*
RUN git init /src/bettercap \
 && git -C /src/bettercap remote add origin https://github.com/bettercap/bettercap.git \
 && git -C /src/bettercap fetch --depth 1 origin "${BETTERCAP_COMMIT}" \
 && git -C /src/bettercap checkout --detach "${BETTERCAP_COMMIT}" \
 && test "$(git -C /src/bettercap rev-parse HEAD)" = "${BETTERCAP_COMMIT}"
WORKDIR /src/bettercap
# xpath 1.3.4 trae CVE-2026-32287 (HIGH, DoS por bucle infinito en boolean
# XPath), corregido en 1.3.6. Llega por antchfx/jsonquery, asi que se sube el
# modulo directamente igual que el resto de bumps.
RUN --mount=type=cache,target=/go/pkg/mod --mount=type=cache,target=/root/.cache/go-build GOTOOLCHAIN=local go mod edit -json >/dev/null \
 && if GOTOOLCHAIN=local go list -m golang.org/x/net >/dev/null 2>&1; then GOTOOLCHAIN=local go get golang.org/x/net@v0.56.0; fi \
 && if GOTOOLCHAIN=local go list -m golang.org/x/mod >/dev/null 2>&1; then GOTOOLCHAIN=local go get golang.org/x/mod@v0.40.0; fi \
 && if GOTOOLCHAIN=local go list -m golang.org/x/crypto >/dev/null 2>&1; then GOTOOLCHAIN=local go get golang.org/x/crypto@v0.56.0; fi \
 && if GOTOOLCHAIN=local go list -m github.com/antchfx/xpath >/dev/null 2>&1; then GOTOOLCHAIN=local go get github.com/antchfx/xpath@v1.3.6; fi \
 && GOTOOLCHAIN=local go mod tidy
RUN mkdir -p /out \
 && if [ "${TARGETARCH}" = "$(GOTOOLCHAIN=local go env GOARCH)" ]; then \
      GOTOOLCHAIN=local CGO_ENABLED=1 CC=gcc GOOS="${TARGETOS}" GOARCH="${TARGETARCH}" \
        go build -mod=readonly -trimpath -buildvcs=false \
        -ldflags "-s -w" \
        -o /out/bettercap .; \
    elif [ "${TARGETARCH}" = "amd64" ]; then \
      GOTOOLCHAIN=local CGO_ENABLED=1 CC=x86_64-linux-gnu-gcc CGO_LDFLAGS="-L/usr/lib/x86_64-linux-gnu" GOOS=linux GOARCH=amd64 \
        go build -mod=readonly -trimpath -buildvcs=false \
        -ldflags "-s -w" \
        -o /out/bettercap .; \
    else \
      GOTOOLCHAIN=local CGO_ENABLED=1 CC=aarch64-linux-gnu-gcc CGO_LDFLAGS="-L/usr/lib/aarch64-linux-gnu" GOOS=linux GOARCH=arm64 \
        go build -mod=readonly -trimpath -buildvcs=false \
        -ldflags "-s -w" \
        -o /out/bettercap .; \
    fi
RUN git init /src/s3scanner \
 && git -C /src/s3scanner remote add origin https://github.com/sa7mon/s3scanner.git \
 && git -C /src/s3scanner fetch --depth 1 origin "${S3SCANNER_COMMIT}" \
 && git -C /src/s3scanner checkout --detach "${S3SCANNER_COMMIT}" \
 && test "$(git -C /src/s3scanner rev-parse HEAD)" = "${S3SCANNER_COMMIT}"
WORKDIR /src/s3scanner
# pgx 5.5.5 trae CVE-2026-33815 y CVE-2026-33816 (CRITICAL, memory safety),
# corregidos en 5.9.0. Se sube igual que hace naabu en light.
RUN --mount=type=cache,target=/go/pkg/mod --mount=type=cache,target=/root/.cache/go-build GOTOOLCHAIN=local go mod edit -json >/dev/null \
 && if GOTOOLCHAIN=local go list -m golang.org/x/net >/dev/null 2>&1; then GOTOOLCHAIN=local go get golang.org/x/net@v0.56.0; fi \
 && if GOTOOLCHAIN=local go list -m golang.org/x/mod >/dev/null 2>&1; then GOTOOLCHAIN=local go get golang.org/x/mod@v0.40.0; fi \
 && if GOTOOLCHAIN=local go list -m golang.org/x/crypto >/dev/null 2>&1; then GOTOOLCHAIN=local go get golang.org/x/crypto@v0.56.0; fi \
 && if GOTOOLCHAIN=local go list -m github.com/jackc/pgx/v5 >/dev/null 2>&1; then GOTOOLCHAIN=local go get github.com/jackc/pgx/v5@v5.9.0; fi \
 && GOTOOLCHAIN=local go mod tidy
# -X main.version para que `s3scanner --version` no salga como "dev": main.go
# declara var version = "dev" y solo lo cambia el linker en release.
RUN mkdir -p /out \
 && GOTOOLCHAIN=local CGO_ENABLED=0 GOOS="${TARGETOS}" GOARCH="${TARGETARCH}" \
      go build -mod=readonly -trimpath -buildvcs=false \
      -ldflags "-s -w -X main.version=${S3SCANNER_VERSION}" \
      -o /out/s3scanner .

FROM ${UBUNTU_IMAGE} AS msf-builder
ARG UBUNTU_SNAPSHOT
ARG RUBY_VERSION
ARG RUBY_SHA256
ARG MSF_VERSION
ARG MSF_COMMIT
ENV DEBIAN_FRONTEND=noninteractive
# Bootstrap de certificados: sale del archivo vivo porque todavia no hay CA con
# que verificar el snapshot. A partir de la linea siguiente todo se instala
# desde el snapshot, que es el pin real del proyecto; la version que resuelve
# queda registrada en supply-chain/tools.lock.yaml. El paquete no llega a la
# imagen final: light ya aporta el suyo, tambien desde el snapshot.
# hadolint ignore=DL3008
RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates \
 && sed -i "s|http://ports.ubuntu.com/ubuntu-ports/|https://snapshot.ubuntu.com/ubuntu/${UBUNTU_SNAPSHOT}/|g" /etc/apt/sources.list.d/ubuntu.sources \
 && sed -i '/^Snapshot:/d' /etc/apt/sources.list.d/ubuntu.sources \
 && apt-get update \
 && apt-get install -y --no-install-recommends \
      autoconf \
      build-essential \
      curl \
      git \
      libffi-dev \
      libgdbm-dev \
      libpcap-dev \
      libpq-dev \
      libreadline-dev \
      libsqlite3-dev \
      libssl-dev \
      libxml2-dev \
      libxslt1-dev \
      libyaml-dev \
      patch \
      pkg-config \
      zlib1g-dev \
 && rm -rf /var/lib/apt/lists/*
# pipefail solo para este RUN: las tuberias de la verificacion del hash y de la
# version no pueden enmascarar un fallo de curl. Se restaura /bin/sh despues
# para no cambiarle el shell al resto del stage.
# El cd va en un subshell a proposito, para que no cambie el directorio del
# layer. Usar WORKDIR aqui dejaria el workdir apuntando a un directorio que
# esta misma linea borra, y el siguiente RUN lo recrearia vacio.
SHELL ["/bin/bash", "-o", "pipefail", "-c"]
# hadolint ignore=DL3003
RUN curl --fail --location --proto '=https' --tlsv1.2 --retry 3 \
      "https://cache.ruby-lang.org/pub/ruby/${RUBY_VERSION%.*}/ruby-${RUBY_VERSION}.tar.gz" \
      --output /tmp/ruby.tar.gz \
 && printf '%s  %s\n' "${RUBY_SHA256}" /tmp/ruby.tar.gz | sha256sum -c - \
 && rm -rf /tmp/ruby && mkdir /tmp/ruby && tar -xzf /tmp/ruby.tar.gz -C /tmp/ruby \
 && ( cd "/tmp/ruby/ruby-${RUBY_VERSION}" \
      && ./configure --disable-install-doc --prefix=/opt/ruby \
      && make -j"$(nproc)" \
      && make install ) \
 && /opt/ruby/bin/ruby -v | grep -q "${RUBY_VERSION}" \
 && rm -rf /tmp/ruby /tmp/ruby.tar.gz
SHELL ["/bin/sh", "-c"]
RUN git init /src/msf \
 && git -C /src/msf remote add origin https://github.com/rapid7/metasploit-framework.git \
 && git -C /src/msf fetch --depth 1 origin "refs/tags/${MSF_VERSION}:refs/tags/${MSF_VERSION}" \
 && git -C /src/msf checkout --detach "refs/tags/${MSF_VERSION}" \
 && test "$(git -C /src/msf rev-parse HEAD)" = "${MSF_COMMIT}"
WORKDIR /src/msf
# concurrent-ruby 1.3.5 (CVE-2026-54906) entra por el Gemfile.lock de MSF
# 6.5.5. Se sube con bundle update y se verifica el minimo con rubygems: si
# Metasploit vuelve a traer una version vulnerable, el build falla aqui en vez
# de colarse en una imagen firmada.
# Mixto: los | de los bloques de Ruby ({ |d| ... }) no son tuberias, y la
# cadena final de msfconsole si lo es pero pipefail la ROMPERIA, porque
# `head -n 1` cierra la tuberia antes de tiempo y los comandos de arriba reciben
# SIGPIPE. El objetivo de esa cadena es extraer la version, no propagar el
# estado de cada eslabon.
# hadolint ignore=DL4006
RUN /opt/ruby/bin/gem install bundler -v 2.5.22 --no-document \
 && /opt/ruby/bin/bundle _2.5.22_ config set --local without 'development test' \
 && /opt/ruby/bin/bundle _2.5.22_ install --jobs "$(nproc)" \
 && /opt/ruby/bin/bundle _2.5.22_ update concurrent-ruby \
 && /opt/ruby/bin/ruby -e 'require "rubygems"; min = Gem::Version.new("1.3.7"); Gem::Specification.dirs.each { |d| Dir.glob(File.join(d, "concurrent-ruby-*.gemspec")).each { |f| s = Gem::Specification.load(f); next unless s; next unless Gem::Version.new(s.version.to_s) < min; puts "borrando gemspec obsoleto #{File.basename(f)}"; File.delete(f) } }' \
 && /opt/ruby/bin/ruby -e 'g = Gem::Specification.find_by_name("concurrent-ruby"); v = Gem::Version.new(g.version.to_s); raise "concurrent-ruby #{g.version} por debajo de 1.3.7" if v < Gem::Version.new("1.3.7"); puts "concurrent-ruby=#{g.version}"' \
 && test "$(/opt/ruby/bin/ruby /src/msf/msfconsole --version 2>&1 | sed -e 's/\x1b\[[0-9;]*m//g' | grep -o '6\.5\.5' | head -n 1)" = "${MSF_VERSION}"
# wpscan va en un GEM_HOME aparte: comparte nokogiri con Metasploit, pero no
# toca su bundle bloqueado. Se compila en este stage porque es el unico con
# make y con el Ruby definitivo; la imagen final solo copia el resultado.
COPY scripts/install-full-wpscan.sh /usr/local/bin/install-full-wpscan
RUN chmod 0555 /usr/local/bin/install-full-wpscan \
 && WPSCAN_GEM_HOME=/out/wpscan-gems /usr/local/bin/install-full-wpscan
RUN mkdir -p /out \
 && cp -r /opt/ruby /out/ruby \
 && cp -r /src/msf /out/metasploit-framework \
 && rm -rf /out/metasploit-framework/.git

FROM ${FULL_BASE}
ARG UBUNTU_SNAPSHOT=20260925T000000Z
ARG PAT_COMMIT=3ac27901c711bdf3f5b65a7b1d1820a1f65bd09a
ARG EXPLOITDB_COMMIT=150aef0e7c4757c9dff33016c8352671cdc9b454
ARG SECLISTS_COMMIT=eccfbd405af82194e125a450a0076dbe4252d6f9
LABEL org.opencontainers.image.source="https://github.com/hackadvisermx/seclab-sbf" \
      org.opencontainers.image.title="seclab-sbf full" \
      org.opencontainers.image.version="0.1.0-phase7"
COPY scripts/install-full-packages.sh /usr/local/bin/install-full-packages
RUN chmod 0555 /usr/local/bin/install-full-packages \
 && SNAPSHOT_ID="${UBUNTU_SNAPSHOT}" PAT_COMMIT="${PAT_COMMIT}" EXPLOITDB_COMMIT="${EXPLOITDB_COMMIT}" SECLISTS_COMMIT="${SECLISTS_COMMIT}" /usr/local/bin/install-full-packages
COPY --from=msf-builder /out/ruby /opt/ruby
COPY --from=msf-builder /out/metasploit-framework /opt/metasploit-framework
# wpscan se compila en msf-builder (alli estan el Ruby definitivo y make) y se
# copia ya instalado. Su GEM_HOME va aparte para no tocar el bundle de msf.
COPY --from=msf-builder /out/wpscan-gems /opt/wpscan-gems
COPY scripts/wpscan-wrapper.sh /usr/local/bin/wpscan
RUN chmod 0555 /usr/local/bin/wpscan
# wpscan escribe su cache de bases de datos en ~/.cache y aborta con
# "Read-only file system" si no puede crearlo, porque /home/tester es de solo
# lectura en runtime. Mismo motivo y mismo patron que .msf4 y .nxc.
RUN ln -sfn /var/lib/seclab/tester/.cache /home/tester/.cache \
  && chown -h tester:tester /home/tester/.cache
RUN ln -sf /opt/metasploit-framework/msfconsole /usr/local/bin/msfconsole \
  && ln -sf /opt/metasploit-framework/msfvenom /usr/local/bin/msfvenom \
  && ln -sf /opt/metasploit-framework/msfdb /usr/local/bin/msfdb
# Metasploit necesita ~/.msf4 para cache, logs y loot, pero /home/tester
# es de solo lectura en runtime. El symlink se crea en build y apunta al
# volumen escribible; el entrypoint crea el destino.
RUN ln -sfn /var/lib/seclab/tester/.msf4 /home/tester/.msf4 \
  && chown -h tester:tester /home/tester/.msf4
COPY --from=go-builder /out/bettercap /usr/bin/bettercap
COPY --from=go-builder /out/s3scanner /usr/bin/s3scanner
COPY --from=nxc-builder /out/nxc /opt/nxc
COPY --from=nxc-builder /out/version /usr/local/share/seclab/netexec-version
# NetExec escribe ~/.nxc; mismo motivo que .msf4, symlink al volumen.
RUN ln -sf /opt/nxc/bin/nxc /usr/local/bin/nxc \
  && ln -sf /opt/nxc/bin/netexec /usr/local/bin/netexec \
  && ln -sf /opt/nxc/bin/nxcdb /usr/local/bin/nxcdb \
  && chmod 0555 /usr/local/bin/nxc /usr/local/bin/netexec /usr/local/bin/nxcdb \
  && ln -sfn /var/lib/seclab/tester/.nxc /home/tester/.nxc \
  && chown -h tester:tester /home/tester/.nxc
ENV PATH="/opt/ruby/bin:/opt/nxc/bin:${PATH}"
WORKDIR /workspace
ENTRYPOINT ["/usr/local/bin/light-entrypoint"]
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 CMD ["/usr/local/bin/light-healthcheck"]
CMD ["/bin/bash"]
