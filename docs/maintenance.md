# Build and maintenance

[Quick start](../README.md) · [简体中文](maintenance.zh-CN.md)

## What goes into the image

The image packages the official Linux Development Build Release without recompiling the core. The upstream release bundles non-glibc shared libraries with relative RPATHs. Ubuntu 24.04 matches its build and validation environment.

| Component | Version |
| --- | --- |
| Platform and client | `linux/amd64`; original WoW 1.12.1, build 5875 |
| Core | [`a9fa07aab5e745cae17c5016c9eddffdb75ea7f1`](https://github.com/vmangos/core/tree/a9fa07aab5e745cae17c5016c9eddffdb75ea7f1) |
| Binary archive | `dev-linux-amd64-a9fa07a.tar.gz` |
| Database snapshot | `db-4641790.zip` |
| Database used in CI | MariaDB 10.11 |

The image includes both servers, extraction tools, default configuration, SQL migrations, and a snapshot for `realmd`, `characters`, `mangos`, and `logs`. SQL migrations and the license come from the same core commit. Only those files are extracted from the source archive.

## Image tags

```text
ghcr.io/cherrs/vmangos-container:a9fa07a-5875
ghcr.io/cherrs/vmangos-container:sha-<repository-commit>
```

The core/client tag can change when this repository's packaging changes. The `sha-...` tag refers to this repository's commit, not the upstream core. Use the `@sha256:...` reference in the Actions summary to pin an exact image.

## Build locally

```bash
docker build -t vmangos-container:local ./image
bash scripts/smoke-test.sh vmangos-container:local
```

The check script creates and removes temporary containers `vmangos-ci-db`, `vmangos-ci-login`, and the `vmangos-ci` network. Run one copy at a time. It generates temporary database passwords and masks them in Actions logs.

## GitHub Actions

Changes to `image/`, `scripts/`, or `.github/workflows/publish.yml` on `main` trigger a build. Documentation-only changes do not. To publish manually, use **Actions → Build, verify and publish to GHCR → Run workflow** on `main`.

Pull requests and manual runs on other branches run the checks without publishing. Pull requests also skip GHCR login. The workflow uses `GITHUB_TOKEN` with `contents: read` and `packages: write`; no long-lived push token is needed. Action versions are pinned to commit SHAs.

CI downloads and verifies the release files, builds the image with Buildx caching, and checks the server and extractor library dependencies. It then imports all four databases into temporary MariaDB storage, repeats bootstrap to check data preservation, renders the configuration, and starts `realmd` with a read-only root filesystem. Only that tested image is pushed to GHCR.

These checks do not cover extracted map data, in-game login, or world gameplay. CI does not connect to a live game server or create player or GM accounts.

## Runtime notes

| Command | Purpose |
| --- | --- |
| `bootstrap` | Initialize a fresh database and configure realm ID 1 |
| `wait` | Wait for a completed bootstrap matching the core revision |
| `realmd` | Generate configuration and start the login server on TCP 3724 |
| `mangosd` | Default command; generate configuration and start the world server on TCP 8085 |

RA and SOAP are disabled. To use a read-only root filesystem, provide writable mounts at `/run/vmangos`, `/var/log/vmangos`, and `/tmp`. The runtime and log directories must be writable by UID 10001. Logs in the container's writable layer are lost when the container is removed.

For an existing database server, set `DB_HOST` and `DB_PORT` to an address reachable from the server containers and pass both variables to each command. Bootstrap requires root access to create the databases and user. It refuses to overwrite existing tables; it cannot adopt or upgrade an existing player database. After a successful bootstrap, changing `PUBLIC_ADDRESS` in the shell does not update the realm row in the database.

Keep the same passwords when recreating database containers. MariaDB initialization variables do not reset passwords in an existing data volume. Back up the databases before upgrades. Some upstream tables use MyISAM, so `--single-transaction` alone does not give a consistent backup of all tables.

## Release files and updates

| Archive | SHA256 |
| --- | --- |
| `dev-linux-amd64-a9fa07a.tar.gz` | `8dc140a926e882d1d4644f3bca0ae370bd0882e175572ab3caacddc493f59511` |
| `db-4641790.zip` | `9e178f1d70363e92a7b8c259000102dc9739333d79ca00c99ea32dd1fb43e904` |

The source archive hash is also pinned in the [Dockerfile](../image/Dockerfile). The upstream license is included in the image at `/opt/vmangos/LICENSE`; the source is available at the core commit linked above.

Upstream replaces assets in the `latest` and `db_latest` releases, so older download URLs may disappear. Keep your own copies and their recorded hashes if you need to rebuild those versions later.

When updating the core, update `CORE_REV`, `RELEASE_ARCHIVE`, both binary and source archive hashes, the workflow's core/client tag, and the version information in these documents. Handle migrations for existing databases separately. Rolling back an image does not roll back its database schema or data.

References: [GHCR](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry) · [MariaDB image variables](https://mariadb.com/docs/server/server-management/automated-mariadb-deployment-and-administration/docker-and-mariadb/mariadb-server-docker-official-image-environment-variables) · [VMaNGOS setup](https://vmangos.github.io/wiki/Getting-it-working-Linux/).
