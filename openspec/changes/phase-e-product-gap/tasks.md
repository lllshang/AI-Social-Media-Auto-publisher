# 阶段 E — 产品文档缺口补齐（除阶段 D 风控外）

> 对照文档：`docs/AI多平台内容自动发布系统产品文档.docx`  
> 前置完成：阶段 A / B / C（见 `content-flow-41-complete/tasks.md`）  
> **本清单不包含阶段 D**（敏感词、频率限制、本机 Worker、图片审核）

---

## 阶段 E.1 — 用户与账号管理细化（P1，建议先做）

### 后端专家

- [x] E.1.1 用户管理 API：`GET/POST/PUT /api/users`（列表、创建、禁用/启用、分配 `role_id`）
- [x] E.1.2 用户改密 API：`POST /api/users/{id}/reset-password`（管理员重置）+ `POST /api/auth/change-password`（本人修改）
- [x] E.1.3 平台账号编辑 API：`PUT /api/platform-accounts/{id}`（账号名、备注等可编辑字段）
- [x] E.1.4 操作日志写入客户端 IP：`add_operation` 从 `Request` 取 IP；发布/账号等关键写操作补记操作日志
- [x] E.1.5 权限点：用户管理仅 `admin` 或新增 `users:write` 权限（与现有 RBAC 对齐）

### 前端专家

- [x] E.1.6 系统设置下新增「用户管理」页：列表、新建用户、禁用、重置密码、分配角色
- [x] E.1.7 平台账号页支持编辑账号名；只读角色保持不可编辑
- [x] E.1.8 个人改密入口（顶栏或设置页，operator/admin 可用）

### 文档与验证

- [x] E.1.9 更新 `docs/daily-usage.md`、`docs/project-overview.md` 默认账号与用户管理说明
- [x] E.1.10 验证：admin 可建用户并分配 viewer；viewer 无法进入用户管理

---

## 阶段 E.2 — 审核管理独立模块（P1）

> 说明：approve/reject API 与任务列表按钮已有；本阶段补齐**独立审核工作台**（仍不引入 D.2～D.5 风控能力）。

### 后端专家

- [x] E.2.1 审核列表 API：`GET /api/publish-tasks?status=pending_review` 增强（分页、按平台/时间筛选）或专用 `GET /api/reviews`
- [x] E.2.2 审核记录：驳回原因、审核人、审核时间写入任务或独立 `review_logs`（择一，需 DDL）
- [x] E.2.3 `require_content_review=true` 时，提交任务默认进 `pending_review`（与系统设置联动，回归测试）

### 前端专家

- [x] E.2.4 新增「内容审核」菜单（`tasks:write` 或独立 `review:write` 权限）
- [x] E.2.5 审核列表页：待审任务、正文/素材预览、通过/驳回（驳回填原因）
- [x] E.2.6 审核历史 Tab：已审记录查询（对接 E.2.2）

### 文档与验证

- [x] E.2.7 更新 `daily-usage.md` 审核流程图；开启 `require_content_review` 的验收步骤
- [x] E.2.8 验证：运营主管角色可仅审核不发布（可选新建 `reviewer` 角色）

---

## 阶段 E.3 — AI 文生图与提示词增强（P2）

### 后端专家

- [x] E.3.1 `POST /api/ai/prompt/build` 响应扩展：`prompt_zh`、`prompt_en`、`negative_prompt`（模板或 LLM 重构二选一，需可回退）
- [x] E.3.2 `POST /api/ai/image/generate` 支持 `style`、`brand_color`、`brand_hint` 等参数并写入 `ai_generation_records`
- [x] E.3.3 补充 `douyin`/`kuaishou` 以外常用比例模板（如 `4:5`、`1:1`）于 `templates/prompts/`

### 前端专家

- [x] E.3.4 素材页「AI 生成图片」：增加风格下拉、品牌色/品牌说明输入
- [x] E.3.5 发布向导文生图步骤：Prompt 预览（复用 `buildPrompt`）、风格与封面文案联动
- [x] E.3.6 Prompt 预览展示中/英/负面三栏（只读）

### 文档与验证

- [x] E.3.7 产品文档 §6 参数表与界面对照截图写入 `docs/daily-usage.md`
- [x] E.3.8 验证：不同 `style` 请求落库且生成记录可追踪

---

## 阶段 E.4 — 素材与任务运维增强（P2）

### 后端专家

- [x] E.4.1 文案素材类型（可选）：`materials.type=text` 或将 AI 文案保存为可复用草稿资产
- [x] E.4.2 失败任务自动重试：Worker 或调度器按配置 `max_auto_retries`、`retry_delay_minutes` 重试 `failed` 任务
- [x] E.4.3 素材清理策略：按天数/容量清理本地或对象存储孤儿文件（`system_configs` 可配开关）
- [x] E.4.4 缩略图：上传/文生图后生成 `materials.thumbnail`（列表预览优化）

### 前端专家

- [x] E.4.5 系统设置增加：自动重试次数、素材保留天数配置项
- [x] E.4.6 素材库支持筛选/预览文案类素材（若做 E.4.1）

### 文档与验证

- [x] E.4.7 `deployment.md` 补充磁盘监控与清理 cron 建议
- [x] E.4.8 验证：模拟失败后自动重试达上限停止；清理不误删关联任务素材

---

## 阶段 E.5 — 多平台发布验收与扩展（P2～P3）

### 后端专家 — 验收（P2）

- [x] E.5.1 抖音图文+视频 E2E 脚本与文档（`scripts/e2e_publish.py` 扩展 `platform=douyin`）
- [x] E.5.2 快手图文+视频 E2E 脚本与文档（`platform=kuaishou`）
- [x] E.5.3 根据 E2E 结果修复 Adapter/DOM/超时问题并记录 spike 结论

### 后端专家 — 新平台（P3）

- [x] E.5.4 Bilibili Adapter + 前端平台常量 + prompt 模板
- [x] E.5.5 视频号 Adapter Spike + 最小可用发布（图文或短视频择一）
- [ ] E.5.6 百家号 / TikTok：仅 Spike 报告，不强制本阶段交付

### 前端专家

- [x] E.5.7 平台选择器与发布向导随 E.5.4/E.5.5 扩展；未实现平台不展示或标「实验」

### 文档与验证

- [x] E.5.8 更新 `multi-platform-roadmap.md` 验收状态表
- [ ] E.5.9 每平台至少 1 条成功发布记录（测试环境截图或日志）

---

## 阶段 E.6 — 运维、监控与通知（P3）

### 后端专家

- [ ] E.6.1 健康检查增强：`/health` 含 DB、Redis、队列积压长度
- [ ] E.6.2 可选 Prometheus metrics 端点（任务成功/失败计数、队列深度）
- [ ] E.6.3 账号 `expired` 状态变更时写入 `operation_logs` 或站内通知表

### 前端专家

- [ ] E.6.4 工作台「账号已过期」醒目提醒条 + 跳转账号页
- [ ] E.6.5 可选：简单站内通知铃铛（过期账号、失败任务超 N 条）

### 运维 / 文档

- [ ] E.6.6 `deployment.md`：Let's Encrypt / 正式 HTTPS 证书替换自签步骤
- [ ] E.6.7 Docker Compose 示例：日志轮转、磁盘告警建议（Grafana 可选）

---

## 阶段 E.7 — 运营增强（P3，产品文档 §13.2）

### 后端专家

- [ ] E.7.1 内容模板库：`content_templates` 表 + CRUD API（行业、平台、文案/文生图模板）
- [ ] E.7.2 发布向导 Step1 可选「从模板创建」

### 前端专家

- [ ] E.7.3 「内容模板」管理页（分类、预览、启用/停用）
- [ ] E.7.4 工作台增加按平台/状态的任务趋势简图（现有统计 API 扩展）

### 文档与验证

- [ ] E.7.5 茶叶/电商等 1～2 个示例模板种子数据
- [ ] E.7.6 明确「平台播放/转化数据」仍为 Out of Scope，写入 `proposal.md` Non-Goals

---

## 阶段 D — 风控 C 方案（保持原规划，本 change 不做）

- [ ] D.1 审核管理独立模块 → **E.2 覆盖 UI/API 增强；D.4 本机 Worker 仍归 D**
- [ ] D.2 敏感词检测
- [ ] D.3 发布频率与并发限制
- [ ] D.4 本机发布 Worker（审核通过后本机 Chrome 执行）
- [ ] D.5 图片内容审核

---

## 推荐实施顺序

```
E.1 用户/账号  →  E.2 审核模块  →  E.5.1～E.5.3 抖音/快手验收
      →  E.3 文生图增强  →  E.4 运维重试/清理  →  E.5.4+ 新平台
      →  E.6 监控通知  →  E.7 模板库
      →  D 风控（最后）
```

---

## 完成判定（Hard Gates）

- 任务勾选 `[x]` 前须：代码可运行 + 关键路径自检 + 无新增明显静态错误
- 涉及新表须同步 `init_db.sql` 与 `migrations.py`
- 前端写操作须 RBAC 与后端 `require_permission` 一致
- 每子阶段交付须更新 `docs/project-overview.md` §路线图状态
