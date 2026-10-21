FROM ubuntu:24.04
ARG CORE_REV=a9fa07aab5e745cae17c5016c9eddffdb75ea7f1
ARG RELEASE_ARCHIVE=dev-linux-amd64-a9fa07a.tar.gz
ARG RELEASE_SHA256=8dc140a926e882d1d4644f3bca0ae370bd0882e175572ab3caacddc493f59511
ARG SOURCE_SHA256=1c771430f367d231b7e4af9f72387098cd366a068ced879939a83281d0321f0f
LABEL org.opencontainers.image.source="https://github.com/vmangos/core" \
      org.opencontainers.image.revision="${CORE_REV}"
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates curl unzip python3 mariadb-client tzdata \
    && rm -rf /var/lib/apt/lists/*
# Official Linux release bundles its non-glibc shared libraries with relative RPATHs.
# No compiler, CMake or source compilation is used in this image build.
RUN curl --fail --location --retry 3 \
    "https://github.com/vmangos/core/releases/download/latest/${RELEASE_ARCHIVE}" -o /tmp/release.tar.gz \
    && echo "${RELEASE_SHA256}  /tmp/release.tar.gz" | sha256sum -c - \
    && mkdir -p /opt/vmangos \
    && tar -xzf /tmp/release.tar.gz --strip-components=1 -C /opt/vmangos \
    && printf '%s\n' "${CORE_REV}" > /opt/vmangos/REVISION \
    && rm /tmp/release.tar.gz
# SQL migrations and license are not included in the binary release.
# Extract only these from the exact source revision; do not build the source.
RUN curl --fail --location --retry 3 \
    "https://codeload.github.com/vmangos/core/tar.gz/${CORE_REV}" -o /tmp/source.tar.gz \
    && echo "${SOURCE_SHA256}  /tmp/source.tar.gz" | sha256sum -c - \
    && mkdir -p /tmp/core \
    && tar -xzf /tmp/source.tar.gz --strip-components=1 -C /tmp/core \
       "core-${CORE_REV}/sql/migrations" "core-${CORE_REV}/LICENSE" \
    && mv /tmp/core/sql /opt/vmangos/sql \
    && mv /tmp/core/LICENSE /opt/vmangos/LICENSE \
    && rm /tmp/source.tar.gz && rmdir /tmp/core
# db_latest is a MOVING release: preserve this ZIP in your own artifact storage.
# Its hash is checked so a different snapshot cannot silently replace it.
RUN curl --fail --location --retry 3 \
    https://github.com/vmangos/core/releases/download/db_latest/db-4641790.zip -o /tmp/db.zip \
    && echo '9e178f1d70363e92a7b8c259000102dc9739333d79ca00c99ea32dd1fb43e904  /tmp/db.zip' | sha256sum -c - \
    && mkdir -p /opt/vmangos/db && unzip -q /tmp/db.zip -d /opt/vmangos/db \
    && rm /tmp/db.zip
COPY runtime.py /usr/local/bin/vmangos-runtime.py
RUN groupadd -g 10001 vmangos && useradd -u 10001 -g 10001 -M vmangos \
    && mkdir -p /run/vmangos /var/log/vmangos /data \
    && chown 10001:10001 /run/vmangos /var/log/vmangos
ENV TZ=Asia/Shanghai PYTHONUNBUFFERED=1
USER 10001:10001
WORKDIR /run/vmangos
EXPOSE 3724/tcp 8085/tcp
ENTRYPOINT ["python3", "/usr/local/bin/vmangos-runtime.py"]
CMD ["mangosd"]
