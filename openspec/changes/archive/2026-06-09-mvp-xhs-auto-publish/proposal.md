## Why

运营团队需要在抖音、小红书等平台重复完成内容制作、封面上传、账号登录和定时发布，流程重复且易出错。本项目以 [social-auto-upload](https://github.com/dreammis/social-auto-upload) 的浏览器自动化能力为基础，叠加 AI 文案/文生图与任务管理，形成企业内部可用的「AI 多平台内容自动发布系统」。

团队此前未做过此类项目，**最大技术不确定性在于 Playwright 能否稳定完成小红书发布**。因此本 change 采用「轻量 MVP + 技术 spike 先行」策略：先验证一条完整链路（主题 → AI 内容 → 小红书发布），再扩展多平台、定时任务和 Web 后台。

## What Changes

### 本 change 包含

- **Task 0（Spike，阻塞项）**：克隆并评估 social-auto-upload，在本地跑通「小红书 1 账号 → 扫码登录 → 上传 1 条内容（图文或视频二选一）」，输出复用/重写决策报告
- **项目骨架**：FastAPI + MySQL + Redis + Docker Compose 最小可运行环境
- **4 个 Adapter 接口**（MVP 各 1 个实现，预留切换）：
  - `PlatformAdapter`：平台发布（MVP：`XhsPlatformAdapter`）
  - `AiTextAdapter`：AI 文案（MVP：`TongyiTextAdapter`，国内通义）
  - `AiImageAdapter`：AI 文生图（MVP：`WanxiangImageAdapter`，通义万相）
  - `StorageAdapter`：文件存储（MVP：`LocalStorageAdapter`，后续可换 COS/OSS）
- **核心业务 API**（鉴权可先用简单 JWT/单用户）：
  - 平台账号：添加账号、触发扫码登录、保存/检测 Cookie
  - AI：生成标题/正文/标签；生成封面图/配图
  - 素材：上传/入库、关联草稿
  - 发布任务：创建任务、手动触发执行、查询日志、失败重试
- **最小数据模型**：`users`、`platform_accounts`、`account_cookies`、`materials`、`ai_generation_records`、`publish_tasks`、`publish_task_logs`
- **Upload Worker**：Playwright 执行发布（MVP 可与 API 同进程，后续拆 Celery）

### 本 change 不包含（Non-goals）

- 完整 Vue3 管理后台（MVP 用 API + Postman/简易测试页即可）
- Celery 定时发布与 APScheduler（手动触发，接口预留 `publish_time` 字段）
- 多平台实现（抖音/快手/B 站仅留 Adapter 接口与配置项）
- RBAC 权限体系、内容审核流、数据看板
- 绕过验证码/平台风控、非合规批量注册
- Prometheus/Grafana 监控（仅结构化日志）
- SaaS 多租户、分布式 Worker 集群

### 扩展预留（设计约束，非本 change 交付）

| 扩展点 | MVP 做法 | 后续切换方式 |
|--------|----------|--------------|
| 发布平台 | 仅小红书 | 新增 `PlatformAdapter` 实现 + `PLATFORM=xhs\|douyin` 配置 |
| 文案 AI | 通义 | 新增 `AiTextAdapter` + `AI_TEXT_PROVIDER` 环境变量 |
| 文生图 | 通义万相 | 新增 `AiImageAdapter` + `AI_IMAGE_PROVIDER` 环境变量 |
| 文件存储 | 本地目录 | 新增 `StorageAdapter` + `STORAGE=local\|cos` 配置 |
| 任务调度 | 同步/简易后台线程 | 引入 Celery Worker，业务层接口不变 |
| 前端 | 无 | Vue3 + Element Plus 管理后台（独立 change） |

## Capabilities

### New Capabilities

- `platform-account`：平台账号管理、扫码登录、Cookie 加密存储与有效性检测
- `platform-upload`：多平台发布适配层；MVP 实现小红书图文/视频上传
- `ai-content`：AI 文案生成与文生图；统一 Adapter，支持提示词模板与生成记录
- `material`：素材上传、AI 生成图入库、与发布任务/草稿关联
- `publish-task`：发布任务创建、状态机、执行日志、手动触发与失败重试

### Modified Capabilities

（无。项目为 greenfield，尚无既有 spec。）

## Impact

### 新增代码与目录（预期）

```
ai-publish/                    # 项目根（待定名）
├── backend/
│   ├── app/
│   │   ├── adapters/
│   │   │   ├── platform/      # PlatformAdapter + xhs.py
│   │   │   ├── ai_text/       # AiTextAdapter + tongyi.py
│   │   │   ├── ai_image/      # AiImageAdapter + wanxiang.py
│   │   │   └── storage/       # StorageAdapter + local.py
│   │   ├── api/               # FastAPI 路由
│   │   ├── models/            # SQLAlchemy 模型
│   │   ├── services/          # 业务逻辑
│   │   └── workers/           # Upload Worker
│   └── tests/
├── docker-compose.yml
├── .env.example
└── docs/spike-report.md       # Task 0 输出
```

### 外部依赖

- [social-auto-upload](https://github.com/dreammis/social-auto-upload)（评估复用或借鉴）
- Playwright / patchright + Chromium
- 阿里云通义（文案 + 万相文生图 API）
- MySQL 8.0、Redis 7

### 风险与缓解

| 风险 | 缓解 |
|------|------|
| 小红书后台改版导致脚本失效 | PlatformAdapter 隔离；spike 阶段记录 DOM 选择器与维护成本 |
| Cookie 泄露 | 加密存储、目录权限、禁止公网暴露 |
| 平台风控 | MVP 限频（单账号手动触发）；不做高频批量 |
| AI 内容合规 | 生成结果落库可审；MVP 不自动跳过人工确认 |
| Spike 失败阻塞整体 | Task 0 为 gate；失败则调整方案（如仅图文、或换平台）再更新 design |

## 验收标准（MVP）

1. Spike 报告完成，明确 social-auto-upload 复用范围
2. `docker-compose up` 可启动 API + MySQL + Redis
3. 可通过 API 完成：添加小红书账号 → 扫码登录 → Cookie 保存
4. 可通过 API 完成：输入主题 → 生成标题/正文/标签 + 封面图 → 素材入库
5. 可通过 API 创建发布任务并**手动触发**，Playwright 完成小红书发布
6. 发布过程有逐步日志；失败返回明确错误并可重试
7. AI 调用写入 `ai_generation_records`（含 provider、prompt、成本字段占位）
8. 切换 AI 供应商或存储方式仅需改配置/新增 Adapter，不改核心业务代码

## 建议实施顺序

```
Week 0  proposal + spike 规划（本 change）
Week 1  Task 0: 小红书 upload spike → spike-report.md
Week 2  后端骨架 + platform-account + platform-upload(XHS)
Week 3  ai-content + material + 串联「主题→生成→入库」
Week 4  publish-task + Worker + Docker + 端到端验收
```
