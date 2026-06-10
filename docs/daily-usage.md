# AI 多平台内容自动发布 — 日常使用手册

适用版本：MVP（小红书首发）  
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

- 默认账号：`admin` / `admin123`
- 停止：终端 `Ctrl+C`

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

## 3. 小红书 Cookie

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

1. **主题与账号** — 选择小红书账号、输入内容主题  
2. **AI 文案** — 生成标题、正文、标签、封面文案、评论引导（可编辑）  
3. **AI 封面** — 文生图生成 3:4 封面（Key 未配置可跳过，改用手动上传）  
4. **素材确认** — 确认或补充图片素材  
5. **排期提交** — 可选计划时间 → **保存草稿** 或 **提交待发布**  
6. 在 **发布任务** 页对 `待发布` 任务点击 **执行** — Playwright 发布  
7. `GET /api/publish-tasks/{id}/logs` — 查看步骤日志  
8. **草稿** 可点 **删除** 清理；**待审核**（需 `.env` 开启 `REQUIRE_CONTENT_REVIEW=true`）可 **通过/驳回**  

> 当前版本设置了 `publish_time` 也**不会自动执行**，需手动点「执行」。Celery 定时发布为后续 change。

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
python ../scripts/e2e_publish.py
```

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

功能：概览、平台账号、AI 模型、素材库、发布任务、**发布向导**。

> 发布流程：向导生成内容 → 提交待发布 → 任务页手动执行。文生图 Key 未配置时可跳过 AI 封面、改用手动上传。

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

## 8. 下一步扩展

- **Vue 完整管理后台**：独立 change，基于现有 API
- **多平台**：抖音/视频号需新增 `PlatformAdapter`
- **Docker 部署**：`docker compose up`（需 Docker Desktop）
