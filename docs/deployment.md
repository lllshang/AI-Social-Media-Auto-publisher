# 部署指南（macOS / Windows / Linux）

本文档说明如何在 **Mac、Windows、Linux 服务器** 上部署「AI 多平台内容自动发布系统」。

相关文档：

- [日常使用手册](./daily-usage.md) — 登录、发布、AI 配置
- [多平台扩展路线图](./multi-platform-roadmap.md) — 抖音等平台后续规划
- [ai-publish/README.md](../ai-publish/README.md) — 项目快速入口

---

## 1. 两种部署模式

| 模式 | 适用场景 | 数据库 | 典型端口 |
|------|----------|--------|----------|
| **A. 本地开发部署** | 个人开发、本机试用、需要小红书扫码发布 | SQLite | `8765` |
| **B. Docker 部署** | 上服务器、团队共用 API、MySQL 生产库 | MySQL + Redis | `8000` |

> **Docker 服务器（推荐）：** API 镜像内置 **apt Chromium**，支持 **管理页无头扫码登录** 与 **无头自动发布**（二维码在网页展示，无需本机 Chrome）。  
> **本地开发：** 可使用本机 Chrome（`PLAYWRIGHT_HEADLESS=false`）弹窗扫码。  
> **混合部署（可选）：** 若服务器 Chromium 不可用，可在 Mac/Windows 本地扫码/发布后同步 Cookie。

---

## 2. 环境要求（三平台通用）

### 2.1 本地开发模式（模式 A）

| 组件 | 版本建议 |
|------|----------|
| Python | 3.11+（3.14 可用，部分依赖需注意） |
| Node.js | 18+（构建 Vue 管理页） |
| Google Chrome | 最新版（小红书扫码/发布） |
| Git | 克隆项目 |

可选：

| 组件 | 用途 |
|------|------|
| Ollama | 本地 AI 文案（自动检测） |
| DashScope Key | 通义文案 + 万相文生图 |

### 2.2 Docker 模式（模式 B）

| 组件 | Mac | Windows | Linux 服务器 |
|------|-----|---------|----------------|
| Docker Engine | Docker Desktop | Docker Desktop + **WSL2** | `docker-ce` + compose 插件 |
| 内存 | ≥ 4GB 可用 | ≥ 4GB 可用 | ≥ 2GB（建议 4GB+） |
| 磁盘 | ≥ 10GB | ≥ 10GB | ≥ 20GB |

---

## 3. 模式 A — 本地开发部署

### 3.1 macOS

```bash
# 1. 进入项目
cd "/path/to/ai多平台内容自动发布系统/ai-publish"

# 2. 配置环境（首次）
cp .env.example .env
# 编辑 .env，本地开发保持 SQLite 相关项即可

# 3. 构建前端（首次或前端有改动）
./web.sh

# 4. 启动 API
./start.sh
```

访问：

| 地址 | 说明 |
|------|------|
| http://127.0.0.1:8765/app/ | Vue 管理后台 |
| http://127.0.0.1:8765/docs | Swagger API |
| http://127.0.0.1:8765/health | 健康检查 |

默认账号：`admin` / `admin123`

**局域网访问（可选）：**

```bash
HOST=0.0.0.0 ./start.sh
# 同网段设备访问：http://<你的Mac局域网IP>:8765/app/
```

**Ollama（可选）：**

```bash
# 安装后确保服务运行
ollama list
# .env 中 OLLAMA_BASE_URL=http://127.0.0.1:11434
```

---

### 3.2 Windows

#### 方式一：PowerShell 脚本（推荐）

```powershell
# 1. 以管理员或普通用户打开 PowerShell，进入项目
cd "D:\path\to\ai多平台内容自动发布系统\ai-publish"

# 2. 若首次运行脚本被拦截，可执行：
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned

# 3. 配置环境
copy .env.example .env

# 4. 构建前端
.\web.sh
# 若无 Git Bash，改用手动：
cd web
npm install
npm run build
cd ..

# 5. 启动
.\start.ps1
```

访问地址与 macOS 相同（`127.0.0.1:8765`）。

#### 方式二：WSL2 + bash（与 Mac 命令一致）

在 WSL Ubuntu 中进入项目目录，执行 `./start.sh`。  
Chrome/Playwright 发布需在 WSLg 或 Windows 侧配置 DISPLAY，**新手建议用方式一（原生 Windows + Chrome）**。

**Windows 注意项：**

- 必须安装 **Google Chrome**（`PLAYWRIGHT_CHANNEL=chrome`）
- 路径含中文时 PowerShell / Python 一般可正常处理；遇问题可将项目放到英文路径
- 防火墙首次启动可能弹窗，需允许 Python 网络访问

---

### 3.3 本地模式 — 前端热更新开发

```bash
# 终端 1：API
./start.sh          # Mac / WSL
# 或 .\start.ps1     # Windows PowerShell

# 终端 2：前端
./web.sh dev        # http://127.0.0.1:5173/app/
```

---

## 4. 模式 B — Docker 部署

Docker 会启动三个服务：

| 服务 | 镜像 | 宿主机端口 |
|------|------|------------|
| mysql | mysql:8.0 | 3307 → 3306 |
| redis | redis:7-alpine | 6380 → 6379 |
| api | 自建 Dockerfile | 8000 → 8000 |

### 4.1 部署前准备（三平台相同）

```bash
cd ai-publish

# 1. 使用 Docker 专用环境文件
cp .env.docker.example .env
# 编辑 .env：修改 SECRET_KEY、ADMIN_PASSWORD、各 AI Key

# 2. 构建 Vue 管理页（必须，否则 /app/ 不可用）
./web.sh
# Windows 无 bash 时在 web 目录 npm install && npm run build

# 3. 确认 vendor 参考项目存在
ls ../vendor/social-auto-upload
```

#### 4.1.1 国内网络：Docker 镜像加速

在国内网络环境下，从 Docker Hub 拉取 `mysql:8.0`、`python:3.11-slim` 等基础镜像时，可能出现 `context deadline exceeded`、`i/o timeout` 等超时错误。可按以下方式处理（任选其一或组合使用）。

**方式一：配置 Docker 镜像加速（推荐，一劳永逸）**

在 Docker Desktop（Mac / Windows）或 Linux 的 `/etc/docker/daemon.json` 中配置 registry mirrors，例如：

```json
{
  "registry-mirrors": [
    "https://docker.m.daocloud.io",
    "https://docker.1panel.live"
  ]
}
```

修改后重启 Docker Engine / Docker Desktop，再执行 `docker compose up -d --build`。

> 镜像源地址可能随服务商调整，以各平台当前文档为准；可配置多个 mirror 作为备选。

**方式二：手动从国内镜像站拉取并 tag（不改 compose）**

本项目 `docker-compose.yml` 使用的官方镜像名如下，可先用 DaoCloud 等镜像站拉取，再 tag 为 compose 期望的名称：

| compose 中名称 | 说明 |
|----------------|------|
| `mysql:8.0` | MySQL 数据库 |
| `redis:7-alpine` | Redis（体积较小，多数环境可直接拉取） |
| `python:3.11-slim` | API 镜像构建基础（`backend/Dockerfile`） |

示例（DaoCloud）：

```bash
# MySQL（compose 依赖）
docker pull docker.m.daocloud.io/library/mysql:8.0
docker tag docker.m.daocloud.io/library/mysql:8.0 mysql:8.0

# Python 基础镜像（API build 依赖）
docker pull docker.m.daocloud.io/library/python:3.11-slim
docker tag docker.m.daocloud.io/library/python:3.11-slim python:3.11-slim

# 可选：Redis
docker pull docker.m.daocloud.io/library/redis:7-alpine
docker tag docker.m.daocloud.io/library/redis:7-alpine redis:7-alpine

# 确认本地已有镜像后再启动
docker images | grep -E 'mysql|python|redis'
cd ai-publish
docker compose up -d --build
```

**方式三：使用 compose 覆盖文件指定镜像前缀（高级）**

若团队统一使用某镜像前缀，可在 `ai-publish/docker-compose.override.yml`（本地文件，勿提交密钥）中覆盖 image，例如：

```yaml
services:
  mysql:
    image: docker.m.daocloud.io/library/mysql:8.0
  redis:
    image: docker.m.daocloud.io/library/redis:7-alpine
```

`api` 服务的 `build` 仍依赖 `python:3.11-slim`，需按方式一或方式二预先拉取并 tag，或在 `backend/Dockerfile` 首行改为带前缀的基础镜像（需自行维护）。

**验证是否就绪**

```bash
docker compose up -d --build
docker compose ps          # mysql、redis 应为 healthy，api 为 running
curl http://127.0.0.1:8000/health
```

若 API 首次启动报 `Can't connect to MySQL server on 'mysql'`，多为 MySQL 仍在初始化；等待数秒后 `docker compose restart api`，或依赖 compose 中 API 的 `restart: unless-stopped` 自动恢复。

### 4.2 macOS — Docker Desktop

```bash
# 安装 Docker Desktop for Mac（Apple Silicon / Intel 均可）
# https://www.docker.com/products/docker-desktop/

cd ai-publish
docker compose up -d --build

# 查看日志
docker compose logs -f api

# 健康检查
curl http://127.0.0.1:8000/health
```

访问：**http://127.0.0.1:8000/app/**（直连 API）或 **http://127.0.0.1:8080/app/**（经 Nginx 反代，默认 `NGINX_HTTP_PORT`）

**访问宿主机 Ollama：** `.env` 中已默认 `OLLAMA_BASE_URL=http://host.docker.internal:11434`（Docker Desktop 支持）。

### 4.2.1 C 阶段服务（Redis 队列 / Worker / Nginx / 对象存储）

`docker compose` 现包含：

| 服务 | 作用 |
|------|------|
| `api` | HTTP API；`TASK_QUEUE_EMBEDDED_CONSUMER=false` 时仅入队 |
| `worker` | 消费 Redis 队列执行发布任务 |
| `nginx` | 80/443 反代 API；HTTPS 需证书 |
| `redis` | 任务队列 |

```bash
# 首次启用 HTTPS 前生成自签证书（开发/内网）
bash docker/nginx/generate-self-signed-cert.sh

docker compose up -d --build
docker compose ps    # 应看到 api、worker、nginx、mysql、redis
docker compose logs -f worker
```

对象存储（腾讯云 COS / 阿里云 OSS）：在 `.env` 设置 `STORAGE=cos` 或 `oss`，并填写 `OBJECT_STORAGE_*`（S3 兼容 endpoint）。公网访问前缀填 `OBJECT_STORAGE_PUBLIC_BASE_URL`。

系统开关（审核、定时发布间隔等）可在管理后台 **系统设置** 页面修改，无需重启。

---

### 4.3 Windows — Docker Desktop + WSL2

1. 安装 [Docker Desktop for Windows](https://www.docker.com/products/docker-desktop/)
2. 设置中启用 **Use WSL 2 based engine**
3. 建议启用 WSL2 集成（Ubuntu）

```powershell
cd D:\path\to\ai-publish

# 构建前端
cd web; npm install; npm run build; cd ..

# 启动
docker compose up -d --build
docker compose logs -f api
```

访问：**http://127.0.0.1:8000/app/**

**Ollama：** 与 Mac 相同，使用 `host.docker.internal`。

**路径注意：** 项目在 WSL 路径（如 `\\wsl$\Ubuntu\home\...`）下时，Docker 卷挂载更稳定；纯 Windows 路径（`D:\...`）在 Docker Desktop 下通常也可用。

---

### 4.4 Linux 服务器（生产推荐）

以 Ubuntu 22.04+ 为例：

```bash
# 安装 Docker
sudo apt update
sudo apt install -y docker.io docker-compose-v2
sudo usermod -aG docker $USER
# 重新登录使 docker 组生效

# 上传/克隆项目到服务器
cd /opt/ai-publish/ai-publish

cp .env.docker.example .env
vim .env   # 修改密码、密钥、AI Key

# 构建前端（在服务器上需 Node，或在 CI/本机 build 后同步 web/dist）
cd web && npm ci && npm run build && cd ..

docker compose up -d --build
docker compose ps
curl http://127.0.0.1:8000/health
```

**对外开放（示例）：**

```bash
# 云安全组放行 TCP 8000（或 80/443 经 Nginx 反代）
# 访问：http://<公网IP>:8000/app/
```

**Linux 访问宿主机 Ollama：**

Docker 内无法使用 `host.docker.internal` 时，在 `.env` 改为：

```bash
OLLAMA_BASE_URL=http://172.17.0.1:11434
# 或宿主机实际局域网 IP，如 http://192.168.1.10:11434
```

**Nginx 反向代理（推荐生产）：**

```nginx
server {
    listen 80;
    server_name publish.example.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_read_timeout 300s;
        client_max_body_size 100m;
    }
}
```

---

### 4.5 腾讯云轻量服务器 — 一键部署（推荐客户交付）

适用于 **腾讯云轻量应用服务器（Lighthouse）** 或任意 Linux 云主机。使用项目自带脚本 `scripts/deploy-tencent.sh`，**IP / 域名变更时只需改 `scripts/deploy.env`**，无需改脚本。

#### 4.5.1 总体流程

```
Mac：构建前端 → rsync 上传代码 → 服务器：装 Docker → 配 deploy.env → 执行脚本 → 浏览器打开管理页
```

服务器上最终目录结构：

```
/opt/ai-publish/
├── ai-publish/          # 应用（含 docker-compose.yml、scripts/）
└── vendor/
    └── social-auto-upload/   # 小红书 Playwright 依赖（必传）
```

#### 4.5.2 部署前检查

| 项 | 要求 |
|----|------|
| 系统 | Ubuntu 22.04 / 24.04 等 |
| 配置 | 建议 ≥2核4G；2G 内存请加 swap（见下文） |
| SSH | Ubuntu 镜像用 **`ubuntu`** 用户，不要用 `root` 直接 SSH |
| 防火墙 | 轻量服务器在 **实例详情 → 防火墙**（不是「主机安全」） |

防火墙需放行：

| 端口 | 用途 |
|------|------|
| **22** | SSH |
| **80** | HTTP（可选，经 Nginx 时使用） |
| **443** | HTTPS（有域名后使用） |
| **8000** | 测试期直接访问 API + 管理页 |

> 部署前用 `nc -zv <公网IP> 80` 若显示 `Connection refused` 属正常（防火墙已通但尚无 Web 服务）；`22` 应 `succeeded`。

#### 4.5.3 第一步：Mac 上构建前端（推荐）

在开发机执行，减少服务器内存占用：

```bash
cd "/path/to/ai多平台内容自动发布系统/ai-publish/web"
npm install
npm run build
```

确认存在目录 `ai-publish/web/dist/`。

#### 4.5.4 第二步：Mac 上传代码到服务器

将 **`ai-publish/`** 与 **`vendor/`** 一并上传（Docker 会挂载 vendor）：

```bash
# 首次：在服务器创建安装目录（/opt 需要 sudo，只需执行一次）
ssh ubuntu@<公网IP>
sudo mkdir -p /opt/ai-publish
sudo chown -R ubuntu:ubuntu /opt/ai-publish
exit

# 或在 deploy.env 改用用户目录，免 sudo：
# INSTALL_DIR=/home/ubuntu/ai-publish
```

```bash
# 创建目录（若上一步已 chown，此处不会报错）
ssh ubuntu@<公网IP> "mkdir -p /opt/ai-publish"

# 上传 ai-publish（排除本地虚拟环境）
rsync -avz --progress \
  --exclude 'backend/.venv' \
  --exclude 'backend/data' \
  --exclude 'web/node_modules' \
  "/path/to/ai多平台内容自动发布系统/ai-publish/" \
  ubuntu@<公网IP>:/opt/ai-publish/ai-publish/

# 上传 vendor（必传）
rsync -avz --progress \
  --exclude '.venv' \
  "/path/to/ai多平台内容自动发布系统/vendor/" \
  ubuntu@<公网IP>:/opt/ai-publish/vendor/
```

无 `rsync` 时，可打包 zip 后通过腾讯云 **Workbench** 上传到 `/opt/ai-publish/` 并解压。

#### 4.5.5 第三步：SSH 登录服务器

```bash
ssh ubuntu@<公网IP>
```

首次连接提示 `Are you sure you want to continue connecting` 时输入 **`yes`**。

#### 4.5.6 第四步：安装 Docker（只需一次）

```bash
# 推荐：使用项目脚本（兼容 Ubuntu 24.04 / 腾讯云）
cd /opt/ai-publish/ai-publish   # 或你的安装路径
bash scripts/install-docker-ubuntu.sh

# 手动方式（Ubuntu 24.04 勿用 docker-compose-plugin，改用 docker-compose-v2）：
# sudo apt update
# sudo apt install -y docker.io docker-compose-v2
# sudo usermod -aG docker ubuntu
# exit 后重新 SSH 登录
```

重新登录并验证：

```bash
ssh ubuntu@<公网IP>
docker --version
docker compose version
```

#### 4.5.7 第五步：可选 — 2G 内存启用 swap

```bash
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
free -h
```

#### 4.5.8 第六步：配置部署参数

```bash
cd /opt/ai-publish/ai-publish

# 复制部署配置（换 IP/域名只改此文件）
cp scripts/deploy.env.example scripts/deploy.env
nano scripts/deploy.env
```

`scripts/deploy.env` 示例：

```bash
PUBLIC_HOST=150.158.23.10      # 公网 IP；有域名时改为 publish.example.com
USE_HTTPS=false                # 有 SSL 证书后改为 true
API_PORT=8000
ADMIN_PASSWORD=你的强密码
USE_CN_MIRROR=true             # 国内服务器建议 true
```

再配置 Docker 运行环境：

```bash
cp .env.docker.example .env
nano .env
```

生产环境至少修改：

| 变量 | 说明 |
|------|------|
| `SECRET_KEY` | 随机长字符串 |
| `ADMIN_PASSWORD` | 与 `deploy.env` 一致 |
| `COOKIE_ENCRYPTION_KEY` | 随机长字符串 |
| `DASHSCOPE_API_KEY` 等 | 可选，也可部署后在管理页配置 |

#### 4.5.9 第七步：执行部署脚本

```bash
cd /opt/ai-publish/ai-publish
bash scripts/deploy-tencent.sh
```

脚本会：

1. 读取 `scripts/deploy.env`
2. 国内网络下预拉取 MySQL / Python / Redis 镜像（见 [4.1.1](#411-国内网络docker-镜像加速)）
3. 若缺少 `web/dist` 且服务器有 Node，则自动构建；否则需在本机构建后上传
4. 执行 `docker compose up -d --build`

首次构建约 **5～15 分钟**。成功后输出：

```
管理后台: http://<PUBLIC_HOST>:8000/app/
健康检查: http://<PUBLIC_HOST>:8000/health
```

#### 4.5.10 第八步：验证

**Mac 上：**

```bash
nc -zv <公网IP> 8000
curl http://<公网IP>:8000/health
```

**浏览器：**

| 地址 | 说明 |
|------|------|
| `http://<公网IP>:8000/app/` | 管理后台 |
| `http://<公网IP>:8000/docs` | API 文档 |

默认账号：`admin` / `.env` 中设置的 `ADMIN_PASSWORD`。

**服务器上：**

```bash
cd /opt/ai-publish/ai-publish
docker compose ps
docker compose logs -f api
```

#### 4.5.11 换 IP 或绑定域名

只需编辑 **`scripts/deploy.env`**：

```bash
# 仅换 IP
PUBLIC_HOST=新公网IP

# 后续有域名 + HTTPS
PUBLIC_HOST=publish.example.com
USE_HTTPS=true
```

保存后重新执行：

```bash
bash scripts/deploy-tencent.sh
```

DNS：将域名 **A 记录** 指向服务器公网 IP；再配置 Nginx + SSL（见 [4.4 Nginx 示例](#44-linux-服务器生产推荐)）。

#### 4.5.12 常用运维（服务器）

```bash
cd /opt/ai-publish/ai-publish

docker compose ps                 # 服务状态
docker compose logs -f api        # API 日志
docker compose restart api        # 重启 API
docker compose down               # 停止（勿加 -v）
bash scripts/upgrade.sh           # 版本升级（推荐）
bash scripts/deploy-tencent.sh    # 首次部署 / 全量
```

**代码更新流程（Mac → 服务器）：**

```bash
# Mac：有前端改动时先构建
cd ai-publish/web && npm run build && cd ../..

# Mac：一键同步（读取 scripts/deploy.env 中的 PUBLIC_HOST / SSH_USER）
cd ai-publish
bash scripts/sync-to-server.sh

# 服务器：升级（保留数据卷，比首次 deploy 快）
ssh ubuntu@<公网IP>
cd /opt/ai-publish/ai-publish
bash scripts/upgrade.sh
```

#### 4.5.15 版本升级（非首次部署）

首次完成 [§4.5](#45-腾讯云轻量服务器--一键部署推荐客户交付) 后，**后续迭代不必重装 Docker、不必重配防火墙**，也 **没有** 管理页「一键在线升级」按钮；由运维/交付侧执行 **同步代码 + 升级脚本** 即可。

| 对比 | 首次 `deploy-tencent.sh` | 日常 `upgrade.sh` |
|------|--------------------------|-------------------|
| 安装 Docker / swap | ✅ | ❌ |
| 预拉取基础镜像 | ✅ | ❌ |
| 重建 API 容器 | ✅ | ✅ |
| MySQL / Redis | 启动 | 保持运行，**不删卷** |
| 客户数据 | 新建 | **保留**（任务、素材、Cookie） |

**Mac 侧（每次发版）：**

```bash
cd ai-publish/web && npm run build && cd ..
bash scripts/sync-to-server.sh
```

**服务器侧：**

```bash
cd /opt/ai-publish/ai-publish
bash scripts/upgrade.sh
```

`upgrade.sh` 等价于 `docker compose up -d --build api`，仅重建 API；**不要**使用 `docker compose down -v`（会删除数据卷）。

**会保留的数据（Docker 卷）：**

| 卷 | 内容 |
|----|------|
| `mysql_data` | 账号、任务、配置 |
| `materials_data` | 上传素材 |
| `cookies_data` | 平台 Cookie |
| `provider_config` | AI 厂商 Key |

**何时仍用 `deploy-tencent.sh`：**

- 首次装机
- 修改了 `deploy.env` 中的端口 / 镜像加速策略
- `docker-compose.yml` 有结构性变更（新增服务等）

**数据库结构变更：** 若某版本附带 SQL 迁移，升级后按该版本说明在 MySQL 中执行；应用启动时会 `create_all`，但不会自动做复杂 ALTER。

**给客户的话术：**

> 系统升级由我们操作，约几分钟；不用换服务器、不用客户重新登录配置；升级期间可能短暂无法访问（通常 1～2 分钟）。

#### 4.5.13 配置文件对照

| 文件 | 作用 | 何时修改 |
|------|------|----------|
| `scripts/deploy.env` | 公网 IP、域名、端口、镜像加速 | 换服务器 / 换域名 |
| `.env` | 密钥、管理员密码、AI Key | 首次部署、改密码 |
| `docker-compose.yml` | 服务定义 | 一般不改 |

#### 4.5.14 当前能力说明

| 功能 | 服务器部署后 |
|------|----------------|
| 管理页登录、素材、任务、AI 配置 | ✅ 可用 |
| 小红书网页扫码（服务器一体） | ✅ 无头 Chromium + 管理页展示二维码 |
| 小红书无头发布 | ✅ 容器内 Playwright 执行（需 Cookie 有效） |
| Chromium 自检 | `bash scripts/install-playwright-browser.sh` |
| 运行时状态 | `GET /api/system/runtime` → `chromium_available`、`qr_login_supported` |

**Docker 扫码/发布验证步骤：**

1. 部署后执行 `bash scripts/install-playwright-browser.sh`（确认 `/usr/bin/chromium` 可用）
2. 打开 `/app/accounts` → 新建小红书账号 → **扫码登录**（应弹出二维码）
3. **检测 Cookie** 显示有效后，创建图文任务并 **执行**
4. 查看 `docker compose logs -f api` 与任务日志抽屉

---

## 5. 混合部署（备选方案）

适用于：**服务器 Chromium 不可用**，或希望在本机 Mac/Windows 完成首次扫码。

| 步骤 | 操作 |
|------|------|
| 1 | 服务器 `docker compose up`，团队通过 `https://publish.example.com/app/` 管理任务 |
| 2 | 在 **有 Chrome 的 Mac/Windows** 上本地 `./start.sh` 扫码，或通过 `import_sau_cookie.py` 导入 Cookie |
| 3 | 将 Cookie 同步到服务器 `cookies_data` 卷，或在管理页重新扫码（推荐服务器一体扫码） |
| 4 | 在管理页创建任务 → **执行** 发布（服务器无头或本机均可） |

---

## 6. 环境变量对照

| 变量 | 本地开发 (.env) | Docker (.env.docker.example) |
|------|-----------------|------------------------------|
| DATABASE_URL | `sqlite:///./data/aipublish.db` | MySQL 连接（compose 内覆盖） |
| STORAGE_LOCAL_PATH | `./data/materials` | `/data/materials` |
| COOKIE_DIR | `./data/cookies` | `/data/cookies` |
| SAU_VENDOR_PATH | 绝对路径到 vendor | `/vendor/social-auto-upload` |
| WEB_DIST_PATH | 留空（自动找 web/dist） | `/web/dist` |
| OLLAMA_BASE_URL | `http://127.0.0.1:11434` | `http://host.docker.internal:11434` |
| PLAYWRIGHT_HEADLESS | `false`（本机弹窗扫码） | `true`（无头，网页展示二维码） |
| PLAYWRIGHT_CHROMIUM_EXECUTABLE | 留空（自动检测） | `/usr/bin/chromium` |

AI Key 也可在管理页 **AI 模型 → 厂商配置** 中填写（加密存于 `backend/data/ai_provider_config.json`）。

---

## 7. 常用运维命令

### 本地模式

```bash
./start.sh              # Mac 启动
.\start.ps1             # Windows 启动
./web.sh                # 构建前端
./web.sh dev            # 前端开发模式
```

### Docker 模式

```bash
docker compose up -d --build    # 启动/重建
docker compose down             # 停止
docker compose down -v          # 停止并删除数据卷（慎用）
docker compose logs -f api      # 查看 API 日志
docker compose restart api      # 重启 API
```

### 数据持久化（Docker 卷）

| 卷名 | 内容 |
|------|------|
| mysql_data | MySQL 数据库 |
| materials_data | 上传素材 |
| cookies_data | 平台 Cookie 文件 |
| provider_config | AI 厂商 Key 配置 |

---

## 8. 端口一览

| 端口 | 模式 | 服务 |
|------|------|------|
| 8765 | 本地 | API + 管理页 |
| 5173 | 本地 dev | Vite 前端热更新 |
| 8000 | Docker | API + 管理页 |
| 3307 | Docker | MySQL（外部访问） |
| 6380 | Docker | Redis（外部访问） |
| 11434 | 可选 | Ollama |

---

## 9. 常见问题

### Q1：`/app/` 打开 404

- 本地：先执行 `./web.sh` 生成 `web/dist`
- Docker：确认 `web/dist` 已构建且 compose 挂载了 `./web/dist:/web/dist`

### Q2：Docker 启动后 API 连不上 MySQL

```bash
docker compose logs mysql
# 等待 healthy 后再看 api 日志
docker compose logs api
```

首次 `docker compose up` 时，MySQL 初始化可能略晚于 API 首次连接；若 API 已退出，执行 `docker compose restart api` 或查看是否已自动重启。

### Q3：Windows 下 Playwright 发布失败

- 确认已安装 Chrome
- `.env` 中 `PLAYWRIGHT_HEADLESS=false`
- 使用 `start.ps1` 而非 Docker 执行 publish execute

### Q4：Mac M 系列 + Ollama 文案慢

- 管理页切换较小模型，或使用远程通义 API

### Q5：Linux 服务器如何备份

```bash
docker compose exec mysql mysqldump -u aipublish -paipublish123 aipublish > backup.sql
# 同时备份 materials_data、cookies_data 卷
```

### Q6：三平台 Docker 都支持吗？

**支持。** 镜像为 Linux 容器；Mac/Windows 通过 Docker Desktop 运行，Linux 服务器原生支持。差异主要在 Ollama 宿主机访问地址和 Playwright 发布需混合部署。

### Q7：拉取镜像超时（国内网络）

参见 **[4.1.1 国内网络：Docker 镜像加速](#411-国内网络docker-镜像加速)**。常见报错：`context deadline exceeded`、`Error response from daemon: Get "https://registry-1.docker.io/..."`。

### Q8：轻量服务器防火墙在哪里？

腾讯云 **轻量应用服务器** → 实例详情 → **防火墙**（不是「主机安全 / 安全组」）。CVM 则在 **安全组** 中配置。详见 [§4.5.2](#452-部署前检查)。

### Q9：部署脚本 / IP 怎么改？

编辑 `ai-publish/scripts/deploy.env` 中的 `PUBLIC_HOST`，再执行 `bash scripts/deploy-tencent.sh`。详见 [§4.5.11](#4511-换-ip-或绑定域名)。

### Q10：发新版本要不要重新部署一遍？

**不用从零再来。** 首次之后：Mac 上 `bash scripts/sync-to-server.sh`，服务器上 `bash scripts/upgrade.sh`。数据在 Docker 卷里会保留。详见 [§4.5.15 版本升级](#4515-版本升级非首次部署)。

### Q11：`mkdir: cannot create directory '/opt/ai-publish': Permission denied`

`/opt` 仅 root 可写。在服务器执行一次：

```bash
sudo mkdir -p /opt/ai-publish
sudo chown -R ubuntu:ubuntu /opt/ai-publish
```

或把 `scripts/deploy.env` 中 `INSTALL_DIR` 改为 `/home/ubuntu/ai-publish`。

### Q12：Ubuntu 24.04 安装 Docker 报 `Unable to locate package docker-compose-plugin`

Ubuntu 24.04 默认源中 Compose 插件包名为 **`docker-compose-v2`**，不是 `docker-compose-plugin`。在服务器执行：

```bash
sudo apt update
sudo apt install -y docker.io docker-compose-v2
sudo usermod -aG docker ubuntu
```

或上传代码后执行 `bash scripts/install-docker-ubuntu.sh`，然后 **重新 SSH 登录**。

---

## 10. 发布限频与风控试运行

生产环境建议在管理页 **系统设置** 开启 `rate_limit_enabled`，试运行期可参考：

| 配置项 | 建议起步值 |
|--------|------------|
| `rate_limit_min_interval_seconds` | `300`（5 分钟） |
| `rate_limit_daily_per_account` | `5`～`10` |
| `rate_limit_max_concurrent` | `1` |
| `sensitive_word_enabled` | `true` |
| `require_content_review` | `true`（有人审时） |

观测指标与是否启用本机 Worker（D.4）的决策流程见 [phase-d-trial-guide.md](./phase-d-trial-guide.md)。

---

## 11. 磁盘监控与素材清理

素材文件默认保存在 API 容器/本机 `storage/materials`（或 `.env` 中 `STORAGE_PATH` 指定目录）。长期运行建议：

### 11.1 磁盘监控

| 环境 | 建议 |
|------|------|
| Docker | `docker system df`；`df -h` 查看挂载卷；轻量云监控告警磁盘 >80% |
| 本机开发 | 定期查看 `ai-publish/data/materials` 目录大小 |

### 11.2 自动清理（管理页配置）

在 **系统设置** 中可配置：

| 配置项 | 说明 |
|--------|------|
| `material_cleanup_enabled` | 开启后每小时清理一次 |
| `material_retention_days` | 超过保留天数且**未被任何发布任务引用**的素材将被物理删除 |

> 已被 `publish_tasks.material_ids` 引用的素材不会被清理，避免误删历史任务依赖。

### 11.3 手动巡检 cron（可选）

若未开启自动清理，可在服务器增加巡检脚本（示例，每日 3:00）：

```bash
# /etc/cron.d/ai-publish-disk
0 3 * * * ubuntu du -sh /opt/ai-publish/data/materials >> /var/log/ai-publish-disk.log 2>&1
```

Docker 部署可将路径改为卷内实际挂载点，并结合云监控告警。

### 11.4 失败任务自动重试

系统设置中 `auto_retry_enabled`、`max_auto_retries`、`retry_delay_minutes` 控制失败后自动重试；达上限后任务保持 `failed`，可在任务列表手动重试。

---

## 12. 正式 HTTPS（Let's Encrypt）

自签证书适用于内网/开发；**公网域名**建议改用 Let's Encrypt。

### 11.1 前置条件

- 域名 A 记录已指向服务器公网 IP
- 安全组/防火墙放行 **80**、**443**
- Nginx 容器已运行（`docker compose up -d nginx`）

### 11.2 使用 Certbot（宿主机申请，挂载到 Nginx）

```bash
# Ubuntu 示例
sudo apt install -y certbot

sudo certbot certonly --standalone -d your.domain.com \
  --pre-hook "docker compose -f /opt/ai-publish/docker-compose.yml stop nginx" \
  --post-hook "docker compose -f /opt/ai-publish/docker-compose.yml start nginx"

# 证书路径（默认）
# /etc/letsencrypt/live/your.domain.com/fullchain.pem
# /etc/letsencrypt/live/your.domain.com/privkey.pem
```

将证书挂载到 `ai-publish/docker/nginx/certs/`（或修改 `nginx.conf` 的 `ssl_certificate` 路径指向 `/etc/letsencrypt/...` 只读挂载）。

### 11.3 更新 deploy.env

```bash
PUBLIC_HOST=your.domain.com
USE_HTTPS=true
NGINX_HTTPS_PORT=443
```

修改 `docker/nginx/nginx.conf` 中 `server_name` 与证书文件名后：

```bash
docker compose up -d --force-recreate nginx api
```

### 11.4 自动续期

```bash
# crontab -e
0 3 1 * * certbot renew --quiet && docker compose -f /opt/ai-publish/docker-compose.yml restart nginx
```

---

## 13. Docker 日志轮转与磁盘告警

### 12.1 日志轮转（json-file driver）

在 `docker-compose.yml` 各服务下可增加（示例）：

```yaml
logging:
  driver: json-file
  options:
    max-size: "50m"
    max-file: "5"
```

适用于 `api`、`worker`、`nginx`，避免容器日志撑满磁盘。

### 12.2 磁盘与队列监控

| 检查项 | 命令/端点 |
|--------|-----------|
| 健康检查 | `GET /health` — 含 `database`、`redis`、`queue_depth` |
| Prometheus | `GET /metrics`（`METRICS_ENABLED=true` 时） |
| 素材目录 | `du -sh /opt/ai-publish/data/materials` 或 Docker 卷 |
| 队列积压 | `/health` 中 `queue_depth` > 10 持续 5 分钟需告警 |

云监控建议：磁盘使用率 > 80% 告警；可选 Grafana + Prometheus 抓取 `/metrics`。

---

## 14. 生产上线检查清单

- [ ] 修改 `SECRET_KEY`、`ADMIN_PASSWORD`、`COOKIE_ENCRYPTION_KEY`
- [ ] 配置 `scripts/deploy.env` 中 `PUBLIC_HOST`（IP 或域名）
- [ ] 轻量服务器防火墙放行 22 / 80 / 443 / 8000
- [ ] 配置 HTTPS（Nginx + 证书）
- [ ] 构建并部署最新 `web/dist`
- [ ] 配置 AI Key（`.env` 或管理页）
- [ ] 验证 `/health` 与 `/app/` 登录
- [ ] 验证小红书账号绑定与发布（或按混合部署过渡）
- [ ] 配置数据库/素材定期备份
- [ ] 云防火墙仅开放必要端口

---

## 15. 快速命令索引

| 目标 | Mac | Windows | Linux / 腾讯云 |
|------|-----|---------|----------------|
| 本地启动 | `./start.sh` | `.\start.ps1` | — |
| Docker 启动 | `docker compose up -d` | 同左 | `bash scripts/deploy-tencent.sh` |
| 版本升级 | — | — | `sync-to-server.sh` + `upgrade.sh` |
| 腾讯云完整流程 | — | — | [§4.5 一键部署](#45-腾讯云轻量服务器--一键部署推荐客户交付) |
| 管理页 | :8765/app/ | :8765/app/ | :8000/app/ 或域名 |
| 构建前端 | `./web.sh` | `cd web; npm run build` | 建议 Mac 构建后 rsync |
