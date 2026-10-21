# vmangos-docker

使用 GitHub Actions 下载官方 Development Build Release，打包为 Docker 镜像，验证后推送到 GitHub Container Registry。**不重新编译 vMaNGOS 源码。**

## 镜像

```text
ghcr.io/cherrs/vmangos-docker:a9fa07a-5875
ghcr.io/cherrs/vmangos-docker:sha-<本仓库的完整提交 SHA>
```

- 平台：`linux/amd64`。
- 客户端：原版 WoW 1.12.1 / build 5875。
- 核心源码：[`vmangos/core@a9fa07aab5e745cae17c5016c9eddffdb75ea7f1`](https://github.com/vmangos/core/tree/a9fa07aab5e745cae17c5016c9eddffdb75ea7f1)。
- 官方二进制：`dev-linux-amd64-a9fa07a.tar.gz`，包含按相对 RPATH 加载的动态库。
- 基础运行环境：Ubuntu 24.04，与官方 Linux Release 的构建/验证环境一致。
- 包含：`mangosd`、`realmd`、地图提取器、默认配置、SQL 迁移与固定官方四库快照。
- 不包含：客户端文件及提取出的 DBC、maps、vmaps、mmaps。

`a9fa07a-5875` 是当前核心/客户端的便捷标签，会随本仓库构建文件更新而重建。需要锁定完全相同的镜像时，使用工作流摘要给出的 `@sha256:...` 引用。`sha-...` 表示本仓库提交，并非上游核心提交。

## 自动构建

`main` 分支的 `image/`、`scripts/` 或工作流文件更新后自动构建。也可以在 **Actions → Build, verify and publish to GHCR → Run workflow** 手动触发。PR 运行构建验证，但不登录 GHCR、不发布镜像；手动运行非 main 分支也不发布。

工作流顺序：

1. 检查 Python/Bash 脚本。
2. 下载固定官方 Release，校验 SHA256 并打包；同一提交的源码归档只提取 SQL 迁移和许可证，不执行编译。镜像层使用 GitHub Actions 缓存。
3. 检查两个服务端二进制与四个提取器的动态库依赖。
4. 启动临时 MariaDB 10.11，导入 realmd、characters、mangos、logs 四库。
5. 重复运行初始化，确认已成功初始化的库不会被重导或覆盖。
6. 验证配置生成，并在只读根文件系统下启动 realmd，检查 TCP 3724。
7. 使用仓库的 `GITHUB_TOKEN` 发布**同一个已验证镜像**，在摘要记录镜像 digest。

无需配置长期 GHCR 推送 Token；工作流声明 `contents: read` 和 `packages: write`。Actions 引用固定在经过核对的提交 SHA。

这些检查不包含完整地图提取、世界服进入游戏或实际客户端登录，不能替代游戏验收。CI 不连接实际游戏服务器，不创建玩家/GM 账号。

## 拉取

首次发布的 GHCR 包默认私有。私有包需要用有 `read:packages` 权限的 GitHub PAT（classic）登录；若账号要求 SSO，还需要为 Token 授权。不要将 Token 提交进仓库：

```bash
printf '%s' "$GHCR_READ_TOKEN" | docker login ghcr.io -u YOUR_GITHUB_USER --password-stdin
docker pull ghcr.io/cherrs/vmangos-docker:a9fa07a-5875
```

包的访问权限在 GitHub 账号 **Packages → vmangos-docker → Package settings** 管理。

## 本地构建和复验

```bash
docker build -t vmangos-local:a9fa07a-5875 ./image
bash scripts/smoke-test.sh vmangos-local:a9fa07a-5875
```

验证脚本会创建并移除名为 `vmangos-ci-db`、`vmangos-ci-login` 的临时容器和 `vmangos-ci` 网络，请不要同时运行多份。MariaDB 使用临时容器存储；CI 随机密码通过环境变量传入并在 Actions 日志中屏蔽。

## 镜像入口

```text
bootstrap  # 只用于全新数据库：导入四库、补齐迁移并配置 realm
wait       # 等待数据库具有匹配核心版本的初始化完成标记
realmd     # 生成配置并启动登录服，TCP 3724
mangosd    # 默认入口，生成配置并启动世界服，TCP 8085
```

| 环境变量 | 含义 |
| --- | --- |
| `DB_HOST` | 数据库主机，默认 `vmangos-db` |
| `DB_PORT` | 数据库端口，默认 `3306` |
| `DB_PASSWORD` | 固定数据库用户 `mangos` 的密码，24–128 位 ASCII 字母、数字或下划线 |
| `DB_ROOT_PASSWORD` | 仅 bootstrap 需要，用于首次创建四库与数据库用户 |
| `PUBLIC_ADDRESS` | bootstrap 需要，客户端可访问的 IPv4 或域名，最长 32 字符 |
| `REALM_NAME` | bootstrap 使用的 realm 名，默认 `VMaNGOS` |

世界服需要只读挂载 `/data`，包含 `5875/dbc/`、`maps/`、`vmaps/`、`mmaps/` 四个有内容的目录。运行用户为 UID/GID 10001，数据需要允许其读取和遍历。只读根文件系统运行时，需要另外提供可写的 `/run/vmangos`、`/var/log/vmangos`、`/tmp`。

世界服控制台需要保留 stdin/TTY。RA、SOAP 默认关闭。bootstrap 检测到已有或部分导入的库会拒绝覆盖；已完成的同版本初始化直接退出，不能用它升级已有玩家库。

## 固定发布包和更新

官方 Linux Release：`dev-linux-amd64-a9fa07a.tar.gz`，SHA256：

```text
8dc140a926e882d1d4644f3bca0ae370bd0882e175572ab3caacddc493f59511
```

镜像使用官方 `db-4641790.zip`，SHA256：

```text
9e178f1d70363e92a7b8c259000102dc9739333d79ca00c99ea32dd1fb43e904
```

官方 `latest` 和 `db_latest` release 都会替换附件，旧下载地址以后可能失效。需要长期复现时，应自行归档二进制包和数据库 ZIP，再更新 Dockerfile 下载地址，保持相同 SHA256。不要静默替换为不同日期的发布包或快照。

更新核心版本时，同步修改 Dockerfile 的 `CORE_REV`、`RELEASE_ARCHIVE`、二进制及源码归档 SHA256、工作流的核心/客户端标签，以及这里的版本说明，并处理已有数据库的迁移。镜像中的上游许可证位于 `/opt/vmangos/LICENSE`；上游源码可从上述固定提交获取。

参考：[GitHub GHCR 文档](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry)、[vMaNGOS Linux 安装说明](https://vmangos.github.io/wiki/Getting-it-working-Linux/)。
