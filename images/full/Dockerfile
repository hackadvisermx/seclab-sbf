ARG FULL_BASE=seclab-sbf:light
ARG UBUNTU_IMAGE=docker.io/library/ubuntu:24.04@sha256:008173c23f95b170204355c12626cb5a965d779a7e1283b09e9cffbb1bf33ca3
ARG UBUNTU_SNAPSHOT=20260922T000000Z
ARG RUBY_VERSION=3.3.8
ARG RUBY_SHA256=5ae28a87a59a3e4ad66bc2931d232dbab953d0aa8f6baf3bc4f8f80977c89cab
ARG MSF_VERSION=6.5.5
ARG MSF_COMMIT=c5429ba817d12d9d89069387142332435598e548
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
 && test "$(git -C /src/nxc describe --tags --exact-match 2>/dev/null || printf v${NXC_VERSION})" = "v${NXC_VERSION}"
RUN python3 -m venv /opt/nxc \
 && /opt/nxc/bin/pip install --no-cache-dir --upgrade pip \
 && /opt/nxc/bin/pip install --no-cache-dir "git+https://github.com/Pennyw0rth/NetExec.git@${NXC_COMMIT}" \
 && /opt/nxc/bin/python -c 'import nxc.netexec, nxc.nxcdb' \
 && mkdir -p /out \
 && cp -r /opt/nxc /out/nxc \
 && printf '%s\n' "${NXC_VERSION}" > /out/version \
 && /opt/nxc/bin/pip freeze --all > /out/frozen.txt

# Sin --platform=$BUILDPLATFORM: Ruby y Metasploit no se pueden cross-compilar,
# asi que este stage tiene que compilar para la plataforma destino. Con
# $BUILDPLATFORM la imagen arm64 llevaba un Ruby amd64 dentro y msfconsole no
# arrancaba. Solo lo enmascara en builds locales, donde build platform y
# destino coinciden.
FROM ${UBUNTU_IMAGE} AS msf-builder
ARG UBUNTU_SNAPSHOT
ARG RUBY_VERSION
ARG RUBY_SHA256
ARG MSF_VERSION
ARG MSF_COMMIT
ENV DEBIAN_FRONTEND=noninteractive
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
RUN curl --fail --location --proto '=https' --tlsv1.2 --retry 3 \
      "https://cache.ruby-lang.org/pub/ruby/${RUBY_VERSION%.*}/ruby-${RUBY_VERSION}.tar.gz" \
      --output /tmp/ruby.tar.gz \
 && printf '%s  %s\n' "${RUBY_SHA256}" /tmp/ruby.tar.gz | sha256sum -c - \
 && rm -rf /tmp/ruby && mkdir /tmp/ruby && tar -xzf /tmp/ruby.tar.gz -C /tmp/ruby \
 && cd "/tmp/ruby/ruby-${RUBY_VERSION}" \
 && ./configure --disable-install-doc --prefix=/opt/ruby \
 && make -j"$(nproc)" \
 && make install \
 && /opt/ruby/bin/ruby -v | grep -q "${RUBY_VERSION}" \
 && cd / && rm -rf /tmp/ruby /tmp/ruby.tar.gz
RUN git init /src/msf \
 && git -C /src/msf remote add origin https://github.com/rapid7/metasploit-framework.git \
 && git -C /src/msf fetch --depth 1 origin "refs/tags/${MSF_VERSION}:refs/tags/${MSF_VERSION}" \
 && git -C /src/msf checkout --detach "refs/tags/${MSF_VERSION}" \
 && test "$(git -C /src/msf rev-parse HEAD)" = "${MSF_COMMIT}"
WORKDIR /src/msf
RUN /opt/ruby/bin/gem install bundler -v 2.5.22 --no-document \
 && /opt/ruby/bin/bundle _2.5.22_ config set --local without 'development test' \
 && /opt/ruby/bin/bundle _2.5.22_ install --jobs "$(nproc)" \
 && test "$(/opt/ruby/bin/ruby /src/msf/msfconsole --version 2>&1 | sed -e 's/\x1b\[[0-9;]*m//g' | grep -o '6\.5\.5' | head -n 1)" = "${MSF_VERSION}"
RUN mkdir -p /out \
 && cp -r /opt/ruby /out/ruby \
 && cp -r /src/msf /out/metasploit-framework \
 && rm -rf /out/metasploit-framework/.git

FROM ${FULL_BASE}
ARG UBUNTU_SNAPSHOT=20260922T000000Z
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
RUN ln -sf /opt/metasploit-framework/msfconsole /usr/local/bin/msfconsole \
  && ln -sf /opt/metasploit-framework/msfvenom /usr/local/bin/msfvenom \
  && ln -sf /opt/metasploit-framework/msfdb /usr/local/bin/msfdb
# Metasploit necesita ~/.msf4 para cache, logs y loot, pero /home/tester
# es de solo lectura en runtime. El symlink se crea en build y apunta al
# volumen escribible; el entrypoint crea el destino.
RUN ln -sfn /var/lib/seclab/tester/.msf4 /home/tester/.msf4 \
  && chown -h tester:tester /home/tester/.msf4
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
