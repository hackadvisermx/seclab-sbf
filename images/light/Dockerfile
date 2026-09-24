ARG BASE_IMAGE=seclab-sbf:base
ARG GO_BUILDER=docker.io/library/golang:1.25.13@sha256:cbff9d1a9041b316010f2da6b701b6c0d597718cb90928c85eb597334a0d23d4
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

FROM ${BASE_IMAGE}
ARG UBUNTU_SNAPSHOT=20260922T000000Z
LABEL org.opencontainers.image.source="https://github.com/hackadvisermx/seclab-sbf" \
      org.opencontainers.image.title="seclab-sbf light" \
      org.opencontainers.image.version="0.3.0-phase3"
COPY scripts/install-light-packages.sh /usr/local/bin/install-light-packages
RUN chmod 0555 /usr/local/bin/install-light-packages \
 && SNAPSHOT_ID="${UBUNTU_SNAPSHOT}" /usr/local/bin/install-light-packages
COPY --from=fzf-builder /out/fzf /usr/bin/fzf
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
