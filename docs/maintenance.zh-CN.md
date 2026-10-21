# 构建与维护

[快速开始](../README.zh-CN.md) · [English](maintenance.md)

## 镜像内容

镜像直接打包官方 Linux Development Build Release，不再编译核心。上游发布包附带 glibc 以外的动态库，通过相对 RPATH 加载；基础镜像使用 Ubuntu 24.04，与上游构建和验证环境一致。

| 组件 | 版本 |
| --- | --- |
| 平台与客户端 | `linux/amd64`；原版 WoW 1.12.1，build 5875 |
| 核心 | [`a9fa07aab5e745cae17c5016c9eddffdb75ea7f1`](https://github.com/vmangos/core/tree/a9fa07aab5e745cae17c5016c9eddffdb75ea7f1) |
| 二进制包 | `dev-linux-amd64-a9fa07a.tar.gz` |
| 数据库快照 | `db-4641790.zip` |
| CI 验证数据库 | MariaDB 10.11 |

镜像包含两个服务端、提取工具、默认配置、SQL 迁移，以及 `realmd`、`characters`、`mangos`、`logs` 四库快照。SQL 迁移和许可证取自同一个核心提交，源码归档只提取这些文件。

## 镜像标签

```text
ghcr.io/cherrs/vmangos-container:a9fa07a-5875
ghcr.io/cherrs/vmangos-container:sha-<repository-commit>
```

核心/客户端标签会随本仓库的打包配置更新。`sha-...` 对应本仓库提交，不是上游核心提交。需要固定某次发布的镜像时，使用 Actions 摘要中的 `@sha256:...` 地址。

## 本地构建

```bash
docker build -t vmangos-container:local ./image
bash scripts/smoke-test.sh vmangos-container:local
```

验证脚本会创建并移除临时容器 `vmangos-ci-db`、`vmangos-ci-login` 和网络 `vmangos-ci`，请勿同时运行多份。数据库密码随机生成，并在 Actions 日志中屏蔽。

## GitHub Actions

`main` 分支的 `image/`、`scripts/` 或 `.github/workflows/publish.yml` 更新后会自动构建，纯文档修改不会触发。手动发布时，在 **Actions → Build, verify and publish to GHCR → Run workflow** 中选择 `main`。

PR 和手动运行的其他分支只做验证，不发布镜像；PR 也会跳过 GHCR 登录。工作流使用 `GITHUB_TOKEN`，权限为 `contents: read`、`packages: write`，无需另配长期推送 Token。Actions 版本均固定到提交 SHA。

CI 会下载并校验发布包，使用 Buildx 缓存构建镜像，检查服务端和提取器的动态库依赖，然后在临时 MariaDB 中导入四库、重复运行 bootstrap 验证数据保留行为、检查配置生成，并在只读根文件系统下启动 `realmd`。通过后才将同一份镜像推送到 GHCR。

这些检查不包含地图数据、实际客户端登录或游戏内功能。CI 不会连接正在运行的游戏服务器，也不会创建玩家或 GM 账号。

## 运行说明

| 命令 | 用途 |
| --- | --- |
| `bootstrap` | 初始化新数据库并配置 realm ID 1 |
| `wait` | 等待与核心版本匹配的初始化完成标记 |
| `realmd` | 生成配置并启动登录服，监听 TCP 3724 |
| `mangosd` | 默认命令；生成配置并启动世界服，监听 TCP 8085 |

RA 和 SOAP 默认关闭。使用只读根文件系统时，需要为 `/run/vmangos`、`/var/log/vmangos`、`/tmp` 提供可写挂载，其中运行目录和日志目录应允许 UID 10001 写入。容器可写层中的日志会在容器删除后丢失。

使用已有数据库实例时，将 `DB_HOST`、`DB_PORT` 设为服务容器能够访问的地址，并在各条命令中传入这两个变量。Bootstrap 需要 root 权限创建数据库和用户；它会拒绝覆盖已有表，不能直接接管或升级已有玩家库。初始化成功后，仅修改终端中的 `PUBLIC_ADDRESS` 不会更新数据库中的 realm 地址。

重建数据库容器时继续使用原密码，MariaDB 初始化变量不会重设已有数据卷中的密码。升级前先备份数据库。上游部分表使用 MyISAM，仅使用 `--single-transaction` 不能保证所有表的备份一致。

## 发布包与更新

| 归档文件 | SHA256 |
| --- | --- |
| `dev-linux-amd64-a9fa07a.tar.gz` | `8dc140a926e882d1d4644f3bca0ae370bd0882e175572ab3caacddc493f59511` |
| `db-4641790.zip` | `9e178f1d70363e92a7b8c259000102dc9739333d79ca00c99ea32dd1fb43e904` |

源码归档散列也固定在 [Dockerfile](../image/Dockerfile) 中。上游许可证位于镜像的 `/opt/vmangos/LICENSE`，对应源码可从文首的核心提交获取。

上游会替换 `latest`、`db_latest` release 的附件，旧下载地址以后可能失效。需要保留重建能力时，请自行归档发布包，并保留已记录的散列。

更新核心时，同步修改 `CORE_REV`、`RELEASE_ARCHIVE`、二进制和源码归档散列、工作流中的核心/客户端标签，以及文档版本信息。已有数据库的迁移需要另行安排。回退镜像不会同时回退数据库结构或数据。

参考：[GHCR](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry) · [MariaDB 镜像变量](https://mariadb.com/docs/server/server-management/automated-mariadb-deployment-and-administration/docker-and-mariadb/mariadb-server-docker-official-image-environment-variables) · [VMaNGOS 安装说明](https://vmangos.github.io/wiki/Getting-it-working-Linux/)。
