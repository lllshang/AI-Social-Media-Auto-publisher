# 阶段 D — 服务器端风控规格（D.4 暂缓）

> 变更目录：`openspec/changes/phase-d-server-risk/`  
> 前置：阶段 E 已完成；D.1 人工审核由 E.2 交付  
> 执行模式：**不变** — Redis 队列 + 服务器 Adapter 发布

---

## 1. 用户故事

### US-D1 运营人员 — 提交前知道文案是否违规

作为运营，我在发布向导填写标题/正文后点击「提交待发布」，若含敏感词，系统应明确告知哪类内容违规，并阻止进入发布队列。

### US-D2 管理员 — 可维护敏感词与限频策略

作为管理员，我可在系统设置中维护敏感词列表、调整单账号发布间隔与日上限，无需改代码或重启（热加载词库或短周期缓存）。

### US-D3 运营主管 — 审核前多一道机器闸门

作为审核主管，开启内容审核时，已进入 `pending_review` 的任务应已通过敏感词机审；被机审拦截的任务不应出现在审核列表。

### US-D4 运维 — 试运行期能判断要不要上本机 Worker

作为运维，我能在日志/工作台看到：限频拦截次数、敏感词拦截次数、疑似平台风控的失败占比，用于评估 D.4 是否有必要。

### US-D5 运营 — 图片素材合规（可选）

作为运营，当管理员开启图片审核后，上传或 AI 生成的违规图片应被标记并阻止绑定到待发布任务。

---

## 2. 功能需求

### 2.1 D.2 敏感词检测

| ID | 需求 | 验收 |
|----|------|------|
| D.2.1 | 支持敏感词 CRUD API（`templates:write` 或新建 `risk:write`） | 增删改查词库 |
| D.2.2 | 词库支持启用/停用单条或全局开关 `sensitive_word_enabled` | 关闭后跳过检测 |
| D.2.3 | 检测字段：`title`、`content`、`tags`、`cover_text`、`comment_guide` | 命中返回明确字段 |
| D.2.4 | `submit_task` 与 `execute_task` 前强制检测（`block` 模式） | 命中返回 HTTP 400 |
| D.2.5 | 命中记录写入 `publish_task_logs`（step=`sensitive_word`） | 任务详情可查看 |
| D.2.6 | 设置页词库管理 UI | 列表、批量导入（文本域粘贴） |

### 2.2 D.3 发布频率与并发限制

| ID | 需求 | 验收 |
|----|------|------|
| D.3.1 | 配置项见 `design.md` D2 表 | 设置页可编辑 |
| D.3.2 | 同 `account_id` 距上次 `success` 间隔 < 配置值时拒绝执行 | 返回可读错误 |
| D.3.3 | 同账号当日 `success` 次数 ≥ 日上限时拒绝 | 跨日重置 |
| D.3.4 | 全局 `running` 任务数 ≥ `max_concurrent` 时排队（保持 pending） | 不丢任务 |
| D.3.5 | 定时调度 `poll_due_tasks` 与手动 execute 均受限 | 行为一致 |
| D.3.6 | 自动重试（E.4）执行前同样限频检查 | 配置 `include_retry` 生效 |
| D.3.7 | 限频拒绝写入 `publish_task_logs`（step=`rate_limit`） | 可观测 |

### 2.3 D.5 图片内容审核

| ID | 需求 | 验收 |
|----|------|------|
| D.5.1 | `materials` 增加 `moderation_status`、`moderation_detail` | DDL + migration |
| D.5.2 | `image_moderation_enabled` 默认 `false` | 未开启时行为与现网一致 |
| D.5.3 | 图片上传、文生图完成后异步或同步调用 `ImageModerationProvider` | 状态入库 |
| D.5.4 | `submit_task` 校验关联图片素材均为 `passed`（开启时） | 含 `rejected` 则 400 |
| D.5.5 | Provider：`stub`（开发）+ 至少一种云 API 适配器占位或实现 | 接口抽象 |
| D.5.6 | 素材库列表展示审核状态 | 前端 |

### 2.4 风控可观测（支撑 D.4 决策）

| ID | 需求 | 验收 |
|----|------|------|
| D.O.1 | Dashboard 或日志汇总：近 7 天敏感词拦截、限频拦截计数 | 工作台可见 |
| D.O.2 | 失败任务 `error_message` 关键词归类统计（风控/其他） | API 或面板 |
| D.O.3 | `docs/phase-d-trial-guide.md` 试运行 checklist（观测周期、记录模板） | 文档 |

---

## 3. D.4 暂缓说明

| 项目 | 状态 |
|------|------|
| 本机发布 Worker | **暂缓**，非永久不做 |
| 试运行路径 | 服务器/Docker 执行 + D.2 + D.3 +（可选）D.5 + E.2 人审 |
| 重新评估 | 见 `design.md`「触发重新评估 D.4 的条件」 |

---

## 4. 权限

| 权限 | 用途 |
|------|------|
| `risk:read` | 查看风控配置与拦截统计 |
| `risk:write` | 管理敏感词、风控配置 |

默认：`admin` 全权限；`operator` 可读；`viewer` 可读统计（可选）。

或复用 `settings:write` 管理风控配置（实施时二选一，tasks 中明确）。

---

## 5. 非功能需求

- 敏感词检测单次 < 50ms（词库 ≤ 5000 词）
- 限频检查单次 < 100ms（索引：`publish_tasks(account_id, status, updated_at)`）
- 所有风控开关关闭时，性能与现网无明显差异

---

## 6. 不在范围

- D.4 本机 Worker
- 平台播放/转化数据
- 视频内容审核（MVP 仅图片；视频标为二期）
