# vmangos-container

[English](README.md) · [构建与维护](docs/maintenance.zh-CN.md)

将 [VMaNGOS](https://github.com/vmangos/core) 官方 Development Build Release 打包为 Linux amd64 容器镜像，支持原版 WoW 1.12.1、build 5875。镜像包含登录服、世界服、提取工具和数据库快照，提取后的游戏数据需要自行准备。

## 开始前

准备一台可以使用 Docker 和 Bash 的 Linux 主机、提取好的客户端数据，并放行入站 TCP 3724、8085。下面以 MariaDB 10.11 新安装为例，请在同一个终端中按顺序执行。

## 1. 准备游戏数据

创建宿主机目录，再将提取好的文件夹复制进去：

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

各目录都需要放入对应的提取文件。容器使用 UID/GID `10001` 运行，需要能读取文件、遍历目录。尚未提取数据时，先按[上游说明](https://vmangos.github.io/wiki/Getting-it-working-Linux/)准备。

## 2. 设置密码并启动数据库

将 `wow.example.com` 换成客户端实际访问的公网 IPv4 或域名。应用数据库密码必须是 24–128 位 ASCII 字母、数字或下划线。请保存这两个密码，重建已有数据库容器时继续使用原密码。

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

数据库文件保存在 `vmangos-db-data` 卷中。3306 端口仅供 Docker 网络内部访问，不映射到宿主机。

## 3. 初始化数据库

先完成初始化，再启动登录服和世界服。Bootstrap 会等待 MariaDB 就绪，创建四库和 `mangos` 用户，导入快照并设置 realm 地址。

```bash
docker run --rm --network vmangos \
  --env DB_HOST --env DB_PASSWORD --env DB_ROOT_PASSWORD --env PUBLIC_ADDRESS \
  "$VMANGOS_IMAGE" bootstrap
unset DB_ROOT_PASSWORD
```

看到 `Bootstrap complete` 后继续。Bootstrap 会拒绝覆盖已有表或未完成的导入；相同核心版本已初始化成功后，再次执行不会改动数据。它不用于升级已有玩家库，也不会创建玩家账号。

## 4. 启动服务

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

世界服通过容器内的 `/data` 只读访问宿主机 `/srv/vmangos/data`。保留 `-it`，让控制台的 stdin 和 TTY 保持打开。登录服不需要挂载游戏数据。

## 5. 查看日志

```bash
docker ps --filter name=vmangos-
docker logs --tail 50 vmangos-db
docker logs --tail 50 vmangos-login
docker logs --tail 50 vmangos-world
```

如果服务反复重启，先查看日志中的数据库或游戏数据错误。需要持续查看输出时，使用 `docker logs -f vmangos-world`。数据库卷需要单独备份，不能只保留提取后的游戏数据。

## 配置

| 变量 | 用途 |
| --- | --- |
| `DB_HOST` | 数据库主机，默认 `vmangos-db` |
| `DB_PORT` | 数据库端口，默认 `3306` |
| `DB_PASSWORD` | `mangos` 用户密码，24–128 位 ASCII 字母、数字或下划线 |
| `DB_ROOT_PASSWORD` | 数据库 root 密码，仅初始化时使用 |
| `PUBLIC_ADDRESS` | 客户端访问的 IPv4 或域名，最长 32 字符，仅初始化时使用 |
| `REALM_NAME` | realm 名，默认 `VMaNGOS`，初始化时设置 |

镜像标签、本地构建、CI 检查、运行选项和更新方法见[构建与维护](docs/maintenance.zh-CN.md)。
