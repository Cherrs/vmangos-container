# vmangos-container

[简体中文](README.zh-CN.md) · [Build and maintenance](docs/maintenance.md)

A Linux amd64 container image for [VMaNGOS](https://github.com/vmangos/core), packaged from the official Development Build Release. It supports original WoW 1.12.1, build 5875. The image includes both servers, extraction tools, and a database snapshot; supply the extracted game data yourself.

## Before you start

Use Docker and Bash on a Linux host. Have your extracted client data ready, and allow incoming TCP 3724 and 8085. The steps below set up a new installation with MariaDB 10.11. Run them in order in the same shell.

## 1. Prepare game data

Create the host directory, then copy the extracted folders into it:

```bash
sudo mkdir -p /srv/vmangos/data
```

```text
/srv/vmangos/data/
├── 5875/dbc/
├── maps/
├── vmaps/
└── mmaps/
```

Each folder must contain the matching extracted files. The container runs as UID/GID `10001` and needs permission to read the files and traverse the directories. Follow the [upstream extraction guide](https://vmangos.github.io/wiki/Getting-it-working-Linux/) if you still need to generate them.

## 2. Set passwords and start the database

Replace `wow.example.com` with the public IPv4 address or DNS name clients will use. The application database password must contain 24–128 ASCII letters, digits, or underscores. Keep both passwords for later use; do not choose new ones when recreating an existing database container.

```bash
export VMANGOS_IMAGE=ghcr.io/cherrs/vmangos-container:a9fa07a-5875
export DB_HOST=vmangos-db
export PUBLIC_ADDRESS=wow.example.com
read -rsp 'Database password (24-128 letters, digits or _): ' DB_PASSWORD; echo
read -rsp 'Database root password: ' DB_ROOT_PASSWORD; echo
export DB_PASSWORD DB_ROOT_PASSWORD

docker pull "$VMANGOS_IMAGE"
docker network create vmangos
docker volume create vmangos-db-data
docker run -d --name vmangos-db --network vmangos \
  --restart unless-stopped \
  --env MARIADB_ROOT_PASSWORD="$DB_ROOT_PASSWORD" \
  --env MARIADB_ROOT_HOST=% \
  --mount type=volume,source=vmangos-db-data,target=/var/lib/mysql \
  mariadb:10.11 \
  --character-set-server=utf8 --collation-server=utf8_general_ci \
  --sql-mode= --max-allowed-packet=256M
```

Database files are stored in the `vmangos-db-data` volume. Port 3306 is available inside the Docker network and is not published to the host.

## 3. Initialize the database

Run bootstrap before starting either server. It waits for MariaDB, creates the four databases and the `mangos` user, imports the snapshot, and sets the realm address.

```bash
docker run --rm --network vmangos \
  --env DB_HOST --env DB_PASSWORD --env DB_ROOT_PASSWORD --env PUBLIC_ADDRESS \
  "$VMANGOS_IMAGE" bootstrap
unset DB_ROOT_PASSWORD
```

Continue after `Bootstrap complete` appears. Bootstrap refuses to overwrite existing or partially imported tables. Repeating a completed bootstrap for the same core revision leaves the data unchanged; it does not upgrade an existing player database or create player accounts.

## 4. Start the servers

```bash
docker run -d --name vmangos-login --network vmangos \
  --restart unless-stopped --publish 3724:3724 \
  --env DB_HOST --env DB_PASSWORD \
  "$VMANGOS_IMAGE" realmd

docker run -dit --name vmangos-world --network vmangos \
  --restart unless-stopped --publish 8085:8085 \
  --env DB_HOST --env DB_PASSWORD \
  --mount type=bind,source=/srv/vmangos/data,target=/data,readonly \
  "$VMANGOS_IMAGE" mangosd
```

The world server reads the host's `/srv/vmangos/data` directory at `/data` inside the container. Keep `-it` so its console has an open stdin and TTY. The login server does not need the game data mount.

## 5. Check the logs

```bash
docker ps --filter name=vmangos-
docker logs --tail 50 vmangos-db
docker logs --tail 50 vmangos-login
docker logs --tail 50 vmangos-world
```

If a server keeps restarting, check its logs for database or game data errors. Use `docker logs -f vmangos-world` to follow new output. Back up the database volume separately from the extracted game data.

## Configuration

| Variable | Purpose |
| --- | --- |
| `DB_HOST` | Database host; default `vmangos-db` |
| `DB_PORT` | Database port; default `3306` |
| `DB_PASSWORD` | Password for `mangos`; 24–128 ASCII letters, digits, or underscores |
| `DB_ROOT_PASSWORD` | Database root password; bootstrap only |
| `PUBLIC_ADDRESS` | Client-facing IPv4 address or DNS name, up to 32 characters; bootstrap only |
| `REALM_NAME` | Realm name; default `VMaNGOS`, set during bootstrap |

For image tags, local builds, CI checks, runtime options, and updates, see [Build and maintenance](docs/maintenance.md).
