ARG BASE_IMAGE=seclab-sbf:base
ARG GO_BUILDER=docker.io/library/golang:1.25.13@sha256:cbff9d1a9041b316010f2da6b701b6c0d597718cb90928c85eb597334a0d23d4
ARG GO_UPSTREAM=docker.io/library/golang:1.26.8@sha256:6c2a5538f964f1c82f97ad14988bf05de100d922d159d0e398b54c7b0ca0c6c9
ARG SUBFINDER_VERSION=2.16.0
ARG SUBFINDER_COMMIT=b360529eebcd29345e44b3a9da3b2b0c04a13ff2
ARG HTTPX_VERSION=1.11.0
ARG HTTPX_COMMIT=c5f67adce6c57c05a6837ebb4f0eba8e81fdcf00
ARG KATANA_VERSION=1.7.0
ARG KATANA_COMMIT=17b0af27a79098a1634c915ca7fca51ed1171e41
ARG NUCLEI_VERSION=3.11.1
ARG NUCLEI_COMMIT=a8c88feb4a1c8e961b7902534ce3af97e9d524a4
ARG FFUF_VERSION=2.2.0
ARG FFUF_COMMIT=0aa36bcfa45c255f0d719f7d5bc58f7cc9c93659
ARG GOBUSTER_VERSION=3.8.2
ARG GOBUSTER_COMMIT=e8410cad6cacf08b82e2f610055f636f0be61c40
ARG NAABU_VERSION=2.6.1
ARG NAABU_COMMIT=5a0ca8bde91b5bb16213e9e8b5c6871eac954bd8
FROM --platform=$BUILDPLATFORM ${GO_BUILDER} AS fzf-builder
ARG FZF_VERSION=0.74.4
ARG FZF_COMMIT=a140afeb4d733cad3c96a56bf6db7e26853b6757
ARG TARGETOS
ARG TARGETARCH
RUN git init /src/fzf \
 && git -C /src/fzf remote add origin https://github.com/junegunn/fzf.git \
 && git -C /src/fzf fetch --depth 1 origin "${FZF_COMMIT}" \
 && git -C /src/fzf checkout --detach "${FZF_COMMIT}" \
 && test "$(git -C /src/fzf rev-parse HEAD)" = "${FZF_COMMIT}"
WORKDIR /src/fzf
RUN GOTOOLCHAIN=local go mod edit -go=1.25.0 \
 && GOTOOLCHAIN=local go get golang.org/x/sys@v0.44.0 \
 && GOTOOLCHAIN=local go mod download \
 && mkdir -p /out \
 && GOTOOLCHAIN=local CGO_ENABLED=0 GOOS="${TARGETOS}" GOARCH="${TARGETARCH}" \
      go build -mod=readonly -trimpath -buildvcs=false \
      -ldflags "-s -w -X main.version=${FZF_VERSION} -X main.revision=${FZF_COMMIT}" \
      -o /out/fzf .

FROM --platform=$BUILDPLATFORM ${GO_UPSTREAM} AS naabu-builder
ARG TARGETOS
ARG TARGETARCH
ARG NAABU_COMMIT
RUN apt-get update \
 && apt-get install -y --no-install-recommends gcc=4:14.2.0-1 libpcap-dev=1.10.5-2 \
 && if [ "$(dpkg --print-architecture)" = "arm64" ] && [ "${TARGETARCH}" = "amd64" ]; then \
      dpkg --add-architecture amd64 && apt-get update \
      && apt-get install -y --no-install-recommends gcc-x86-64-linux-gnu=4:14.2.0-1 libpcap-dev:amd64=1.10.5-2; \
    fi \
 && if [ "$(dpkg --print-architecture)" = "amd64" ] && [ "${TARGETARCH}" = "arm64" ]; then \
      dpkg --add-architecture arm64 && apt-get update \
      && apt-get install -y --no-install-recommends gcc-aarch64-linux-gnu=4:14.2.0-1 libpcap-dev:arm64=1.10.5-2; \
    fi \
 && rm -rf /var/lib/apt/lists/*
RUN git init /src/naabu \
 && git -C /src/naabu remote add origin https://github.com/projectdiscovery/naabu.git \
 && git -C /src/naabu fetch --depth 1 origin "${NAABU_COMMIT}" \
 && git -C /src/naabu checkout --detach "${NAABU_COMMIT}" \
 && test "$(git -C /src/naabu rev-parse HEAD)" = "${NAABU_COMMIT}"
WORKDIR /src/naabu
RUN GOTOOLCHAIN=local go mod edit -json >/dev/null \
 && if GOTOOLCHAIN=local go list -m golang.org/x/net >/dev/null 2>&1; then GOTOOLCHAIN=local go get golang.org/x/net@v0.56.0; fi \
 && if GOTOOLCHAIN=local go list -m golang.org/x/mod >/dev/null 2>&1; then GOTOOLCHAIN=local go get golang.org/x/mod@v0.40.0; fi \
 && if GOTOOLCHAIN=local go list -m github.com/jackc/pgx/v5 >/dev/null 2>&1; then GOTOOLCHAIN=local go get github.com/jackc/pgx/v5@v5.9.0; fi \
 && if GOTOOLCHAIN=local go list -m google.golang.org/grpc >/dev/null 2>&1; then GOTOOLCHAIN=local go get google.golang.org/grpc@v1.83.2; fi \
 && if GOTOOLCHAIN=local go list -m github.com/go-git/go-git/v5 >/dev/null 2>&1; then GOTOOLCHAIN=local go get github.com/go-git/go-git/v5@v5.19.2; fi \
 && if GOTOOLCHAIN=local go list -m golang.org/x/crypto >/dev/null 2>&1; then GOTOOLCHAIN=local go get golang.org/x/crypto@v0.56.0; fi \
 && GOTOOLCHAIN=local go mod tidy
RUN mkdir -p /out \
 && if [ "${TARGETARCH}" = "$(GOTOOLCHAIN=local go env GOARCH)" ]; then \
      GOTOOLCHAIN=local CGO_ENABLED=1 CC=gcc GOOS="${TARGETOS}" GOARCH="${TARGETARCH}" \
        go build -mod=readonly -trimpath -buildvcs=false \
        -ldflags "-s -w" \
        -o /out/naabu ./cmd/naabu; \
    elif [ "${TARGETARCH}" = "amd64" ]; then \
      GOTOOLCHAIN=local CGO_ENABLED=1 CC=x86_64-linux-gnu-gcc CGO_LDFLAGS="-L/usr/lib/x86_64-linux-gnu" GOOS=linux GOARCH=amd64 \
        go build -mod=readonly -trimpath -buildvcs=false \
        -ldflags "-s -w" \
        -o /out/naabu ./cmd/naabu; \
    else \
      GOTOOLCHAIN=local CGO_ENABLED=1 CC=aarch64-linux-gnu-gcc CGO_LDFLAGS="-L/usr/lib/aarch64-linux-gnu" GOOS=linux GOARCH=arm64 \
        go build -mod=readonly -trimpath -buildvcs=false \
        -ldflags "-s -w" \
        -o /out/naabu ./cmd/naabu; \
    fi
FROM --platform=$BUILDPLATFORM ${GO_UPSTREAM} AS upstream-builder
ARG TARGETOS
ARG TARGETARCH
ARG SUBFINDER_COMMIT
ARG HTTPX_COMMIT
ARG KATANA_COMMIT
ARG NUCLEI_COMMIT
ARG FFUF_COMMIT
ARG GOBUSTER_COMMIT
RUN git init /src/subfinder \
 && git -C /src/subfinder remote add origin https://github.com/projectdiscovery/subfinder.git \
 && git -C /src/subfinder fetch --depth 1 origin "${SUBFINDER_COMMIT}" \
 && git -C /src/subfinder checkout --detach "${SUBFINDER_COMMIT}" \
 && test "$(git -C /src/subfinder rev-parse HEAD)" = "${SUBFINDER_COMMIT}"
WORKDIR /src/subfinder
RUN GOTOOLCHAIN=local go mod edit -json >/dev/null \
 && if GOTOOLCHAIN=local go list -m golang.org/x/net >/dev/null 2>&1; then GOTOOLCHAIN=local go get golang.org/x/net@v0.56.0; fi \
 && if GOTOOLCHAIN=local go list -m golang.org/x/mod >/dev/null 2>&1; then GOTOOLCHAIN=local go get golang.org/x/mod@v0.40.0; fi \
 && if GOTOOLCHAIN=local go list -m github.com/jackc/pgx/v5 >/dev/null 2>&1; then GOTOOLCHAIN=local go get github.com/jackc/pgx/v5@v5.9.0; fi \
 && if GOTOOLCHAIN=local go list -m google.golang.org/grpc >/dev/null 2>&1; then GOTOOLCHAIN=local go get google.golang.org/grpc@v1.83.2; fi \
 && if GOTOOLCHAIN=local go list -m github.com/go-git/go-git/v5 >/dev/null 2>&1; then GOTOOLCHAIN=local go get github.com/go-git/go-git/v5@v5.19.2; fi \
 && if GOTOOLCHAIN=local go list -m golang.org/x/crypto >/dev/null 2>&1; then GOTOOLCHAIN=local go get golang.org/x/crypto@v0.56.0; fi \
 && GOTOOLCHAIN=local go mod tidy
RUN mkdir -p /out \
 && GOTOOLCHAIN=local CGO_ENABLED=0 GOOS="${TARGETOS}" GOARCH="${TARGETARCH}" \
      go build -mod=readonly -trimpath -buildvcs=false \
      -ldflags "-s -w" \
      -o /out/subfinder ./cmd/subfinder
RUN git init /src/httpx \
 && git -C /src/httpx remote add origin https://github.com/projectdiscovery/httpx.git \
 && git -C /src/httpx fetch --depth 1 origin "${HTTPX_COMMIT}" \
 && git -C /src/httpx checkout --detach "${HTTPX_COMMIT}" \
 && test "$(git -C /src/httpx rev-parse HEAD)" = "${HTTPX_COMMIT}"
WORKDIR /src/httpx
RUN GOTOOLCHAIN=local go mod edit -json >/dev/null \
 && if GOTOOLCHAIN=local go list -m golang.org/x/net >/dev/null 2>&1; then GOTOOLCHAIN=local go get golang.org/x/net@v0.56.0; fi \
 && if GOTOOLCHAIN=local go list -m golang.org/x/mod >/dev/null 2>&1; then GOTOOLCHAIN=local go get golang.org/x/mod@v0.40.0; fi \
 && if GOTOOLCHAIN=local go list -m github.com/jackc/pgx/v5 >/dev/null 2>&1; then GOTOOLCHAIN=local go get github.com/jackc/pgx/v5@v5.9.0; fi \
 && if GOTOOLCHAIN=local go list -m google.golang.org/grpc >/dev/null 2>&1; then GOTOOLCHAIN=local go get google.golang.org/grpc@v1.83.2; fi \
 && if GOTOOLCHAIN=local go list -m github.com/go-git/go-git/v5 >/dev/null 2>&1; then GOTOOLCHAIN=local go get github.com/go-git/go-git/v5@v5.19.2; fi \
 && if GOTOOLCHAIN=local go list -m golang.org/x/crypto >/dev/null 2>&1; then GOTOOLCHAIN=local go get golang.org/x/crypto@v0.56.0; fi \
 && GOTOOLCHAIN=local go mod tidy
RUN GOTOOLCHAIN=local CGO_ENABLED=0 GOOS="${TARGETOS}" GOARCH="${TARGETARCH}" \
      go build -mod=readonly -trimpath -buildvcs=false \
      -ldflags "-s -w" \
      -o /out/httpx ./cmd/httpx
RUN git init /src/katana \
 && git -C /src/katana remote add origin https://github.com/projectdiscovery/katana.git \
 && git -C /src/katana fetch --depth 1 origin "${KATANA_COMMIT}" \
 && git -C /src/katana checkout --detach "${KATANA_COMMIT}" \
 && test "$(git -C /src/katana rev-parse HEAD)" = "${KATANA_COMMIT}"
WORKDIR /src/katana
RUN GOTOOLCHAIN=local go mod edit -json >/dev/null \
 && if GOTOOLCHAIN=local go list -m golang.org/x/net >/dev/null 2>&1; then GOTOOLCHAIN=local go get golang.org/x/net@v0.56.0; fi \
 && if GOTOOLCHAIN=local go list -m golang.org/x/mod >/dev/null 2>&1; then GOTOOLCHAIN=local go get golang.org/x/mod@v0.40.0; fi \
 && if GOTOOLCHAIN=local go list -m github.com/jackc/pgx/v5 >/dev/null 2>&1; then GOTOOLCHAIN=local go get github.com/jackc/pgx/v5@v5.9.0; fi \
 && if GOTOOLCHAIN=local go list -m google.golang.org/grpc >/dev/null 2>&1; then GOTOOLCHAIN=local go get google.golang.org/grpc@v1.83.2; fi \
 && if GOTOOLCHAIN=local go list -m github.com/go-git/go-git/v5 >/dev/null 2>&1; then GOTOOLCHAIN=local go get github.com/go-git/go-git/v5@v5.19.2; fi \
 && if GOTOOLCHAIN=local go list -m golang.org/x/crypto >/dev/null 2>&1; then GOTOOLCHAIN=local go get golang.org/x/crypto@v0.56.0; fi \
 && GOTOOLCHAIN=local go mod tidy
RUN GOTOOLCHAIN=local CGO_ENABLED=0 GOOS="${TARGETOS}" GOARCH="${TARGETARCH}" \
      go build -mod=readonly -trimpath -buildvcs=false \
      -ldflags "-s -w" \
      -o /out/katana ./cmd/katana
RUN git init /src/nuclei \
 && git -C /src/nuclei remote add origin https://github.com/projectdiscovery/nuclei.git \
 && git -C /src/nuclei fetch --depth 1 origin "${NUCLEI_COMMIT}" \
 && git -C /src/nuclei checkout --detach "${NUCLEI_COMMIT}" \
 && test "$(git -C /src/nuclei rev-parse HEAD)" = "${NUCLEI_COMMIT}"
WORKDIR /src/nuclei
RUN GOTOOLCHAIN=local go mod edit -json >/dev/null \
 && if GOTOOLCHAIN=local go list -m golang.org/x/net >/dev/null 2>&1; then GOTOOLCHAIN=local go get golang.org/x/net@v0.56.0; fi \
 && if GOTOOLCHAIN=local go list -m golang.org/x/mod >/dev/null 2>&1; then GOTOOLCHAIN=local go get golang.org/x/mod@v0.40.0; fi \
 && if GOTOOLCHAIN=local go list -m github.com/jackc/pgx/v5 >/dev/null 2>&1; then GOTOOLCHAIN=local go get github.com/jackc/pgx/v5@v5.9.0; fi \
 && if GOTOOLCHAIN=local go list -m google.golang.org/grpc >/dev/null 2>&1; then GOTOOLCHAIN=local go get google.golang.org/grpc@v1.83.2; fi \
 && if GOTOOLCHAIN=local go list -m github.com/go-git/go-git/v5 >/dev/null 2>&1; then GOTOOLCHAIN=local go get github.com/go-git/go-git/v5@v5.19.2; fi \
 && if GOTOOLCHAIN=local go list -m golang.org/x/crypto >/dev/null 2>&1; then GOTOOLCHAIN=local go get golang.org/x/crypto@v0.56.0; fi \
 && GOTOOLCHAIN=local go mod tidy
RUN GOTOOLCHAIN=local CGO_ENABLED=0 GOOS="${TARGETOS}" GOARCH="${TARGETARCH}" \
      go build -mod=readonly -trimpath -buildvcs=false \
      -ldflags "-s -w" \
      -o /out/nuclei ./cmd/nuclei
RUN git init /src/ffuf \
 && git -C /src/ffuf remote add origin https://github.com/ffuf/ffuf.git \
 && git -C /src/ffuf fetch --depth 1 origin "${FFUF_COMMIT}" \
 && git -C /src/ffuf checkout --detach "${FFUF_COMMIT}" \
 && test "$(git -C /src/ffuf rev-parse HEAD)" = "${FFUF_COMMIT}"
WORKDIR /src/ffuf
RUN GOTOOLCHAIN=local go mod edit -json >/dev/null \
 && if GOTOOLCHAIN=local go list -m golang.org/x/net >/dev/null 2>&1; then GOTOOLCHAIN=local go get golang.org/x/net@v0.56.0; fi \
 && if GOTOOLCHAIN=local go list -m golang.org/x/mod >/dev/null 2>&1; then GOTOOLCHAIN=local go get golang.org/x/mod@v0.40.0; fi \
 && if GOTOOLCHAIN=local go list -m github.com/jackc/pgx/v5 >/dev/null 2>&1; then GOTOOLCHAIN=local go get github.com/jackc/pgx/v5@v5.9.0; fi \
 && if GOTOOLCHAIN=local go list -m google.golang.org/grpc >/dev/null 2>&1; then GOTOOLCHAIN=local go get google.golang.org/grpc@v1.83.2; fi \
 && if GOTOOLCHAIN=local go list -m github.com/go-git/go-git/v5 >/dev/null 2>&1; then GOTOOLCHAIN=local go get github.com/go-git/go-git/v5@v5.19.2; fi \
 && if GOTOOLCHAIN=local go list -m golang.org/x/crypto >/dev/null 2>&1; then GOTOOLCHAIN=local go get golang.org/x/crypto@v0.56.0; fi \
 && GOTOOLCHAIN=local go mod tidy
RUN GOTOOLCHAIN=local CGO_ENABLED=0 GOOS="${TARGETOS}" GOARCH="${TARGETARCH}" \
      go build -mod=readonly -trimpath -buildvcs=false \
      -ldflags "-s -w" \
      -o /out/ffuf .
RUN git init /src/gobuster \
 && git -C /src/gobuster remote add origin https://github.com/OJ/gobuster.git \
 && git -C /src/gobuster fetch --depth 1 origin "${GOBUSTER_COMMIT}" \
 && git -C /src/gobuster checkout --detach "${GOBUSTER_COMMIT}" \
 && test "$(git -C /src/gobuster rev-parse HEAD)" = "${GOBUSTER_COMMIT}"
WORKDIR /src/gobuster
RUN GOTOOLCHAIN=local go mod edit -json >/dev/null \
 && if GOTOOLCHAIN=local go list -m golang.org/x/net >/dev/null 2>&1; then GOTOOLCHAIN=local go get golang.org/x/net@v0.56.0; fi \
 && if GOTOOLCHAIN=local go list -m golang.org/x/mod >/dev/null 2>&1; then GOTOOLCHAIN=local go get golang.org/x/mod@v0.40.0; fi \
 && if GOTOOLCHAIN=local go list -m github.com/jackc/pgx/v5 >/dev/null 2>&1; then GOTOOLCHAIN=local go get github.com/jackc/pgx/v5@v5.9.0; fi \
 && if GOTOOLCHAIN=local go list -m google.golang.org/grpc >/dev/null 2>&1; then GOTOOLCHAIN=local go get google.golang.org/grpc@v1.83.2; fi \
 && if GOTOOLCHAIN=local go list -m github.com/go-git/go-git/v5 >/dev/null 2>&1; then GOTOOLCHAIN=local go get github.com/go-git/go-git/v5@v5.19.2; fi \
 && if GOTOOLCHAIN=local go list -m golang.org/x/crypto >/dev/null 2>&1; then GOTOOLCHAIN=local go get golang.org/x/crypto@v0.56.0; fi \
 && GOTOOLCHAIN=local go mod tidy
RUN GOTOOLCHAIN=local CGO_ENABLED=0 GOOS="${TARGETOS}" GOARCH="${TARGETARCH}" \
      go build -mod=readonly -trimpath -buildvcs=false \
      -ldflags "-s -w" \
      -o /out/gobuster .

FROM ${BASE_IMAGE}
ARG UBUNTU_SNAPSHOT=20260922T000000Z
LABEL org.opencontainers.image.source="https://github.com/hackadvisermx/seclab-sbf" \
      org.opencontainers.image.title="seclab-sbf light" \
      org.opencontainers.image.version="0.3.0-phase3"
COPY scripts/install-light-packages.sh /usr/local/bin/install-light-packages
COPY scripts/pwntools-requirements-aarch64.txt scripts/pwntools-requirements-x86_64.txt /tmp/
RUN chmod 0555 /usr/local/bin/install-light-packages \
 && SNAPSHOT_ID="${UBUNTU_SNAPSHOT}" /usr/local/bin/install-light-packages
COPY --from=fzf-builder /out/fzf /usr/bin/fzf
COPY --from=naabu-builder /out/naabu /usr/bin/naabu
COPY --from=upstream-builder /out/subfinder /usr/bin/subfinder
COPY --from=upstream-builder /out/httpx /usr/bin/httpx
COPY --from=upstream-builder /out/katana /usr/bin/katana
COPY --from=upstream-builder /out/nuclei /usr/bin/nuclei
COPY --from=upstream-builder /out/ffuf /usr/bin/ffuf
COPY --from=upstream-builder /out/gobuster /usr/bin/gobuster
COPY shell/tools.json /usr/local/share/seclab/tools.json
COPY shell/zshrc /usr/local/share/seclab/zshrc
COPY shell/pentest-lab /usr/local/share/seclab/pentest-lab
COPY scripts/install-shell.sh /usr/local/bin/install-shell
RUN usermod --login tester --home /home/tester --move-home --shell /usr/bin/zsh ubuntu \
 && groupmod --new-name tester ubuntu \
 && usermod --groups tester tester \
 && install -d -m 0755 /home/tester \
 && install -d -m 0700 /var/lib/seclab/ssh \
 && chown tester:tester /home/tester
COPY .tmux.conf /home/tester/.tmux.conf
RUN chown root:root /home/tester/.tmux.conf \
 && chmod 0444 /home/tester/.tmux.conf
RUN chmod 0555 /usr/local/bin/install-shell \
 && OH_MY_ZSH_COMMIT=74965c96098134b192f00084f966b4b02438a739 \
    ZSH_AUTOSUGGESTIONS_COMMIT=85919cd1ffa7d2d5412f6d3fe437ebdbeeec4fc5 \
    ZSH_SYNTAX_HIGHLIGHTING_COMMIT=0bfcb582e71d3abe604ce67bc0fe5a21f377507e \
    ZSH_COMPLETIONS_COMMIT=b5e8e0a22deb05a807bb8655aef809a29f3cffed \
    ZOXIDE_PLUGIN_COMMIT=09a18b4424b3f1033094ffd97da6d47585e38259 \
    /usr/local/bin/install-shell \
  && install -m 0644 -o tester -g tester /usr/local/share/seclab/zshrc /home/tester/.zshrc
COPY security/ssh/sshd_config /etc/ssh/sshd_config.seclab

COPY scripts/entrypoint/light-entrypoint.sh /usr/local/bin/light-entrypoint
COPY scripts/entrypoint/ttyd-as-tester.sh /usr/local/bin/ttyd-as-tester
COPY scripts/entrypoint/ttyd-as-tester-shell.sh /usr/local/bin/ttyd-as-tester-shell
COPY scripts/vpn-manager.sh /usr/local/bin/vpn-manager
COPY scripts/vpn-control.py /usr/local/bin/vpn-control
COPY scripts/proxy-control.py /usr/local/bin/pt-forward
COPY scripts/health/light-healthcheck.sh /usr/local/bin/light-healthcheck
RUN chmod 0555 /usr/local/bin/light-entrypoint /usr/local/bin/ttyd-as-tester /usr/local/bin/ttyd-as-tester-shell /usr/local/bin/vpn-manager /usr/local/bin/vpn-control /usr/local/bin/pt-forward /usr/local/bin/light-healthcheck
WORKDIR /workspace
ENTRYPOINT ["/usr/local/bin/light-entrypoint"]
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 CMD ["/usr/local/bin/light-healthcheck"]
CMD ["/bin/bash"]
