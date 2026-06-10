## Spike 实测记录（2026-06-09）

- 登录：`sau xiaohongshu login --account test1 --headed` ✅
- 校验：`sau xiaohongshu check --account test1` → valid ✅
- 发布：`sau xiaohongshu upload-note ... --headed` → 账号上可见笔记 ✅
- 已知问题：标签「AI发布」偶发无候选下拉，脚本会跳过该标签继续发布（非阻塞）


- [x] 1.1 克隆 social-auto-upload 到本地，阅读 LICENSE 与小红书相关模块结构
- [x] 1.2 安装 Playwright/Chromium，在 headed 模式跑通小红书扫码登录（需本地 Chrome + 人工扫码）
- [x] 1.3 跑通 1 条内容发布（图文或视频，选较稳定的一种），记录每步耗时与失败点（需有效 Cookie）→ **图文 note 发布成功 2026-06-09**
- [x] 1.4 评估：可直接 import / 仅借鉴逻辑自写 / 需换内容类型或平台 → **借鉴逻辑 + Adapter 封装，MVP 首发图文**
- [x] 1.5 编写 `docs/spike-report.md`（含复用决策、Cookie 有效期、DOM 维护点、Mac vs Linux 差异）
- [x] 1.6 Spike 评审：通过 gate 后标记 Task 2+ 可开始；未通过则更新 design.md 再评审 → **代码级 gate 通过**

## 2. 项目骨架与基础设施

- [x] 2.1 创建 `ai-publish/` 目录结构与 `backend/requirements.txt`（FastAPI、SQLAlchemy、Pydantic、JWT、Loguru、cryptography、playwright 等）
- [x] 2.2 实现 `app/config.py`（pydantic-settings，读取 `.env`）
- [x] 2.3 编写 `.env.example`（DB、Redis、JWT、Cookie 密钥、通义 API Key、存储路径）
- [x] 2.4 编写 `scripts/init_db.sql` 建表（users、roles 占位、platform_accounts、account_cookies、materials、ai_generation_records、publish_tasks、publish_task_logs、system_configs、operation_logs）
- [x] 2.5 编写 `docker-compose.yml`（api、mysql、redis）及 `backend/Dockerfile`
- [x] 2.6 验证 `docker-compose up` 可启动 API + MySQL + Redis（2026-06-09 本地 Mac Docker 验证通过）

## 3. Adapter 抽象层

- [x] 3.1 定义 `adapters/base.py` 中四个 Protocol：`PlatformAdapter`、`AiTextAdapter`、`AiImageAdapter`、`StorageAdapter`
- [x] 3.2 实现 `adapters/factory.py`（按环境变量/平台名返回 Adapter 实例）
- [x] 3.3 实现 `adapters/storage/local.py`（LocalStorageAdapter：save/get/url）
- [x] 3.4 实现 `app/utils/crypto.py`（Cookie AES 加解密）

## 4. 平台账号（platform-account）

- [x] 4.1 实现 SQLAlchemy 模型：`PlatformAccount`、`AccountCookie`
- [x] 4.2 实现 Pydantic schemas 与 `PlatformAccountService`
- [x] 4.3 实现 API：`GET/POST /api/platform-accounts`、`POST /{id}/login`、`POST /{id}/check-cookie`
- [x] 4.4 在 `XhsPlatformAdapter` 中实现 login 流程（Playwright 扫码，超时 120s）
- [x] 4.5 实现 Cookie 加密入库与解密读取
- [x] 4.6 实现 Cookie 有效性检测并更新账号状态（active/expired）
- [x] 4.7 编写 platform-account 相关 API 手动测试用例（Postman/curl 清单）→ `docs/api-test.md`

## 5. 平台发布（platform-upload）

- [x] 5.1 实现 `adapters/platform/xhs.py`（基于 spike 结论：发布图文或视频）
- [x] 5.2 实现发布步骤日志写入（open_page、upload_media、fill_title、fill_content、fill_tags、submit）
- [x] 5.3 封装 Playwright 异常为可读业务错误
- [x] 5.4 实现 `workers/upload_worker.py`（接收 PublishContext，调用 PlatformAdapter.publish）
- [x] 5.5 本地验证：有效 Cookie + 测试素材 → 发布成功并产生日志（sau upload-note 已验证）

## 6. AI 内容（ai-content）

- [x] 6.1 编写提示词模板 `app/templates/prompts/xhs_text.yaml`、`xhs_image.yaml`
- [x] 6.2 实现 `adapters/ai_text/tongyi.py`（TongyiTextAdapter）
- [x] 6.3 实现 `adapters/ai_image/wanxiang.py`（WanxiangImageAdapter）
- [x] 6.4 实现 SQLAlchemy 模型 `AiGenerationRecord` 与 `AiContentService`
- [x] 6.5 实现 API：`POST /api/ai/text/generate`、`POST /api/ai/image/generate`
- [x] 6.6 验证 AI 调用写入 `ai_generation_records`（含 provider、prompt、cost 占位）

## 7. 素材中心（material）

- [x] 7.1 实现 SQLAlchemy 模型 `Material`
- [x] 7.2 实现 `MaterialService`（上传、AI 生成图自动入库、按 ID 查询）
- [x] 7.3 实现 API：`POST /api/materials/upload`、`GET /api/materials/{id}`、`GET /api/materials`
- [x] 7.4 串联：文生图 API 成功后自动创建 `source=ai_generated` 素材记录
- [x] 7.5 验证上传与 AI 入库素材均可被发布任务引用

## 8. 发布任务（publish-task）

- [x] 8.1 实现 SQLAlchemy 模型 `PublishTask`、`PublishTaskLog`
- [x] 8.2 实现 `PublishService`（创建、状态机流转、execute、retry）
- [x] 8.3 实现 API：`POST /api/publish-tasks`、`GET /api/publish-tasks/{id}`、`POST /{id}/execute`、`POST /{id}/retry`、`GET /{id}/logs`
- [x] 8.4 实现 execute 异步执行（BackgroundTasks 或线程），running 态防重复提交
- [x] 8.5 实现任务与素材关联校验（material_ids 存在且类型匹配）
- [x] 8.6 预留 `publish_time` 字段读写（MVP 不自动调度）

## 9. 鉴权与横切关注点

- [x] 9.1 实现 JWT 登录 `POST /api/auth/login` 与 Bearer 鉴权中间件
- [x] 9.2 init SQL 种子管理员用户（或环境变量引导首次创建）
- [x] 9.3 配置 Loguru 结构化日志（请求 ID、任务 ID）
- [x] 9.4 所有 API 除 login 外 MUST 鉴权

## 10. 端到端验收

- [x] 10.1 E2E-1：添加小红书账号 → 扫码登录 → Cookie 保存 → check-cookie 有效
- [x] 10.2 E2E-2：输入主题 → AI 文案 + 封面图 → 素材入库
- [x] 10.3 E2E-3：创建发布任务 → 手动 execute → 小红书发布成功 → 日志完整（sau CLI + ai-publish API task#3 均已验证 2026-06-09）
- [x] 10.4 E2E-4：模拟失败步骤 → 任务 failed → retry → 再次 execute（execute 并发 bug 已修复；失败重试机制可用）
- [x] 10.5 E2E-5：修改 `AI_TEXT_PROVIDER` / `STORAGE` 配置项验证 Adapter 工厂可扩展（stub adapter 已实现）
- [x] 10.6 编写 `README.md` 部署与 API 快速上手说明
- [x] 10.7 对照 proposal 验收标准 8 条逐项勾选（除真实小红书发布与 Docker 外均已满足）
