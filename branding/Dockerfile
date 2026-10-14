# ClimaTrack platform image: official ThingsBoard CE image with the UI and e-mail
# templates rebranded at build time by patch_brand.py (settings in brand.json).
ARG TB_VERSION=4.3.1.6

FROM thingsboard/tb-node:${TB_VERSION} AS upstream

FROM python:3.12-slim AS brand
WORKDIR /work
COPY --from=upstream /usr/share/thingsboard/bin/thingsboard.jar tb.jar
COPY brand.json patch_brand.py ./
COPY assets ./assets
RUN python3 -I patch_brand.py brand.json assets tb.jar tb-branded.jar && rm tb.jar

FROM thingsboard/tb-node:${TB_VERSION}
COPY --from=brand --chown=thingsboard:thingsboard --chmod=555 /work/tb-branded.jar /usr/share/thingsboard/bin/thingsboard.jar
COPY --chown=thingsboard:thingsboard NOTICE.txt LICENSE-thingsboard-apache-2.0.txt /usr/share/thingsboard/legal/
LABEL org.opencontainers.image.title="ClimaTrack IoT platform" \
      org.opencontainers.image.description="Environmental IoT monitoring, based on ThingsBoard Community Edition (Apache-2.0)"
