# AI 多平台内容自动发布 — 日常使用手册

适用版本：MVP（小红书 + 抖音 + 快手）  
API 地址：http://127.0.0.1:8765  
管理页：http://127.0.0.1:8765/app/  
Swagger：http://127.0.0.1:8765/docs  

部署（Mac / Windows / Linux / Docker）：见 [deployment.md](./deployment.md)

---

## 1. 启动与停止

**macOS / Linux：**

```bash
cd ai-publish
./start.sh
```

**Windows（PowerShell）：**

```powershell
cd ai-publish
.\start.ps1
```

- 默认账号见下表；停止：终端 `Ctrl+C`

| 角色 | 账号 | 默认密码 |
|------|------|----------|
| 管理员 | `admin` | `admin123` |
| 运营 | `operator` | `operator123` |
| 审核主管 | `reviewer` | `reviewer123` |
| 只读 | `viewer` | `viewer123` |

> 密码经 bcrypt 加密存储，**修改后无法在系统中查看明文**。生产环境请尽快修改默认密码。

---

## 2. AI 模型配置（自动匹配）

系统启动时会**自动检测**本机可用模型，并写入 `backend/data/ai_runtime.json`。

### 检测优先级

| 类型 | 优先级 | 说明 |
|------|--------|------|
| 文案 | 本地 Ollama → 通义 → 混元 → OpenAI → DeepSeek → Moonshot → Stub | 本机已检测到 `qwen3.6:latest` 等 |
| 文生图 | 通义万相 → **混元 HY-Image-V3.0** → OpenAI DALL·E → Stub | 本地 Ollama 暂无文生图模型 |

### 配置 API Key（`.env`）

```bash
# 通义（文案 + 万相文生图）
DASHSCOPE_API_KEY=sk-xxx

# OpenAI 或兼容代理
OPENAI_API_KEY=sk-xxx
OPENAI_BASE_URL=https://api.openai.com/v1

# DeepSeek / Moonshot 可选
DEEPSEEK_API_KEY=
MOONSHOT_API_KEY=

# 腾讯混元（OpenAI 兼容，控制台申请 API Key）
HUNYUAN_API_KEY=

# 本地 Ollama（默认已可用）
OLLAMA_BASE_URL=http://127.0.0.1:11434
```

修改 `.env` 后重启 `./start.sh`，或调用 `POST /api/ai/models/detect` 重新检测。

### 模型 API

```bash
# 登录拿 Token
TOKEN=$(curl -s -X POST http://127.0.0.1:8765/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"admin123"}' | python3 -c "import sys,json;print(json.load(sys.stdin)['access_token'])")

# 查看当前可用模型（含本机 Ollama + 远程 Key）
curl -s http://127.0.0.1:8765/api/ai/models -H "Authorization: Bearer $TOKEN" | python3 -m json.tool

# 手动切换文案模型（例如改用通义）
curl -s -X POST http://127.0.0.1:8765/api/ai/models/select \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"mode":"manual","text_provider":"tongyi","text_model":"qwen-plus"}'

# 恢复自动匹配
curl -s -X POST http://127.0.0.1:8765/api/ai/models/detect \
  -H "Authorization: Bearer $TOKEN"
```

---

## 3. 平台账号与 Cookie

支持 **小红书（xhs）**、**抖音（douyin）**、**快手（kuaishou）**。在 Vue「平台账号」页按平台筛选，新建账号后扫码登录。

**Docker 服务器：** 使用容器内 Chromium 无头打开登录页，二维码显示在管理页弹窗（无需本机 Chrome）。部署后若扫码不可用，执行 `bash scripts/install-playwright-browser.sh`。

**方式 A：从 sau 导入（推荐）**

```bash
cd ai-publish/backend && source .venv/bin/activate
python ../scripts/import_sau_cookie.py
```

**方式 B：Swagger 扫码**

`POST /api/platform-accounts/{id}/login`（需 `PLAYWRIGHT_HEADLESS=false`）

**校验：** `POST /api/platform-accounts/1/check-cookie` → `valid: true`

---

## 4. 发布一条图文（§4.1 流程）

推荐通过 **Vue 发布向导**（`/app/publish`）完成：

1. **主题与账号** — 选择平台（小红书/抖音/快手）、内容类型（图文/视频）、账号与主题  
2. **AI 文案** — 按平台模板生成标题、正文、标签等（可编辑）  
3. **AI 封面** — 图文：文生图；**小红书视频**：可选 3:4 视频封面（AI 生成/上传）；其他平台视频可跳过  
4. **素材确认** — 图文选图片；视频选/上传 MP4，小红书可附带封面图  
5. **排期提交** — 可选计划时间 → **保存草稿** 或 **提交待发布**  
6. 在 **发布任务** 页对 `待发布` 任务点击 **执行** — Playwright 发布  
7. `GET /api/publish-tasks/{id}/logs` — 查看步骤日志  
8. **草稿** 可点 **删除** 清理；**待审核**（需 `.env` 开启 `REQUIRE_CONTENT_REVIEW=true`）可 **通过/驳回**  

> 设置了 `publish_time` 的任务会在到点后**自动执行**（默认每 30 秒轮询，可通过 `SCHEDULER_POLL_INTERVAL_SECONDS` 调整）。未设置计划时间的任务仍需手动点「执行」。

### Swagger 等价流程

1. `POST /api/auth/login` → Authorize  
2. `POST /api/ai/text/generate` — 生成文案（含 `comment_guide`）  
3. `POST /api/ai/image/generate` — 可选，生成封面图  
4. `POST /api/materials/upload` — 或上传真实图片  
5. `POST /api/publish-tasks` — 创建任务，`submit: true`（进入待发布）  
6. `POST /api/publish-tasks/{id}/execute` — 手动触发发布  

---

## 5. 一键 E2E 脚本

```bash
cd ai-publish/backend && source .venv/bin/activate
# 小红书图文（默认）
python ../scripts/e2e_publish.py

# 抖音 / 快手（需先导入对应 Cookie）
python ../scripts/e2e_publish.py --platform douyin --content-type note
python ../scripts/e2e_publish.py --platform kuaishou --content-type video --cookie /path/to/cookie.json

# 仅验证 API 链路，不触发 Playwright 发布
python ../scripts/e2e_publish.py --platform xhs --skip-execute
```

### AI 文生图参数（阶段 E.3）

| 参数 | 说明 | 界面位置 |
|------|------|----------|
| `style` | 风格：清新自然 / 极简留白 / 鲜艳醒目 等 | 素材库「AI 生成图片」、发布向导 Step2 |
| `brand_color` | 品牌色，如 `#2E8B57` | 同上 |
| `brand_hint` | 品牌说明，如「高山有机春茶」 | 同上 |
| `ratio` | 比例：`1:1`、`3:4`、`4:5`、`9:16` 等 | 同上 |
| Prompt 预览 | 中文 / 英文 / 负面三栏 | 「预览 Prompt」按钮 |

生成记录写入 `ai_generation_records.result_summary`（JSON，含 style、品牌参数等），可在 **日志中心 → AI 记录** 查看。

---

## 6. Vue 管理后台

**生产模式（推荐）：**

```bash
cd ai-publish
./web.sh          # 构建前端
./start.sh        # 启动 API
```

浏览器打开：**http://127.0.0.1:8765/app/**

**开发模式（热更新）：**

```bash
# 终端 1
./start.sh

# 终端 2
./web.sh dev      # http://127.0.0.1:5173/app/
```

功能：概览、平台账号、AI 模型、素材库、发布任务、**发布向导**、系统设置。

> 发布流程：向导生成内容 → 提交待发布 → 任务页手动执行。文生图 Key 未配置时可跳过 AI 封面、改用手动上传。

### 用户与账号管理（阶段 E.1）

**个人改密：** 顶栏「修改密码」→ 输入原密码与新密码（所有已登录用户可用）。

**用户管理（仅管理员）：** 系统设置 → **用户管理**

- 新建用户：填写用户名、初始密码、角色
- 编辑：调整角色
- 重置密码：管理员为指定用户设置新密码
- 启用/禁用：禁用后该用户无法登录

**平台账号编辑（运营及以上）：** 平台账号页 → **编辑** → 可修改账号名与备注；只读角色（viewer）无编辑按钮。

**权限说明：** `viewer` 仅可查看；`reviewer` 仅可审核（无发布向导、无执行任务）；`operator` 可运营但无用户管理；`admin` 拥有全部权限。

### 内容审核（阶段 E.2）

在 **系统设置** 将 `require_content_review` 设为 `true` 后，发布向导「提交待发布」的任务会进入 **待审核**，不会直接进入待发布队列。

```mermaid
flowchart LR
  A[草稿] -->|提交| B{需审核?}
  B -->|是| C[待审核]
  B -->|否| D[待发布]
  C -->|通过| D
  C -->|驳回| E[已驳回]
  E -->|退回草稿| A
  D -->|执行| F[发布成功/失败]
```

**审核入口：**

1. 侧栏 **内容审核** → 待审核 Tab：预览正文/素材，通过或驳回（驳回须填原因）
2. **审核历史** Tab：查看审核人、时间、结果与驳回原因
3. 发布任务页仍保留快捷通过/驳回按钮（运营与审核主管可用）

### 敏感词检测（阶段 D.2）

在 **系统设置** 中可配置：

| 配置项 | 说明 |
|--------|------|
| `sensitive_word_enabled` | 是否启用敏感词检测（默认开启） |
| `sensitive_word_action` | `block` 拦截提交/执行；`warn` 仅写入任务日志 |

**敏感词管理：** 系统设置页 → **敏感词管理**（支持单条新增、批量粘贴导入、删除）。

检测字段：标题、正文、主题、封面文案、评论引导、标签。命中 `block` 时，发布向导提交或任务执行会返回明确错误（如「敏感词检测未通过：标题 含「xxx」」），并写入任务日志 `step=sensitive_word`。

试运行建议见 [phase-d-trial-guide.md](./phase-d-trial-guide.md)。

### 发布限频（阶段 D.3）

在 **系统设置** 中可配置：

| 配置项 | 默认 | 说明 |
|--------|------|------|
| `rate_limit_enabled` | 开启 | 总开关 |
| `rate_limit_min_interval_seconds` | 300 | 同账号两次**成功**发布最小间隔（秒） |
| `rate_limit_daily_per_account` | 10 | 单账号每日成功发布上限 |
| `rate_limit_max_concurrent` | 1 | 全局同时 `running` 的任务数 |
| `rate_limit_include_retry` | 开启 | 关闭后，带 `retry_count` 的自动重试不受日上限约束 |

手动「执行」、定时调度、自动重试入队前均会检查。被限频时任务保持 **pending**，原因写入任务日志 `step=rate_limit`（不会标为 failed）。

### 风控观测（阶段 D.O）

工作台 **风控观测（近 7 天）** 面板展示：敏感词/限频拦截次数、发布成功/失败与失败率、疑似风控失败数。失败任务列表增加 **归类** 列（疑似风控 / 技术 / 其他）。

试运行记录模板见 [phase-d-trial-guide.md](./phase-d-trial-guide.md)。

### 图片内容审核（阶段 D.5）

默认 **关闭**（`image_moderation_enabled=false`），行为与升级前一致。

开启后：

| 配置项 | 说明 |
|--------|------|
| `image_moderation_enabled` | 上传/文生图入库后执行审核 |
| `image_moderation_provider` | `stub`（免费）/ `tencent`（腾讯云 IMS，按量计费）/ `alibaba`（阿里云 Green，按量计费） |

**费用提示：** 在系统设置开启图片审核或切换为腾讯云/阿里云时，界面会弹出确认框。密钥在「图片内容审核」卡片中配置；`stub` 不产生云审费用。

图片素材 `moderation_status`：`passed` / `rejected` / `pending` / `skipped`。未通过或审核中的图片**不可**绑定到待发布任务；素材库与发布向导会过滤。

---

**验收步骤（开启审核）：**

1. 系统设置 → `require_content_review` 开关拨到 **开启** → 点该行「保存」（须看到「内容审核已开启」提示）
2. 运营账号提交一条任务 → 状态应为 `待审核`
3. 使用 `reviewer` / `reviewer123` 登录 → 仅有「内容审核」等只读/审核菜单，无「发布向导」「执行」
4. 在内容审核页通过 → 任务变为 `待发布`；运营或管理员可执行发布
5. 审核历史 Tab 可看到记录（含审核人、时间）

### 素材与任务运维（阶段 E.4）

**文案素材：** 发布向导 Step1 生成文案后，可点 **保存到素材库**；素材库类型筛选选「文案」可预览全文。

**自动重试：** 系统设置可配置 `auto_retry_enabled`、`max_auto_retries`、`retry_delay_minutes`。任务执行失败后按间隔自动重试，达上限后保持 `failed`，可手动重试。

**素材清理：** 开启 `material_cleanup_enabled` 并设置 `material_retention_days` 后，系统每小时清理超过保留期且未被任何发布任务引用的素材文件。

**缩略图：** 上传图片或 AI 文生图后自动生成列表缩略图，加快素材库加载。

### B站投稿（阶段 E.5.4，实验）

- 发布向导选择 **B站（实验）**，内容类型固定为**视频**，需选择**投稿分区 tid**
- 登录：在本地终端执行 `cd vendor/social-auto-upload && sau bilibili login --account <账号名>`，完成后在平台账号页点「校验 Cookie」
- 发布通过 **biliup CLI** 上传，不支持图文笔记

### 视频号投稿（阶段 E.5.5，实验）

- 发布向导选择 **视频号（实验）**，内容类型为**短视频**
- 支持可选 **3:4 封面** 与 **短标题**（6-16 字，对应 `cover_text`）
- 登录：平台账号页 **扫码登录**（微信 App 扫视频号创作者二维码）
- E2E：`python ai-publish/scripts/e2e_publish.py --platform channels --skip-execute`

### 运维监控（阶段 E.6）

- **健康检查**：`GET /health` 返回数据库、Redis、队列 `queue_depth`
- **指标**：`GET /metrics`（Prometheus 文本格式，任务各状态计数 + 队列深度）
- **工作台**：过期账号、失败任务过多时顶部告警条；顶栏铃铛同步提醒
- **账号过期**：校验 Cookie 失效时写入操作日志 `platform_account.expired`
- 验收记录模板：[platform-publish-verification.md](./platform-publish-verification.md)

---

## 7. 简易 HTML 管理页（旧）

http://127.0.0.1:8765/admin/（若未构建 Vue 则可用）

---

## 8. 常见问题

| 问题 | 处理 |
|------|------|
| check-cookie 500 | 运行 `import_sau_cookie.py` 重新导入 Cookie |
| 文生图只有 1x1 占位图 | 配置 `DASHSCOPE_API_KEY` 或 `OPENAI_API_KEY` |
| execute 卡住 | 确认 Chrome 弹出且 Cookie 有效 |
| 标签「AI发布」被跳过 | 非阻塞，可换常见标签如「测试」 |

---

## 9. 下一步扩展

- **Vue 完整管理后台**：独立 change，基于现有 API
- **多平台**：抖音、快手、B站、视频号已接入 Adapter（B站/视频号标为实验）
- **Docker 部署**：`docker compose up`（需 Docker Desktop）
