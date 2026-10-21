FROM ubuntu:24.04 AS build
ARG CORE_REV=a9fa07aab5e745cae17c5016c9eddffdb75ea7f1
ARG BUILD_JOBS=2
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential cmake git ca-certificates libmysqlclient-dev libssl-dev zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*
RUN git init /src && cd /src && git remote add origin https://github.com/vmangos/core.git \
    && git fetch --depth 1 origin "${CORE_REV}" && git checkout --detach FETCH_HEAD \
    && test "$(git rev-parse HEAD)" = "${CORE_REV}"
RUN cmake -S /src -B /build -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_INSTALL_PREFIX=/opt/vmangos -DSUPPORTED_CLIENT_BUILD=5875 \
    -DBUILD_FOR_HOST_CPU=OFF -DBUILD_EXTRACTORS=ON -DENABLE_CPPTRACE=OFF \
    -DDEBUG_SYMBOLS=OFF -DUSE_PCH=ON \
    && cmake --build /build --parallel "${BUILD_JOBS}" && cmake --install /build \
    && printf '%s\n' "${CORE_REV}" > /opt/vmangos/REVISION \
    && mkdir -p /opt/vmangos/sql \
    && cp -r /src/sql/migrations /opt/vmangos/sql/ \
    && cp /src/LICENSE* /opt/vmangos/

FROM ubuntu:24.04
ARG CORE_REV=a9fa07aab5e745cae17c5016c9eddffdb75ea7f1
LABEL org.opencontainers.image.source="https://github.com/vmangos/core" \
      org.opencontainers.image.revision="${CORE_REV}"
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates curl unzip python3 mariadb-client libmysqlclient21 libssl3t64 zlib1g tzdata \
    && rm -rf /var/lib/apt/lists/*
# db_latest is a MOVING release: preserve this ZIP in your own artifact storage.
# Its hash is checked so a different snapshot cannot silently replace it.
RUN curl --fail --location --retry 3 \
    https://github.com/vmangos/core/releases/download/db_latest/db-4641790.zip -o /tmp/db.zip \
    && echo '9e178f1d70363e92a7b8c259000102dc9739333d79ca00c99ea32dd1fb43e904  /tmp/db.zip' | sha256sum -c - \
    && mkdir -p /opt/vmangos/db && unzip -q /tmp/db.zip -d /opt/vmangos/db \
    && rm /tmp/db.zip
COPY --from=build /opt/vmangos /opt/vmangos
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
