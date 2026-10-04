# Imagen unica del laboratorio. Antes eran images/light y images/full: full
# hacia FROM light, asi que light ya era un subconjunto y la imagen final
# contenia todo lo suyo. Se fusionaron en este fichero el 2026-09-29.
#
# Orden: los builders que corren en BUILDPLATFORM (que compilan Go para la
# arquitectura destino) y los que corren en TARGETPLATFORM (necesitan correr
# alli porque compilan con cgo o esn su toolchain), y al final la imagen.
ARG UBUNTU_IMAGE=docker.io/library/ubuntu:26.04@sha256:da6fc2be547864451aa253836dd926da33623312df4a9a243e35dc877c378a78
ARG UBUNTU_SNAPSHOT=20261005T000000Z
ARG RUBY_VERSION=3.3.8
ARG RUBY_SHA256=5ae28a87a59a3e4ad66bc2931d232dbab953d0aa8f6baf3bc4f8f80977c89cab
ARG MSF_VERSION=6.5.5
ARG MSF_COMMIT=c5429ba817d12d9d89069387142332435598e548
# Dos toolchains de Go, como antes de fusionar: fzf se compilaba con
# 1.25.13 y el resto con 1.26.8. GO_BUILDER solo lo usa fzf-builder;
# naabu, upstream y go (bettercap, s3scanner) usan GO_UPSTREAM.
ARG GO_BUILDER=docker.io/library/golang:1.25.13@sha256:cbff9d1a9041b316010f2da6b701b6c0d597718cb90928c85eb597334a0d23d4
ARG BETTERCAP_VERSION=2.41.7
ARG BETTERCAP_COMMIT=dfe56780bb342b6a6715c9557a2cefe1f13d805c
ARG S3SCANNER_VERSION=3.1.1
ARG S3SCANNER_COMMIT=9c61311a2f7610e523cfc8194abb98ab96c584d2
ARG PAT_COMMIT=3ac27901c711bdf3f5b65a7b1d1820a1f65bd09a
ARG EXPLOITDB_COMMIT=150aef0e7c4757c9dff33016c8352671cdc9b454
ARG NXC_VERSION=1.5.1
ARG NXC_COMMIT=c7dc286ba65daf10402cdc470e531b84e6d3d911
ARG PSPY_VERSION=1.2.1
ARG PSPY_COMMIT=f9e6a1590a4312b9faa093d8dc84e19567977a6d
ARG SECLISTS_COMMIT=eccfbd405af82194e125a450a0076dbe4252d6f9
ARG BASE_IMAGE=seclab-sbf:base
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
ARG DNSX_VERSION=1.3.1
ARG DNSX_COMMIT=01e315f216db7d36198ec326fac13dd7846b1bec
ARG ANEW_VERSION=0.1.1
ARG ANEW_COMMIT=26ebc8ce1f0bdbaaee2930ea7ab191ed0c0da261
ARG WAYBACKURLS_VERSION=0.1.0
ARG WAYBACKURLS_COMMIT=86aeb97852707e1a6fb3bcd33e61d5433a6476c5
ARG NAABU_VERSION=2.6.1
ARG NAABU_COMMIT=5a0ca8bde91b5bb16213e9e8b5c6871eac954bd8
ARG CHISEL_VERSION=1.12.0
ARG CHISEL_COMMIT=fe4f4fe7e6a849b4aa6d1b8ee47037e16033f42a
ARG LIGOLO_VERSION=0.9.2
ARG LIGOLO_COMMIT=e543732f4be6dc899096ae322ae620bf010bfbfc
ARG GF_VERSION=0.1.0
ARG GF_COMMIT=dcd4c361f9f5ba302294ed38b8ce278e8ba69006
ARG QSREPLACE_VERSION=0.0.3
ARG QSREPLACE_COMMIT=320475befaf66d986400aa8c3ed9b43e0b6b5a02
ARG GF_PATTERNS_COMMIT=f686f06ae647726578920084c894100d702496cc
ARG ASSETFINDER_VERSION=0.1.1
ARG ASSETFINDER_COMMIT=4e95d8701aae8cff1c27af2626eb22ba110ad583
ARG HTTPROBE_VERSION=0.2
ARG HTTPROBE_COMMIT=7e8abdb4096ab224f21616478b699b4dfda9d409

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
RUN --mount=type=cache,target=/go/pkg/mod --mount=type=cache,target=/root/.cache/go-build GOTOOLCHAIN=local go mod edit -go=1.25.0 \
 && GOTOOLCHAIN=local go get golang.org/x/sys@v0.44.0 \
 && GOTOOLCHAIN=local go mod download \
 && mkdir -p /out \
 && GOTOOLCHAIN=local CGO_ENABLED=0 GOOS="${TARGETOS}" GOARCH="${TARGETARCH}" \
      go build -mod=readonly -trimpath -buildvcs=false \
      -ldflags "-s -w -X main.version=${FZF_VERSION} -X main.revision=${FZF_COMMIT}" \
      -o /out/fzf .

FROM --platform=$BUILDPLATFORM ${GO_UPSTREAM} AS pspy-builder
ARG TARGETOS
ARG TARGETARCH
ARG PSPY_VERSION
ARG PSPY_COMMIT
# pspy NO tiene release para arm64: la v1.2.1 publica pspy32, pspy32s, pspy64
# y pspy64s, y `file` sobre pspy64 da "ELF 64-bit x86-64". No hay release con
# aarch64 en ninguna version, asi que la unica via en arm64 es compilarlo, que
# es lo que hace este stage. El resto del repo hace lo mismo con naabu,
# bettercap y s3scanner.
#
# CGO_ENABLED=0 porque es Go puro y el binario tiene que ser estatico: no
# quiero enlazar contra nada de la imagen golang (que es Debian trixie) en un
# binario que luego corre en Ubuntu. Es el mismo motivo que fzf.
RUN git init /src/pspy \
 && git -C /src/pspy remote add origin https://github.com/DominicBreuker/pspy.git \
 && git -C /src/pspy fetch --depth 1 origin "${PSPY_COMMIT}" \
 && git -C /src/pspy checkout --detach FETCH_HEAD \
 && test "$(git -C /src/pspy rev-parse HEAD)" = "${PSPY_COMMIT}" \
 && test "$(git -C /src/pspy describe --tags --exact-match 2>/dev/null || printf 'v%s' "${PSPY_VERSION}")" = "v${PSPY_VERSION}"
WORKDIR /src/pspy
RUN GOTOOLCHAIN=local CGO_ENABLED=0 GOOS="${TARGETOS}" GOARCH="${TARGETARCH}" \
      go build -mod=readonly -trimpath -buildvcs=false -ldflags "-s -w" -o /out/pspy .

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
RUN --mount=type=cache,target=/go/pkg/mod --mount=type=cache,target=/root/.cache/go-build GOTOOLCHAIN=local go mod edit -json >/dev/null \
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
ARG DNSX_COMMIT
ARG ANEW_COMMIT
ARG WAYBACKURLS_COMMIT
ARG CHISEL_VERSION
ARG CHISEL_COMMIT
ARG LIGOLO_VERSION
ARG LIGOLO_COMMIT
ARG GF_COMMIT
ARG QSREPLACE_COMMIT
ARG GF_PATTERNS_COMMIT
ARG ASSETFINDER_COMMIT
ARG HTTPROBE_COMMIT
RUN git init /src/subfinder \
 && git -C /src/subfinder remote add origin https://github.com/projectdiscovery/subfinder.git \
 && git -C /src/subfinder fetch --depth 1 origin "${SUBFINDER_COMMIT}" \
 && git -C /src/subfinder checkout --detach "${SUBFINDER_COMMIT}" \
 && test "$(git -C /src/subfinder rev-parse HEAD)" = "${SUBFINDER_COMMIT}"
WORKDIR /src/subfinder
RUN --mount=type=cache,target=/go/pkg/mod --mount=type=cache,target=/root/.cache/go-build GOTOOLCHAIN=local go mod edit -json >/dev/null \
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
RUN --mount=type=cache,target=/go/pkg/mod --mount=type=cache,target=/root/.cache/go-build GOTOOLCHAIN=local go mod edit -json >/dev/null \
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
RUN --mount=type=cache,target=/go/pkg/mod --mount=type=cache,target=/root/.cache/go-build GOTOOLCHAIN=local go mod edit -json >/dev/null \
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
RUN --mount=type=cache,target=/go/pkg/mod --mount=type=cache,target=/root/.cache/go-build GOTOOLCHAIN=local go mod edit -json >/dev/null \
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
RUN --mount=type=cache,target=/go/pkg/mod --mount=type=cache,target=/root/.cache/go-build GOTOOLCHAIN=local go mod edit -json >/dev/null \
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
RUN --mount=type=cache,target=/go/pkg/mod --mount=type=cache,target=/root/.cache/go-build GOTOOLCHAIN=local go mod edit -json >/dev/null \
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
RUN git init /src/dnsx \
 && git -C /src/dnsx remote add origin https://github.com/projectdiscovery/dnsx.git \
 && git -C /src/dnsx fetch --depth 1 origin "${DNSX_COMMIT}" \
 && git -C /src/dnsx checkout --detach "${DNSX_COMMIT}" \
 && test "$(git -C /src/dnsx rev-parse HEAD)" = "${DNSX_COMMIT}"
WORKDIR /src/dnsx
# dnsx arrastra x/net, x/mod y x/crypto mas viejos que los que ya fijamos
# para las demas herramientas del mismo autor; se suben al mismo valor.
RUN --mount=type=cache,target=/go/pkg/mod --mount=type=cache,target=/root/.cache/go-build GOTOOLCHAIN=local go mod edit -json >/dev/null \
 && if GOTOOLCHAIN=local go list -m golang.org/x/net >/dev/null 2>&1; then GOTOOLCHAIN=local go get golang.org/x/net@v0.56.0; fi \
 && if GOTOOLCHAIN=local go list -m golang.org/x/mod >/dev/null 2>&1; then GOTOOLCHAIN=local go get golang.org/x/mod@v0.40.0; fi \
 && if GOTOOLCHAIN=local go list -m golang.org/x/crypto >/dev/null 2>&1; then GOTOOLCHAIN=local go get golang.org/x/crypto@v0.56.0; fi \
 && GOTOOLCHAIN=local go mod tidy
RUN mkdir -p /out \
 && GOTOOLCHAIN=local CGO_ENABLED=0 GOOS="${TARGETOS}" GOARCH="${TARGETARCH}" \
      go build -mod=readonly -trimpath -buildvcs=false \
      -ldflags "-s -w" \
      -o /out/dnsx ./cmd/dnsx
# anew y waybackurls no tienen dependencias: solo biblioteca estandar de Go.
RUN git init /src/anew \
 && git -C /src/anew remote add origin https://github.com/tomnomnom/anew.git \
 && git -C /src/anew fetch --depth 1 origin "${ANEW_COMMIT}" \
 && git -C /src/anew checkout --detach "${ANEW_COMMIT}" \
 && test "$(git -C /src/anew rev-parse HEAD)" = "${ANEW_COMMIT}"
WORKDIR /src/anew
RUN mkdir -p /out \
 && GOTOOLCHAIN=local CGO_ENABLED=0 GOOS="${TARGETOS}" GOARCH="${TARGETARCH}" \
      go build -mod=readonly -trimpath -buildvcs=false \
      -ldflags "-s -w" \
      -o /out/anew .
RUN git init /src/waybackurls \
 && git -C /src/waybackurls remote add origin https://github.com/tomnomnom/waybackurls.git \
 && git -C /src/waybackurls fetch --depth 1 origin "${WAYBACKURLS_COMMIT}" \
 && git -C /src/waybackurls checkout --detach "${WAYBACKURLS_COMMIT}" \
 && test "$(git -C /src/waybackurls rev-parse HEAD)" = "${WAYBACKURLS_COMMIT}"
WORKDIR /src/waybackurls
RUN mkdir -p /out \
 && GOTOOLCHAIN=local CGO_ENABLED=0 GOOS="${TARGETOS}" GOARCH="${TARGETARCH}" \
      go build -mod=readonly -trimpath -buildvcs=false \
      -ldflags "-s -w" \
      -o /out/waybackurls .
RUN git init /src/gf \
 && git -C /src/gf remote add origin https://github.com/tomnomnom/gf.git \
 && git -C /src/gf fetch --depth 1 origin "${GF_COMMIT}" \
 && git -C /src/gf checkout --detach "${GF_COMMIT}" \
 && test "$(git -C /src/gf rev-parse HEAD)" = "${GF_COMMIT}"
WORKDIR /src/gf
RUN mkdir -p /out \
 && ( test -f go.mod || go mod init github.com/tomnomnom/gf ) \
 && GOTOOLCHAIN=local CGO_ENABLED=0 GOOS="${TARGETOS}" GOARCH="${TARGETARCH}" \
      go build -mod=readonly -trimpath -buildvcs=false \
      -ldflags "-s -w" \
      -o /out/gf .
RUN git init /src/qsreplace \
 && git -C /src/qsreplace remote add origin https://github.com/tomnomnom/qsreplace.git \
 && git -C /src/qsreplace fetch --depth 1 origin "${QSREPLACE_COMMIT}" \
 && git -C /src/qsreplace checkout --detach "${QSREPLACE_COMMIT}" \
 && test "$(git -C /src/qsreplace rev-parse HEAD)" = "${QSREPLACE_COMMIT}"
WORKDIR /src/qsreplace
RUN mkdir -p /out \
 && GOTOOLCHAIN=local CGO_ENABLED=0 GOOS="${TARGETOS}" GOARCH="${TARGETARCH}" \
      go build -mod=readonly -trimpath -buildvcs=false \
      -ldflags "-s -w" \
      -o /out/qsreplace .
RUN git init /src/gf-patterns \
 && git -C /src/gf-patterns remote add origin https://github.com/1ndianl33t/Gf-Patterns.git \
 && git -C /src/gf-patterns fetch --depth 1 origin "${GF_PATTERNS_COMMIT}" \
 && git -C /src/gf-patterns checkout --detach "${GF_PATTERNS_COMMIT}" \
 && test "$(git -C /src/gf-patterns rev-parse HEAD)" = "${GF_PATTERNS_COMMIT}" \
 && mkdir -p /out/gf-patterns \
 && cp /src/gf/examples/*.json /out/gf-patterns/ \
 && cp /src/gf-patterns/*.json /out/gf-patterns/
RUN git init /src/assetfinder \
 && git -C /src/assetfinder remote add origin https://github.com/tomnomnom/assetfinder.git \
 && git -C /src/assetfinder fetch --depth 1 origin "${ASSETFINDER_COMMIT}" \
 && git -C /src/assetfinder checkout --detach "${ASSETFINDER_COMMIT}" \
 && test "$(git -C /src/assetfinder rev-parse HEAD)" = "${ASSETFINDER_COMMIT}"
WORKDIR /src/assetfinder
RUN mkdir -p /out \
 && go mod init github.com/tomnomnom/assetfinder 2>/dev/null || true \
 && GOTOOLCHAIN=local CGO_ENABLED=0 GOOS="${TARGETOS}" GOARCH="${TARGETARCH}" \
      go build -mod=readonly -trimpath -buildvcs=false \
      -ldflags "-s -w" \
      -o /out/assetfinder .
RUN git init /src/httprobe \
 && git -C /src/httprobe remote add origin https://github.com/tomnomnom/httprobe.git \
 && git -C /src/httprobe fetch --depth 1 origin "${HTTPROBE_COMMIT}" \
 && git -C /src/httprobe checkout --detach "${HTTPROBE_COMMIT}" \
 && test "$(git -C /src/httprobe rev-parse HEAD)" = "${HTTPROBE_COMMIT}"
WORKDIR /src/httprobe
RUN mkdir -p /out \
 && GOTOOLCHAIN=local CGO_ENABLED=0 GOOS="${TARGETOS}" GOARCH="${TARGETARCH}" \
      go build -mod=readonly -trimpath -buildvcs=false \
      -ldflags "-s -w" \
      -o /out/httprobe .
RUN git init /src/chisel \
 && git -C /src/chisel remote add origin https://github.com/jpillora/chisel.git \
 && git -C /src/chisel fetch --depth 1 origin "${CHISEL_COMMIT}" \
 && git -C /src/chisel checkout --detach "${CHISEL_COMMIT}" \
 && test "$(git -C /src/chisel rev-parse HEAD)" = "${CHISEL_COMMIT}"
WORKDIR /src/chisel
RUN --mount=type=cache,target=/go/pkg/mod --mount=type=cache,target=/root/.cache/go-build GOTOOLCHAIN=local go mod edit -json >/dev/null \
 && if GOTOOLCHAIN=local go list -m golang.org/x/crypto >/dev/null 2>&1; then GOTOOLCHAIN=local go get golang.org/x/crypto@v0.56.0; fi \
 && if GOTOOLCHAIN=local go list -m golang.org/x/net >/dev/null 2>&1; then GOTOOLCHAIN=local go get golang.org/x/net@v0.58.0; fi \
 && GOTOOLCHAIN=local go mod tidy
RUN mkdir -p /out/pivoting \
 && GOTOOLCHAIN=local CGO_ENABLED=0 GOOS="${TARGETOS}" GOARCH="${TARGETARCH}" \
      go build -mod=readonly -trimpath -buildvcs=false \
      -ldflags "-s -w -X main.version=${CHISEL_VERSION}" \
      -o /out/chisel . \
 && GOTOOLCHAIN=local CGO_ENABLED=0 GOOS=linux GOARCH=amd64 \
      go build -mod=readonly -trimpath -buildvcs=false \
      -ldflags "-s -w -X main.version=${CHISEL_VERSION}" \
      -o /out/pivoting/chisel_linux_amd64 . \
 && GOTOOLCHAIN=local CGO_ENABLED=0 GOOS=linux GOARCH=arm64 \
      go build -mod=readonly -trimpath -buildvcs=false \
      -ldflags "-s -w -X main.version=${CHISEL_VERSION}" \
      -o /out/pivoting/chisel_linux_arm64 . \
 && GOTOOLCHAIN=local CGO_ENABLED=0 GOOS=windows GOARCH=amd64 \
      go build -mod=readonly -trimpath -buildvcs=false \
      -ldflags "-s -w -X main.version=${CHISEL_VERSION}" \
      -o /out/pivoting/chisel_windows_amd64.exe .
RUN git init /src/ligolo \
 && git -C /src/ligolo remote add origin https://github.com/nicocha30/ligolo-ng.git \
 && git -C /src/ligolo fetch --depth 1 origin "${LIGOLO_COMMIT}" \
 && git -C /src/ligolo checkout --detach "${LIGOLO_COMMIT}" \
 && test "$(git -C /src/ligolo rev-parse HEAD)" = "${LIGOLO_COMMIT}"
WORKDIR /src/ligolo
RUN --mount=type=cache,target=/go/pkg/mod --mount=type=cache,target=/root/.cache/go-build GOTOOLCHAIN=local go mod edit -json >/dev/null \
 && if GOTOOLCHAIN=local go list -m golang.org/x/crypto >/dev/null 2>&1; then GOTOOLCHAIN=local go get golang.org/x/crypto@v0.56.0; fi \
 && if GOTOOLCHAIN=local go list -m golang.org/x/net >/dev/null 2>&1; then GOTOOLCHAIN=local go get golang.org/x/net@v0.58.0; fi \
 && GOTOOLCHAIN=local go mod tidy
RUN mkdir -p /out/pivoting \
 && GOTOOLCHAIN=local CGO_ENABLED=0 GOOS="${TARGETOS}" GOARCH="${TARGETARCH}" \
      go build -mod=readonly -trimpath -buildvcs=false \
      -ldflags "-s -w -X main.version=${LIGOLO_VERSION}" \
      -o /out/ligolo-proxy ./cmd/proxy \
 && GOTOOLCHAIN=local CGO_ENABLED=0 GOOS=linux GOARCH=amd64 \
      go build -mod=readonly -trimpath -buildvcs=false \
      -ldflags "-s -w -X main.version=${LIGOLO_VERSION}" \
      -o /out/pivoting/ligolo_agent_linux_amd64 ./cmd/agent \
 && GOTOOLCHAIN=local CGO_ENABLED=0 GOOS=linux GOARCH=arm64 \
      go build -mod=readonly -trimpath -buildvcs=false \
      -ldflags "-s -w -X main.version=${LIGOLO_VERSION}" \
      -o /out/pivoting/ligolo_agent_linux_arm64 ./cmd/agent \
 && GOTOOLCHAIN=local CGO_ENABLED=0 GOOS=windows GOARCH=amd64 \
      go build -mod=readonly -trimpath -buildvcs=false \
      -ldflags "-s -w -X main.version=${LIGOLO_VERSION}" \
      -o /out/pivoting/ligolo_agent_windows_amd64.exe ./cmd/agent

FROM ${UBUNTU_IMAGE} AS nxc-builder
ARG UBUNTU_SNAPSHOT
ARG NXC_VERSION
ARG NXC_COMMIT
ENV DEBIAN_FRONTEND=noninteractive
# Bootstrap de certificados: sale del archivo vivo porque todavia no hay CA con
# que verificar el snapshot. A partir de la linea siguiente todo se instala
# desde el snapshot, que es el pin real del proyecto; la version que resuelve
# queda registrada en supply-chain/tools.lock.yaml. El paquete no llega a la
# imagen final: el toolkit ya aporta el suyo, tambien desde el snapshot.
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
 && /opt/nxc/bin/pip install --no-cache-dir "PyYAML==6.0.3" \
 && /opt/nxc/bin/python -c 'import nxc.netexec, nxc.nxcdb, cryptography, OpenSSL, yaml' \
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
# gopacket/pcap. En runtime el pcap ya lo aporta el toolkit (libpcap0.8t64).

FROM --platform=$BUILDPLATFORM ${GO_UPSTREAM} AS go-builder
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
# corregidos en 5.9.0. Se sube igual que hace naabu.
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
# imagen final: el toolkit ya aporta el suyo, tambien desde el snapshot.
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
# wpscan y zsteg van cada uno en su propio GEM_HOME: comparten gemas con
# Metasploit, pero no tocan su bundle bloqueado. Se compilan en este stage
# porque es el unico con make y con el Ruby definitivo; la imagen final solo
# copia el resultado.
COPY scripts/install-full-gems.sh /usr/local/bin/install-full-gems
RUN chmod 0555 /usr/local/bin/install-full-gems \
 && GEMS_OUT_DIR=/out /usr/local/bin/install-full-gems
RUN mkdir -p /out \
 && cp -r /opt/ruby /out/ruby \
 && cp -r /src/msf /out/metasploit-framework \
 && rm -rf /out/metasploit-framework/.git

FROM ${BASE_IMAGE}
# Los ARG de la cabecera no llegan aqui: un ARG declarado antes del primer
# FROM vive fuera de toda etapa y no se puede usar en un RUN posterior.
# La etapa final los re-declara con su valor por defecto, que es la que
# construye si no se pasa --build-arg.
ARG UBUNTU_SNAPSHOT=20261005T000000Z
ARG PAT_COMMIT=3ac27901c711bdf3f5b65a7b1d1820a1f65bd09a
ARG EXPLOITDB_COMMIT=150aef0e7c4757c9dff33016c8352671cdc9b454
ARG SECLISTS_COMMIT=eccfbd405af82194e125a450a0076dbe4252d6f9
# El LABEL lo deja el bloque de full, mas abajo: una sola imagen.
#
COPY scripts/install-toolkit-packages.sh /usr/local/bin/install-toolkit-packages
COPY scripts/pwntools-requirements-aarch64.txt scripts/pwntools-requirements-x86_64.txt /tmp/
RUN chmod 0555 /usr/local/bin/install-toolkit-packages \
 && SNAPSHOT_ID="${UBUNTU_SNAPSHOT}" /usr/local/bin/install-toolkit-packages
COPY --from=fzf-builder /out/fzf /usr/bin/fzf
COPY --from=naabu-builder /out/naabu /usr/bin/naabu
COPY --from=pspy-builder /out/pspy /usr/bin/pspy
COPY --from=upstream-builder /out/subfinder /usr/bin/subfinder
COPY --from=upstream-builder /out/httpx /usr/bin/httpx
COPY --from=upstream-builder /out/katana /usr/bin/katana
COPY --from=upstream-builder /out/nuclei /usr/bin/nuclei
COPY --from=upstream-builder /out/ffuf /usr/bin/ffuf
COPY --from=upstream-builder /out/gobuster /usr/bin/gobuster
COPY --from=upstream-builder /out/dnsx /usr/bin/dnsx
COPY --from=upstream-builder /out/anew /usr/bin/anew
COPY --from=upstream-builder /out/waybackurls /usr/bin/waybackurls
COPY --from=upstream-builder /out/gf /usr/bin/gf
COPY --from=upstream-builder /out/qsreplace /usr/bin/qsreplace
COPY --from=upstream-builder /out/assetfinder /usr/bin/assetfinder
COPY --from=upstream-builder /out/httprobe /usr/bin/httprobe
COPY --from=upstream-builder /out/gf-patterns /usr/local/share/seclab/gf-patterns
COPY --from=upstream-builder /out/chisel /usr/bin/chisel
COPY --from=upstream-builder /out/ligolo-proxy /usr/bin/ligolo-proxy
COPY --from=upstream-builder /out/pivoting /usr/local/share/seclab/payloads/pivoting
COPY security/proxychains/proxychains4.conf /etc/proxychains4.conf
RUN chmod 0555 /usr/bin/chisel /usr/bin/ligolo-proxy /usr/bin/gf /usr/bin/qsreplace /usr/bin/assetfinder /usr/bin/httprobe /usr/local/share/seclab/payloads/pivoting/* \
 && chmod -R 0555 /usr/local/share/seclab/gf-patterns \
 && chmod 0644 /etc/proxychains4.conf
COPY shell/tools.json /usr/local/share/seclab/tools.json
COPY shell/zshrc /usr/local/share/seclab/zshrc
COPY shell/pentest-lab /usr/local/share/seclab/pentest-lab
COPY scripts/install-shell.sh /usr/local/bin/install-shell
RUN usermod --login tester --home /home/tester --move-home --shell /usr/bin/zsh ubuntu \
 && groupmod --new-name tester ubuntu \
 && usermod --groups tester tester \
&& install -d -m 0755 /home/tester \
  && install -d -m 0700 /var/lib/seclab/ssh \
  && install -d -m 0755 /home/tester/.config \
  && install -d -m 0700 /home/tester/.config/subfinder \
  && ln -sfn /usr/local/share/seclab/gf-patterns /home/tester/.gf \
  && ln -sfn /usr/local/share/seclab/gf-patterns /home/tester/.config/gf \
  && ln -sfn /etc/gdb/gdbinit /home/tester/.gdbinit \
  && printf 'sources: []\n' > /home/tester/.config/subfinder/config.yaml \
  && chown -R tester:tester /home/tester
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

COPY scripts/entrypoint/lab-entrypoint.sh /usr/local/bin/lab-entrypoint
COPY scripts/entrypoint/ttyd-as-tester.sh /usr/local/bin/ttyd-as-tester
COPY scripts/entrypoint/ttyd-as-tester-shell.sh /usr/local/bin/ttyd-as-tester-shell
COPY scripts/vpn-manager.sh /usr/local/bin/vpn-manager
COPY scripts/vpn-control.py /usr/local/bin/vpn-control
COPY scripts/pt-vpn-ip.sh /usr/local/bin/pt-vpn-ip
COPY scripts/proxy-control.py /usr/local/bin/pt-forward
COPY scripts/health/lab-healthcheck.sh /usr/local/bin/lab-healthcheck
COPY scripts/pt-scope-validator.py /usr/local/bin/pt-scope-validator
RUN chmod 0555 /usr/local/bin/lab-entrypoint /usr/local/bin/ttyd-as-tester /usr/local/bin/ttyd-as-tester-shell /usr/local/bin/vpn-manager /usr/local/bin/vpn-control /usr/local/bin/pt-vpn-ip /usr/local/bin/pt-forward /usr/local/bin/lab-healthcheck /usr/local/bin/pt-scope-validator

# Workspace de tester. En local esto se monta como volumen con nombre, y un
# volumen nuevo toma como dueño el directorio de la imagen: si /workspace
# aqui fuera de root, el volumen naceria sin permiso de escritura para
# tester y no se podria documentar nada. De ahi el chown, que no es cosmetico.
# En el host cloud esto se sustituye por un bind mount de la carpeta del
# disco, que ya viene con el dueño correcto.
COPY workspace-seed/ /workspace/
RUN chown -R tester:tester /workspace && chmod 0755 /workspace

LABEL org.opencontainers.image.source="https://github.com/hackadvisermx/seclab-sbf" \
      org.opencontainers.image.title="seclab-sbf full" \
      org.opencontainers.image.version="0.1.0-phase7"
COPY scripts/install-full-packages.sh /usr/local/bin/install-full-packages
RUN chmod 0555 /usr/local/bin/install-full-packages \
 && SNAPSHOT_ID="${UBUNTU_SNAPSHOT}" PAT_COMMIT="${PAT_COMMIT}" EXPLOITDB_COMMIT="${EXPLOITDB_COMMIT}" SECLISTS_COMMIT="${SECLISTS_COMMIT}" /usr/local/bin/install-full-packages
COPY --from=msf-builder /out/ruby /opt/ruby
COPY --from=msf-builder /out/metasploit-framework /opt/metasploit-framework
# wpscan y zsteg se compilan en msf-builder (alli estan el Ruby definitivo y
# make) y se copian ya instalados, cada uno con su GEM_HOME.
COPY --from=msf-builder /out/wpscan-gems /opt/wpscan-gems
COPY --from=msf-builder /out/zsteg-gems /opt/zsteg-gems
COPY scripts/wpscan-wrapper.sh /usr/local/bin/wpscan
COPY scripts/zsteg-wrapper.sh /usr/local/bin/zsteg
RUN chmod 0555 /usr/local/bin/wpscan /usr/local/bin/zsteg
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
COPY --from=nxc-builder /out/nxc /opt/nxc
COPY --from=nxc-builder /out/version /usr/local/share/seclab/netexec-version
# NetExec escribe ~/.nxc; mismo motivo que .msf4, symlink al volumen.
RUN ln -sf /opt/nxc/bin/nxc /usr/local/bin/nxc \
  && ln -sf /opt/nxc/bin/netexec /usr/local/bin/netexec \
  && ln -sf /opt/nxc/bin/nxcdb /usr/local/bin/nxcdb \
  && chmod 0555 /usr/local/bin/nxc /usr/local/bin/netexec /usr/local/bin/nxcdb \
  && ln -sfn /var/lib/seclab/tester/.nxc /home/tester/.nxc \
  && chown -h tester:tester /home/tester/.nxc
#
# NO se exponen los ficheros de impacket/examples/ como ejecutables, y el
# motivo esta medido para que no se vuelva a intentar:
#
# impacket 0.14 (la dependencia de NetExec) es la libreria pura, "Network
# protocols Constructors and Dissectors". Ya no distribuye los CLI. Sus ficheros
# en examples/ son modulos: se importan desde el codigo de nxc, como
# `from impacket.examples.secretsdump import ...` en nxc/protocols/smb.py, y
# no tienen bloque `if __name__ == "__main__"`, ni funcion main(), ni
# parse_args(), ni entry point console_scripts.
#
# Se intento chmod +x y sonaba a que funcionaba, pero ejecutar secretsdump no
# imprimia nada y salia con 0: importado y sin main que ejecutar. Ademas no
# llevan shebang, asi que sin tocar upstream los ejecutaba /bin/sh y fallaba
# con "import: not found". Un wrapper propio tampoco sirve: no hay main que
# llamar.
#
# ESTO NO CONTRADICE lo de arriba, porque son scripts distintos. NetExec trae
# sus PROPIOS ejecutables en /opt/nxc/bin/, y esos si son CLIs de verdad: tienen
# su bloque main y su argparse, se ejecutan con el python del venv y responden
# con su usage. Comprobado uno a uno antes de exponerlos, no por el nombre del
# fichero.
#
# Se expone un subconjunto, no los 139 binarios del venv. El criterio es el uso
# diario contra un objetivo de AD desde linea de comandos, y lo que se deja
# dentro sigue accesible por su ruta completa. Los .py llevan ALGO de codigo
# nuestro, asi que el shebang se antepone con `install` en vez de tocar los
# ficheros de upstream.
RUN for tool in netview.py wmiexec.py psexec.py smbexec.py smbclient.py \
               GetUserSPNs.py Get-GPPPassword.py GetADUsers.py GetADComputers.py \
               getPac.py getST.py getTGT.py describeTicket.py findDelegation.py \
               owneredit.py rbcd.py dacledit.py dpapi.py mimikatz.py mssqlclient.py \
               reg.py ticketer.py atexec.py net.py ntfs-read.py dpapidump.py \
               secretsdump.py GetLAPSPassword.py GetUserSPNs.py; do \
      if [ -f "/opt/nxc/bin/${tool}" ]; then \
        install -m 0755 "/opt/nxc/bin/${tool}" "/usr/local/bin/${tool}"; \
      fi; \
    done \
 && ln -sf /opt/nxc/bin/certipy /usr/local/bin/certipy \
 && chmod 0555 /usr/local/bin/certipy \
 && for tool in netview.py psexec.py GetUserSPNs.py dacledit.py dpapi.py; do \
      "/usr/local/bin/${tool}" -h >/dev/null 2>&1 || { \
        printf 'AD tool rota: %s\n' "$tool" >&2; exit 1; }; \
    done \
 && certipy find -h >/dev/null 2>&1 || { printf 'certipy roto\n' >&2; exit 1; } \
 && /usr/bin/pspy -h >/dev/null 2>&1 || { printf 'pspy no arranca\n' >&2; exit 1; } \
 && sed -i "1s|.*|#!/opt/nxc/bin/python3|" /opt/enum4linux-ng.py \
 && install -m 0755 /opt/enum4linux-ng.py /usr/bin/enum4linux-ng \
 && rm -f /opt/enum4linux-ng.py \
 && enum4linux-ng --help >/dev/null 2>&1 || { printf 'enum4linux-ng no arranca\n' >&2; exit 1; } \
 && printf '%s\n' 'AD tools de impacket, certipy, pspy y enum4linux-ng ok'
COPY --from=go-builder /out/s3scanner /usr/bin/s3scanner
ENV PATH="/opt/ruby/bin:/opt/nxc/bin:${PATH}"
WORKDIR /workspace
ENTRYPOINT ["/usr/local/bin/lab-entrypoint"]
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 CMD ["/usr/local/bin/lab-healthcheck"]
CMD ["/bin/bash"]
