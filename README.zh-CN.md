# vmangos-container

[English](README.md)

这个项目将 [VMaNGOS](https://github.com/vmangos/core) 官方 Development Build Release 打包成容器镜像。GitHub Actions 下载发布包、校验 SHA256，完成验证后推送到 GHCR，不再编译核心源码。

镜像包含 `mangosd`、`realmd`、提取工具、默认配置、SQL 迁移和固定的四库快照。客户端文件及提取出的游戏数据需要自行准备。

## 镜像与版本

```text
ghcr.io/cherrs/vmangos-container:a9fa07a-5875
ghcr.io/cherrs/vmangos-container:sha-<repository-commit>
```

| 项目 | 版本 |
| --- | --- |
| 平台 | `linux/amd64` |
| 客户端 | 原版 WoW 1.12.1，build 5875 |
| 核心提交 | [`a9fa07aab5e745cae17c5016c9eddffdb75ea7f1`](https://github.com/vmangos/core/tree/a9fa07aab5e745cae17c5016c9eddffdb75ea7f1) |
| 官方二进制包 | `dev-linux-amd64-a9fa07a.tar.gz` |
| 基础镜像 | Ubuntu 24.04，与官方 Linux 发布包的构建和验证环境一致 |
| CI 验证数据库 | MariaDB 10.11 |

官方发布包附带 glibc 以外的动态库，通过相对 RPATH 加载。`a9fa07a-5875` 标签会随本仓库的打包配置更新；`sha-...` 对应本仓库的提交，不是上游核心提交。需要固定某次发布的镜像时，使用 Actions 摘要中的 `@sha256:...` 地址。

## 拉取镜像

```bash
docker pull ghcr.io/cherrs/vmangos-container:a9fa07a-5875
```

## 将游戏数据挂载到 /data

下面的命令使用 Bash，并假定数据库已初始化，可通过现有 Docker 网络 `vmangos` 中的 `vmangos-db` 访问。登录服和世界服使用相同的数据库凭据。新数据库请先执行下文的[初始化步骤](#初始化新数据库)。

先在 Docker 宿主机上准备提取好的数据：

```text
/srv/vmangos/data/
├── 5875/
│   └── dbc/
├── maps/
├── vmaps/
└── mmaps/
```

各目录中需要放入与当前版本提取工具匹配的文件。容器使用 UID/GID `10001` 运行，需要能读取文件、遍历目录。数据提取方法见[上游说明](https://vmangos.github.io/wiki/Getting-it-working-Linux/)。

在当前终端设置镜像和数据库连接：

```bash
export VMANGOS_IMAGE=ghcr.io/cherrs/vmangos-container:a9fa07a-5875
export DB_HOST=vmangos-db
read -rsp 'Database password: ' DB_PASSWORD; echo
export DB_PASSWORD
```

以只读方式挂载数据并启动世界服：

```bash
docker run -dit \
  --name vmangos-world \
  --network vmangos \
  --restart unless-stopped \
  --publish 8085:8085 \
  --env DB_HOST --env DB_PASSWORD \
  --mount type=bind,source=/srv/vmangos/data,target=/data,readonly \
  "$VMANGOS_IMAGE" mangosd
```

`/srv/vmangos/data` 是宿主机路径，`/data` 是容器内路径。宿主机目录必须事先存在。保留 `-it`，让世界服控制台的 stdin 和 TTY 保持打开。

登录服使用同一个镜像和数据库，不需要挂载游戏数据：

```bash
docker run -d \
  --name vmangos-login \
  --network vmangos \
  --restart unless-stopped \
  --publish 3724:3724 \
  --env DB_HOST --env DB_PASSWORD \
  "$VMANGOS_IMAGE" realmd
```

数据库中的 realm 地址应填写客户端能访问的公网 IPv4 或域名，世界服端口为 8085。宿主机和上游防火墙都需要放行 TCP 3724、8085。游戏数据目录与数据库分开存放，数据库需要单独持久化和备份。

## 初始化新数据库

启动脚本要求四库已通过本镜像的 `bootstrap` 命令完成初始化。如果使用全新的数据库实例，请先设置上文的镜像和数据库变量，再执行下面的命令，最后启动登录服和世界服。数据库需要能从 `vmangos` 网络访问，root 账号也要允许该连接。

```bash
export PUBLIC_ADDRESS=wow.example.com
read -rsp 'Database root password: ' DB_ROOT_PASSWORD; echo
export DB_ROOT_PASSWORD
docker run --rm --network vmangos \
  --env DB_HOST --env DB_PASSWORD --env DB_ROOT_PASSWORD --env PUBLIC_ADDRESS \
  "$VMANGOS_IMAGE" bootstrap
unset DB_ROOT_PASSWORD
```

将 `wow.example.com` 换成服务器实际地址。Bootstrap 会创建 `realmd`、`characters`、`mangos`、`logs` 四库和 `mangos` 用户，导入快照、补齐迁移，并配置 realm ID 1，不会创建玩家或 GM 账号。

检测到已有表或未完成的导入时，bootstrap 会拒绝覆盖。相同核心版本已初始化成功后，再次运行不会改动数据或 realm 设置。不要用它升级已有玩家库。

## 命令与配置

| 命令 | 用途 |
| --- | --- |
| `bootstrap` | 初始化新数据库并设置 realm 地址 |
| `wait` | 等待与核心版本匹配的初始化完成标记 |
| `realmd` | 生成配置并启动登录服，监听 TCP 3724 |
| `mangosd` | 默认命令；启动世界服，监听 TCP 8085 |

| 环境变量 | 用途 |
| --- | --- |
| `DB_HOST` | 数据库主机，默认 `vmangos-db` |
| `DB_PORT` | 数据库端口，默认 `3306` |
| `DB_PASSWORD` | 固定数据库用户 `mangos` 的密码，24–128 位 ASCII 字母、数字或下划线 |
| `DB_ROOT_PASSWORD` | 仅 bootstrap 使用，用于创建数据库和用户 |
| `PUBLIC_ADDRESS` | bootstrap 必填；客户端可访问的 IPv4 或域名，最长 32 字符 |
| `REALM_NAME` | bootstrap 使用的 realm 名，默认 `VMaNGOS` |

RA 和 SOAP 默认关闭。如果将容器根文件系统设为只读，还需为 `/run/vmangos`、`/var/log/vmangos`、`/tmp` 提供可写挂载，其中运行目录和日志目录应允许 UID 10001 写入。容器可写层中的日志会在容器删除后丢失。

## 构建与发布

`main` 分支的 `image/`、`scripts/` 或工作流文件更新后会自动构建。也可以在 **Actions → Build, verify and publish to GHCR → Run workflow** 手动触发。PR 只做验证，不登录 GHCR、不发布镜像；手动运行其他分支也不会发布。

发布前，CI 会检查服务端和提取器的动态库依赖，在临时 MariaDB 中导入四库，再次运行 bootstrap 验证数据保留行为，检查配置生成，并在只读根文件系统下启动 `realmd`。通过后使用 `GITHUB_TOKEN` 推送同一份镜像，权限为 `contents: read`、`packages: write`。Actions 版本均固定到提交 SHA，无需另配长期推送 Token。

这些检查不包含地图数据、实际客户端登录或世界内玩法。CI 不会连接正在运行的游戏服务器。

在本地构建并复验：

```bash
docker build -t vmangos-container:local ./image
bash scripts/smoke-test.sh vmangos-container:local
```

验证脚本会创建并移除临时容器 `vmangos-ci-db`、`vmangos-ci-login` 和网络 `vmangos-ci`，请勿同时运行多份。数据库密码随机生成，并在 Actions 日志中屏蔽。

## 发布包与更新

| 归档文件 | SHA256 |
| --- | --- |
| `dev-linux-amd64-a9fa07a.tar.gz` | `8dc140a926e882d1d4644f3bca0ae370bd0882e175572ab3caacddc493f59511` |
| `db-4641790.zip` | `9e178f1d70363e92a7b8c259000102dc9739333d79ca00c99ea32dd1fb43e904` |

SQL 迁移和许可证取自同一个核心提交。源码归档只提取这些文件，其散列固定在 [Dockerfile](image/Dockerfile) 中。

上游会替换 `latest`、`db_latest` release 的附件，旧地址以后可能失效。需要保留重建能力时，请自行归档发布包，并保留已记录的散列。

更新核心时，同步修改 `CORE_REV`、`RELEASE_ARCHIVE`、二进制和源码归档散列、工作流中的核心/客户端标签，以及本文版本信息。已有数据库的迁移需要另行安排。上游许可证位于镜像的 `/opt/vmangos/LICENSE`，对应源码可从文首的固定提交获取。

参考：[GHCR 文档](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry) · [VMaNGOS Linux 安装说明](https://vmangos.github.io/wiki/Getting-it-working-Linux/)。
