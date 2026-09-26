ARG FULL_BASE=seclab-sbf:light
ARG UBUNTU_IMAGE=docker.io/library/ubuntu:24.04@sha256:008173c23f95b170204355c12626cb5a965d779a7e1283b09e9cffbb1bf33ca3
ARG UBUNTU_SNAPSHOT=20260922T000000Z
ARG RUBY_VERSION=3.3.8
ARG RUBY_SHA256=5ae28a87a59a3e4ad66bc2931d232dbab953d0aa8f6baf3bc4f8f80977c89cab
ARG MSF_VERSION=6.5.5
ARG MSF_COMMIT=c5429ba817d12d9d89069387142332435598e548
ARG PAT_COMMIT=3ac27901c711bdf3f5b65a7b1d1820a1f65bd09a
ARG EXPLOITDB_COMMIT=150aef0e7c4757c9dff33016c8352671cdc9b454
FROM --platform=$BUILDPLATFORM ${UBUNTU_IMAGE} AS msf-builder
ARG TARGETOS
ARG TARGETARCH
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
ENV PATH="/opt/ruby/bin:${PATH}"
WORKDIR /workspace
ENTRYPOINT ["/usr/local/bin/light-entrypoint"]
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 CMD ["/usr/local/bin/light-healthcheck"]
CMD ["/bin/bash"]
