#!/usr/bin/env bash
set -euo pipefail

image=${1:?Usage: smoke-test.sh IMAGE}
network=vmangos-ci
database=vmangos-ci-db
login=vmangos-ci-login
export DB_ROOT_PASSWORD DB_PASSWORD DB_HOST PUBLIC_ADDRESS REALM_NAME
DB_ROOT_PASSWORD=$(openssl rand -hex 32)
DB_PASSWORD=$(openssl rand -hex 32)
DB_HOST=$database
PUBLIC_ADDRESS=127.0.0.1
REALM_NAME='VMaNGOS CI'
echo "::add-mask::$DB_ROOT_PASSWORD"
echo "::add-mask::$DB_PASSWORD"

# Invoked indirectly by the EXIT trap, including on the final exit 0.
# shellcheck disable=SC2317
cleanup() {
  status=$?
  if [ "$status" -ne 0 ]; then
    docker logs "$database" 2>&1 || true
    docker logs "$login" 2>&1 || true
  fi
  docker rm -f "$login" "$database" >/dev/null 2>&1 || true
  docker network rm "$network" >/dev/null 2>&1 || true
  return "$status"
}
trap cleanup EXIT

docker run --rm --entrypoint bash "$image" -euc '
  for binary in /opt/vmangos/bin/mangosd /opt/vmangos/bin/realmd /opt/vmangos/bin/Extractors/{MapExtractor,VMapExtractor,VMapAssembler,MoveMapGenerator}; do
    test -x "$binary"
    output=$(ldd "$binary")
    echo "$output"
    if grep -q "not found" <<< "$output"; then exit 1; fi
  done
'
docker network create "$network" >/dev/null
docker run -d --network "$network" --name "$database" \
  -e MARIADB_ROOT_PASSWORD="$DB_ROOT_PASSWORD" -e MARIADB_ROOT_HOST=% mariadb:10.11 \
  --character-set-server=utf8 --collation-server=utf8_general_ci \
  --sql-mode= --max-allowed-packet=256M --innodb-buffer-pool-size=256M >/dev/null

for attempt in $(seq 1 120); do
  if docker exec "$database" healthcheck.sh --connect --innodb_initialized >/dev/null 2>&1; then break; fi
  if [ "$attempt" -eq 120 ]; then echo 'MariaDB startup timed out' >&2; exit 1; fi
  sleep 2
done

app_env=(-e DB_PASSWORD -e DB_HOST -e PUBLIC_ADDRESS -e REALM_NAME)
bootstrap() {
  docker run --rm --network "$network" "${app_env[@]}" -e DB_ROOT_PASSWORD "$image" bootstrap
}
db_query() {
  docker exec -e MYSQL_PWD="$DB_ROOT_PASSWORD" "$database" \
    mariadb -h 127.0.0.1 -u root -N -B -e "$1"
}

bootstrap
test "$(db_query "SELECT status FROM realmd._k3s_bootstrap WHERE id=1;")" = ready
test "$(db_query "SELECT COUNT(*) FROM mangos.creature_template;")" -gt 0
test "$(db_query "SELECT COUNT(*) FROM characters.migrations;")" -gt 0
test "$(db_query "SELECT COUNT(*) FROM logs.migrations;")" -gt 0
db_query "CREATE TABLE realmd._ci_preserve (value INT); INSERT INTO realmd._ci_preserve VALUES (42);"
bootstrap
test "$(db_query "SELECT value FROM realmd._ci_preserve;")" = 42

# Check config rendering against the actual installed template, without map assets.
docker run --rm "${app_env[@]}" --entrypoint python3 "$image" -c \
  "import runpy; m=runpy.run_path('/usr/local/bin/vmangos-runtime.py'); m['conf']('mangosd')"

# Match the Kubernetes read-only filesystem and writable runtime directories.
docker run -d --network "$network" --name "$login" "${app_env[@]}" \
  --read-only --tmpfs /run/vmangos:uid=10001,gid=10001 \
  --tmpfs /var/log/vmangos:uid=10001,gid=10001 --tmpfs /tmp \
  "$image" realmd >/dev/null
for attempt in $(seq 1 60); do
  if docker exec "$login" python3 -c "import socket; socket.create_connection(('127.0.0.1',3724),timeout=2).close()" 2>/dev/null; then
    echo 'PASS: compiled binaries, four-database bootstrap, repeat-bootstrap preservation, configs and realmd TCP startup'
    exit 0
  fi
  if [ "$(docker inspect -f '{{.State.Running}}' "$login")" != true ]; then
    echo 'realmd stopped before opening port 3724' >&2
    exit 1
  fi
  sleep 2
done
echo 'realmd readiness timed out' >&2
exit 1
