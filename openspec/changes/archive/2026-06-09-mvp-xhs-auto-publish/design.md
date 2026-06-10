## Context

本项目为 greenfield 开发，目标是将 social-auto-upload 的 CLI 自动化上传能力升级为企业内部可用的「AI 多平台内容自动发布系统」。当前无既有代码，团队无同类项目经验。

**约束与偏好：**
- 首发平台：小红书（xhs）
- AI 供应商：国内优先（通义文案 + 万相文生图），通过 Adapter 预留切换
- 部署：Docker Compose 单机，测试环境 2C4G 可运行
- MVP 不做完整 Web 后台，API 驱动

**参考来源：**
- 产品文档：`docs/AI多平台内容自动发布系统产品文档.docx`
- 开源参考：https://github.com/dreammis/social-auto-upload

## Goals / Non-Goals

**Goals:**

- 跑通端到端链路：主题 → AI 文案/封面 → 素材入库 → 创建发布任务 → Playwright 发布小红书 → 日志可追溯
- 建立 4 个 Adapter 抽象层，切换平台/AI/存储不改核心业务
- Task 0 spike 验证 Playwright 小红书发布可行性，输出复用决策
- Docker Compose 一键启动 API + MySQL + Redis

**Non-Goals:**

- Vue3 管理后台、Celery 定时、多平台实现、RBAC、审核流、监控大盘
- 绕过验证码/风控、高频批量发布

## Decisions

### D1: 技术栈 — FastAPI + Vue3 延后

| 选项 | 结论 |
|------|------|
| FastAPI + SQLAlchemy + Pydantic | **选用**。异步友好、OpenAPI 自动生成、Python 生态与 Playwright 同语言 |
| Poseidon Java 栈 | 不选用。与产品文档及 social-auto-upload 技术栈不一致 |
| Django | 不选用。MVP 过重 |

前端 MVP 用 Postman/curl 验证；Vue3 后台作为独立 change。

### D2: 自动化引擎 — Playwright（评估 patchright）

| 选项 | 结论 |
|------|------|
| Playwright | **选用**。social-auto-upload 已用，社区成熟 |
| patchright | spike 阶段对比；若反检测更好则替换 |
| Selenium | 不选用。维护成本更高 |

浏览器自动化逻辑**仅**出现在 `PlatformAdapter` 实现中，不散落业务层。

### D3: Adapter 模式 — 工厂 + 环境变量

```python
# 伪代码 — 配置驱动，业务层只依赖抽象接口
class PlatformAdapter(Protocol):
    async def login(self, account_id: int) -> LoginResult: ...
    async def check_cookie_valid(self, account_id: int) -> bool: ...
    async def publish(self, task: PublishContext) -> PublishResult: ...

def get_platform_adapter(platform: str) -> PlatformAdapter:
    registry = {"xhs": XhsPlatformAdapter, "douyin": DouyinPlatformAdapter}
    return registry[platform]()  # MVP 仅注册 xhs
```

环境变量：
- `AI_TEXT_PROVIDER=tongyi`
- `AI_IMAGE_PROVIDER=wanxiang`
- `STORAGE=local`
- `DEFAULT_PLATFORM=xhs`

### D4: Cookie 存储 — AES 加密 + 文件/DB 双轨

- DB 表 `account_cookies` 存加密后的 cookie JSON
- 可选同步到 `{COOKIE_DIR}/{platform}/{account_id}.json` 供 Playwright 脚本读取
- 加密密钥来自 `COOKIE_ENCRYPTION_KEY` 环境变量
- MVP 单用户；权限隔离留后续 RBAC change

### D5: 任务执行 — MVP 同步 Worker，接口预留异步

| 阶段 | 做法 |
|------|------|
| MVP | `POST /publish-tasks/{id}/execute` 触发，`BackgroundTasks` 或独立线程跑 Playwright |
| 后续 | 同一 `PublishService.execute(task_id)` 迁入 Celery task |

状态机：

```
draft → pending → running → success
                    ↓
                  failed → (retry) → pending
```

`publish_time` 字段预留；MVP 忽略定时，仅手动触发。

### D6: AI 接入 — 统一 Adapter + 生成记录落库

**AiTextAdapter** 输入：`topic, platform, style`  
输出：`title, content, tags[], cover_text`

**AiImageAdapter** 输入：`prompt, ratio, style, count`  
输出：`image_urls[]` → 经 StorageAdapter 存本地 → 写入 `materials`

每次调用写入 `ai_generation_records`（provider, prompt, result, cost_tokens/cost_yuan 占位）。

提示词模板放 `app/templates/prompts/`，按平台分文件（`xhs_text.yaml`, `xhs_image.yaml`）。

### D7: 项目目录结构

```
ai-publish/
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── config.py              # pydantic-settings，读 .env
│   │   ├── adapters/
│   │   │   ├── base.py            # Protocol 定义
│   │   │   ├── factory.py         # get_*_adapter()
│   │   │   ├── platform/xhs.py
│   │   │   ├── ai_text/tongyi.py
│   │   │   ├── ai_image/wanxiang.py
│   │   │   └── storage/local.py
│   │   ├── api/
│   │   │   ├── auth.py
│   │   │   ├── platform_accounts.py
│   │   │   ├── materials.py
│   │   │   ├── ai.py
│   │   │   └── publish_tasks.py
│   │   ├── models/                # SQLAlchemy ORM
│   │   ├── schemas/               # Pydantic DTO
│   │   ├── services/              # 业务编排
│   │   ├── workers/upload_worker.py
│   │   └── utils/crypto.py        # Cookie 加解密
│   ├── alembic/                   # 可选；MVP 可用 init SQL
│   ├── requirements.txt
│   └── Dockerfile
├── docker-compose.yml
├── .env.example
├── docs/spike-report.md
└── scripts/init_db.sql
```

### D8: 数据库 — MySQL 8.0，核心表

见 proposal Impact 节。关键索引：
- `platform_accounts(platform, status)`
- `publish_tasks(status, publish_time)`
- `publish_task_logs(task_id, created_at)`

### D9: Spike 决策门（Task 0 Gate）

Spike 完成后在 `docs/spike-report.md` 记录：

1. social-auto-upload 小红书模块是否可直接 import
2. 图文 vs 视频哪个先实现
3. Cookie 有效期与刷新策略
4. Mac 开发 vs Linux 部署差异
5. **决策**：fork 改造 / 仅借鉴逻辑自写 / 换平台

未通过 gate 时，暂停 Task 2+，更新 design 后再继续。

### D10: 鉴权 — JWT 单用户

MVP：`POST /api/auth/login` 返回 JWT，其余接口 `Authorization: Bearer`。  
预置管理员账号由 `ADMIN_USERNAME` / `ADMIN_PASSWORD` 环境变量或 init SQL 种子数据创建。

## Risks / Trade-offs

| 风险 | 缓解 |
|------|------|
| 小红书 DOM 改版 | PlatformAdapter 隔离；日志记录每步选择器；spike 文档化维护点 |
| Playwright 需 GUI/浏览器 | Docker 镜像含 Chromium + 依赖；开发机 headed 模式扫码 |
| Cookie 泄露 | AES 加密、目录权限 600、`.env` 不入库 |
| 平台风控 | MVP 手动触发、单任务串行、账号间加间隔 |
| AI 成本 | `ai_generation_records` 记 cost；限制单次生成 count |
| Spike 失败 | Gate 机制；可降级为仅图文或换抖音 |
| MVP Worker 同步阻塞 API | 接受；后续 Celery 拆分 |

## Migration Plan

1. **开发环境**：本地 Python venv + Docker MySQL/Redis；Playwright headed 扫码
2. **首次部署**：`cp .env.example .env` → 填 API Key → `docker-compose up -d`
3. **数据初始化**：`scripts/init_db.sql` 建表 + 种子用户
4. **回滚**：停止 compose；数据库 volume 保留；无破坏性迁移

## Open Questions

1. Spike 结果：图文笔记 vs 短视频，哪个作为 MVP 首发内容类型？（Task 0 决定）
2. social-auto-upload 授权协议是否允许直接 fork 商用？（需 spike 时确认 LICENSE）
3. 通义 API 具体模型版本（qwen-max / wanx-v1）与计费方式 — 实施时按账号能力选定
4. 生产环境是否必须 Linux 服务器跑 Playwright？（影响 Docker 镜像选型）
