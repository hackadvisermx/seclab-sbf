ARG BASE_IMAGE=docker.io/library/ubuntu@sha256:da6fc2be547864451aa253836dd926da33623312df4a9a243e35dc877c378a78
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
