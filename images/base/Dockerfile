ARG BASE_IMAGE=docker.io/library/ubuntu@sha256:008173c23f95b170204355c12626cb5a965d779a7e1283b09e9cffbb1bf33ca3
FROM ${BASE_IMAGE}
LABEL org.opencontainers.image.source="https://github.com/hackadvisermx/seclab-sbf" \
      org.opencontainers.image.title="seclab-sbf base" \
      org.opencontainers.image.version="0.2.0-phase2"
COPY scripts/entrypoint/base-entrypoint.sh /usr/local/bin/base-entrypoint
COPY scripts/health/base-healthcheck.sh /usr/local/bin/base-healthcheck
RUN chmod 0555 /usr/local/bin/base-entrypoint /usr/local/bin/base-healthcheck
WORKDIR /workspace
ENTRYPOINT ["/usr/local/bin/base-entrypoint"]
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 CMD ["/usr/local/bin/base-healthcheck"]
CMD ["/bin/bash"]
