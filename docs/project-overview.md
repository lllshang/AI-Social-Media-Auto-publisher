# AI 多平台内容自动发布系统 — 项目总览

本文档汇总**工程代码结构**、**全部文档索引**、**脚本与配置说明**，便于新人上手或交付客户时快速定位。

> 当前主开发分支：`develop_P0`  
> 核心应用目录：`ai-publish/`  
> 管理后台入口：`/app/`（本地 `http://127.0.0.1:8765/app/`，Docker 直连 API `http://127.0.0.1:8000/app/`，Nginx 反代默认 `http://127.0.0.1:8080/app/`）

---

## 1. 仓库顶层结构

```
AI-Social-Media-Auto-publisher/
├── ai-publish/                 # ★ 主应用（后端 + 前端 + Docker + 脚本）
├── docs/                       # ★ 用户/运维文档（本目录）
├── openspec/                   # 规格驱动开发（SDD）规格与任务
├── vendor/
│   └── social-auto-upload/     # 第三方参考：Playwright 扫码/发布逻辑
├── .gitignore                  # 忽略 __pycache__、.env、.specstory 等
└── docs/project-overview.md    # 本文档
```

---

## 2. `ai-publish/` 应用结构

### 2.1 总览

| 目录/文件 | 说明 |
|-----------|------|
| `backend/` | FastAPI 后端（Python 3.11） |
| `web/` | Vue 3 + Element Plus 管理后台 |
| `web/dist/` | 前端构建产物（部署时挂载或同步到服务器） |
| `scripts/` | 数据库初始化、部署、升级、E2E 脚本 |
| `docker-compose.yml` | 生产编排：mysql、redis、api、worker、nginx |
| `docker/nginx/` | Nginx 反代配置与 HTTPS 自签证书 |
| `.env.example` | 本地开发环境变量模板 |
| `.env.docker.example` | Docker 部署环境变量模板 |
| `start.sh` / `start.ps1` | 本地启动 API |
| `web.sh` | 构建前端 `npm run build` |
| `README.md` | 应用快速入口（链接到 docs） |

### 2.2 后端 `backend/app/` 分层

```
backend/app/
├── main.py                 # FastAPI 入口、路由注册、生命周期（调度器/Redis 消费者）
├── config.py               # 环境变量配置（数据库、Redis、AI Key、存储等）
├── database.py             # SQLAlchemy 引擎与会话
├── dependencies.py         # JWT 鉴权、RBAC 权限依赖
├── models/                 # ORM 实体（User、Role、PublishTask、Material…）
├── schemas/                # Pydantic 请求/响应模型
├── api/                    # HTTP 路由层
│   ├── auth.py             # 登录 /api/auth
│   ├── dashboard.py        # 工作台统计 /api/dashboard
│   ├── platform_accounts.py
│   ├── account_groups.py
│   ├── materials.py        # 素材 + AI 文案/文生图/提示词构建
│   ├── publish_tasks.py    # 发布任务 CRUD、执行、审核
│   ├── ai_models.py        # AI 模型检测与切换
│   ├── logs.py             # AI 生成记录、操作日志
│   ├── system.py           # 运行时信息 /api/system/runtime
│   ├── system_configs.py   # 系统配置 /api/system/configs
│   └── roles.py            # 角色列表 /api/roles
├── services/               # 业务逻辑
│   ├── publish_service.py  # 任务状态机、提交、执行
│   ├── material_service.py # 素材、AI 内容生成
│   ├── platform_account_service.py
│   ├── ai_model_service.py
│   ├── dashboard_service.py
│   ├── system_config_service.py
│   ├── rbac_service.py
│   └── ...
├── adapters/               # 可插拔适配器
│   ├── factory.py          # 平台/AI/存储 工厂
│   ├── platform/           # xhs、douyin、kuaishou 发布适配
│   ├── ai_text/            # 文案生成（通义、OpenAI 兼容等）
│   ├── ai_image/           # 文生图
│   └── storage/            # local、stub、cos/oss/s3 对象存储
├── workers/                # 后台任务
│   ├── redis_queue.py      # Redis 发布任务队列
│   ├── redis_consumer.py   # 独立 worker 进程入口
│   ├── schedule_worker.py  # APScheduler 定时到点发布
│   ├── task_runner.py      # 执行单条发布任务
│   └── upload_worker.py    # 调用平台 Adapter 实际上传
├── templates/prompts/      # 各平台 YAML 提示词模板
└── utils/                  # 迁移、Playwright、权限、加解密等
```

**数据流简述：**

1. 用户在 `web` 发布向导生成文案/封面 → `materials` + `publish_tasks`
2. 提交后任务为 `pending`；手动或定时触发 → Redis 队列 → `worker` 执行
3. `upload_worker` 通过 `vendor/social-auto-upload` 的 Playwright 脚本完成平台发布

### 2.3 前端 `web/src/`

| 路径 | 页面 | 路由 |
|------|------|------|
| `views/DashboardView.vue` | 工作台（失败任务、账号健康、AI 统计） | `/app/` |
| `views/AccountsView.vue` | 平台账号、分组、扫码登录 | `/app/accounts` |
| `views/ModelsView.vue` | AI 模型与 Key 配置 | `/app/models` |
| `views/MaterialsView.vue` | 素材库、AI 批量文生图 | `/app/materials` |
| `views/TasksView.vue` | 发布任务列表与操作 | `/app/tasks` |
| `views/PublishView.vue` | 5 步发布向导 | `/app/publish` |
| `views/LogsView.vue` | 日志中心 | `/app/logs` |
| `views/SettingsView.vue` | 系统设置（RBAC 可见） | `/app/settings` |
| `api/index.js` | 全部后端 API 封装 | — |
| `stores/auth.js` | 登录态、角色权限 | — |
| `constants/platforms.js` | 小红书/抖音/快手常量 | — |

### 2.4 Docker Compose 服务

| 服务 | 端口（默认） | 作用 |
|------|-------------|------|
| `mysql` | 3307→3306 | 业务数据库 |
| `redis` | 6380→6379 | 发布任务队列 |
| `api` | 8000 | FastAPI + 静态管理页 |
| `worker` | — | 消费 Redis 队列执行发布 |
| `nginx` | 8080/8443 | HTTP/HTTPS 反代 API |

### 2.5 第三方 `vendor/social-auto-upload/`

- **用途**：小红书/抖音/快手 Playwright 登录与上传的参考实现
- **集成方式**：后端通过 `SAU_VENDOR_PATH` 动态加载 `uploader/*_uploader/main.py`
- **注意**：Docker 内使用系统 Chromium + `--no-sandbox`（见 `utils/chromium_launch.py`）

---

## 3. 文档索引（按用途分类）

### 3.1 运维与使用（`docs/`）— 日常必读

| 文档 | 路径 | 适用对象 | 内容摘要 |
|------|------|----------|----------|
| **项目总览（本文）** | [project-overview.md](./project-overview.md) | 全员 | 代码结构、文档地图、路线图状态 |
| **部署指南** | [deployment.md](./deployment.md) | 运维、交付 | Mac/Win/Linux 本地部署、Docker、腾讯云、镜像加速、Nginx/Worker、升级流程 |
| **日常使用手册** | [daily-usage.md](./daily-usage.md) | 运营、测试 | 启动停止、AI 配置、发布流程、账号扫码、任务执行 |
| **API 手动测试** | [api-test.md](./api-test.md) | 开发、测试 | curl 示例：登录、账号、素材、任务、执行 |
| **多平台路线图** | [multi-platform-roadmap.md](./multi-platform-roadmap.md) | 产品、开发 | 平台扩展步骤与优先级（历史规划，部分已实现） |
| **Spike 报告** | [spike-report.md](./spike-report.md) | 开发 | 小红书 Playwright 可行性验证与 vendor 复用决策 |

**推荐阅读顺序（新人）：**  
`project-overview.md` → `deployment.md` → `daily-usage.md` → `api-test.md`

### 3.2 应用内 README

| 文档 | 路径 | 说明 |
|------|------|------|
| 应用快速入口 | [ai-publish/README.md](../ai-publish/README.md) | 本地/Docker 一键命令、文档链接、验收状态 |

### 3.3 规格驱动开发（`openspec/`）— 产品与研发

| 类型 | 路径 | 说明 |
|------|------|------|
| **现行主规格** | `openspec/specs/` | 各模块稳定规格：ai-content、material、publish-task、platform-account、platform-upload |
| **进行中 Change** | `openspec/changes/content-flow-41-complete/` | 发布向导完整流程；含 `proposal.md`、`design.md`、`tasks.md`、子规格 |
| **已归档 MVP** | `openspec/changes/archive/2026-06-09-mvp-xhs-auto-publish/` | 首版小红书 MVP 的规格与任务记录 |

**任务进度看板：**

- 已完成 A/B/C：[content-flow-41-complete/tasks.md](../openspec/changes/content-flow-41-complete/tasks.md)
- **下一阶段 E**：[phase-e-product-gap/tasks.md](../openspec/changes/phase-e-product-gap/tasks.md)

| 阶段 | 状态 | 要点 |
|------|------|------|
| A 平台与发布 P0 | ✅ 完成 | 定时发布、抖音/快手、Docker 扫码、视频向导 |
| B 后台补全 P1 | ✅ 完成 | 工作台、账号分组、日志中心、提示词 API |
| C 基础设施 P2 | ✅ 完成 | Redis 队列、RBAC、系统配置、COS/OSS、Nginx |
| **E 产品缺口补齐** | ⏳ 规划中 | 用户管理、审核模块、文生图增强、平台 E2E、运维监控（**不含 D 风控**） |
| D 风控 C 方案 | ⏳ 未开始 | 敏感词、频率限制、本机 Worker、图片审核（**最后做**） |

---

## 4. 脚本说明（`ai-publish/scripts/`）

| 脚本 | 用途 |
|------|------|
| `init_db.sql` | MySQL 全量建表 + 默认角色/admin 种子数据 |
| `sync-to-server.sh` | 本地 rsync 同步代码与 `web/dist` 到服务器 |
| `upgrade.sh` | 服务器上拉代码、`docker compose up` 升级 |
| `deploy-tencent.sh` | 腾讯云一键部署辅助 |
| `deploy.env.example` | 部署目标服务器 SSH/rsync 配置模板 |
| `install-docker-ubuntu.sh` | Ubuntu 安装 Docker |
| `install-playwright-browser.sh` | 服务器安装 Playwright Chromium |
| `import_sau_cookie.py` | 从 vendor 格式导入 Cookie |
| `e2e_publish.py` | 端到端发布冒烟脚本 |

**典型发版流程：**

```bash
cd ai-publish
./web.sh                              # 构建前端
bash scripts/sync-to-server.sh        # 同步到服务器
# 在服务器项目目录：
bash scripts/upgrade.sh
```

---

## 5. 配置与环境变量

| 文件 | 场景 |
|------|------|
| `ai-publish/.env` | 本地开发（SQLite 或自建 MySQL） |
| `ai-publish/.env.docker` | Docker 生产（从 `.env.docker.example` 复制） |
| `ai-publish/scripts/deploy.env` | `sync-to-server.sh` 的服务器地址（勿提交密钥） |

**关键变量（节选）：**

| 变量 | 说明 |
|------|------|
| `DATABASE_URL` | 数据库连接 |
| `REDIS_URL` | Redis；发布任务队列 |
| `TASK_QUEUE_ENABLED` | 是否使用 Redis 队列 |
| `STORAGE` | `local` / `cos` / `oss` / `s3` |
| `OBJECT_STORAGE_*` | 对象存储 endpoint、bucket、密钥 |
| `SCHEDULER_ENABLED` | 定时发布开关（可被系统设置覆盖） |
| `DASHSCOPE_API_KEY` 等 | 各 AI 厂商 Key |

系统设置页（`/app/settings`）中的 `require_content_review`、`scheduler_enabled` 等**优先于**部分环境变量。

---

## 6. API 路由一览

| 前缀 | 模块 |
|------|------|
| `/api/auth` | 登录、当前用户 |
| `/api/dashboard` | 工作台统计 |
| `/api/platform-accounts` | 平台账号、扫码、Cookie |
| `/api/account-groups` | 账号分组 |
| `/api/materials` | 素材上传/列表 |
| `/api/ai/text/generate` | AI 文案 |
| `/api/ai/image/generate` | AI 文生图 |
| `/api/ai/prompt/build` | 提示词预览 |
| `/api/ai/models` | 模型检测与切换 |
| `/api/publish-tasks` | 发布任务全生命周期 |
| `/api/logs` | AI 记录、操作日志 |
| `/api/system/runtime` | 运行环境（Docker/Chromium/队列） |
| `/api/system/configs` | 系统配置 |
| `/api/roles` | 角色权限 |
| `/api/users` | 用户管理（`users:write`，仅管理员） |
| `/api/reviews/pending` | 待审核任务列表（分页） |
| `/api/reviews/history` | 审核历史记录 |
| `/api/auth/change-password` | 当前用户修改密码 |
| `/health` | 健康检查 |
| `/docs` | Swagger UI |

---

## 7. 数据库主要表

| 表名 | 说明 |
|------|------|
| `users` / `roles` | 用户与 RBAC |
| `platform_accounts` / `account_cookies` | 平台账号与加密 Cookie |
| `account_groups` | 账号分组 |
| `materials` | 素材（上传/AI 生成） |
| `ai_generation_records` | AI 调用日志（Token/张数记在 cost） |
| `publish_tasks` / `publish_task_logs` | 发布任务与执行日志 |
| `system_configs` | 可后台修改的系统开关 |
| `operation_logs` | 管理操作审计 |

DDL 见：`ai-publish/scripts/init_db.sql`；SQLite 增量迁移见 `backend/app/utils/migrations.py`。

---

## 8. 默认账号与权限

首次启动会自动创建三个登录账号（密码经 bcrypt 加密，**修改后无法在系统中查看**）：

| 角色 | 登录账号 | 默认初始密码 | 环境变量 |
|------|----------|--------------|----------|
| admin（管理员） | `admin` | `admin123` | `ADMIN_USERNAME` / `ADMIN_PASSWORD` |
| operator（运营人员） | `operator` | `operator123` | `OPERATOR_USERNAME` / `OPERATOR_PASSWORD` |
| reviewer（审核主管） | `reviewer` | `reviewer123` | `REVIEWER_USERNAME` / `REVIEWER_PASSWORD` |
| viewer（只读用户） | `viewer` | `viewer123` | `VIEWER_USERNAME` / `VIEWER_PASSWORD` |

> 环境变量仅在**首次创建对应账号**时写入密码；生产环境务必修改并妥善保管。

| 角色 | 权限说明 |
|------|----------|
| **admin（管理员）** | 全部权限 |
| **operator（运营人员）** | 查看工作台；查看/管理平台账号；查看/管理素材库；查看/管理/执行发布任务；使用发布向导；**内容审核**；查看/配置 AI 模型；查看日志中心 |
| **reviewer（审核主管）** | 查看工作台、平台账号、素材库、发布任务；**内容审核**（通过/驳回，不可发布与执行） |
| **viewer（只读用户）** | 查看工作台、平台账号、素材库、发布任务、AI 模型、日志中心（不可修改与执行） |

- 菜单与部分 API 按权限控制；修改角色后需重新登录生效
- 系统设置 → **角色列表** 可查看各角色中文权限说明；账号与密码在 **用户管理** 中维护
- 系统设置 → **用户管理**（仅 admin）：新建/禁用用户、分配角色、重置密码
- 顶栏 **修改密码**：所有登录用户可修改本人密码
- 平台账号页支持编辑账号名与备注（`PUT /api/platform-accounts/{id}`）

---

## 9. 相关链接速查

| 需求 | 去看 |
|------|------|
| 怎么部署上服务器？ | [deployment.md](./deployment.md) |
| 怎么发布一条内容？ | [daily-usage.md](./daily-usage.md) |
| 接口怎么调？ | [api-test.md](./api-test.md) 或 `/docs` |
| 代码在哪？ | 本文 §2 + `ai-publish/backend/app` |
| 还有哪些功能没做？ | [phase-e-product-gap/tasks.md](../openspec/changes/phase-e-product-gap/tasks.md)（阶段 E）；阶段 D 风控见 [tasks.md](../openspec/changes/content-flow-41-complete/tasks.md) |
| 为什么用 vendor？ | [spike-report.md](./spike-report.md) |

---

*文档随项目迭代更新；若与代码不一致，以仓库最新代码与 `tasks.md` 为准。*
