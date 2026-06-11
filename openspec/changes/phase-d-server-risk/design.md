## Context

当前发布执行路径：

```
创建/草稿 → submit（可选 pending_review）→ approve → pending
    → execute → Redis 队列 → UploadWorker → Platform Adapter（Playwright/biliup）
```

风控插入点应在前置闸门，**不改变**上述执行端。

**前置已完成：**

- E.2 人工审核（`require_content_review` + 审核工作台）
- E.4 失败自动重试（须与 D.3 限频协调：重试计入频率）
- E.6 监控告警（可扩展风控类告警）

## Goals / Non-Goals

**Goals:**

- 在不引入本机 Worker 的情况下，降低违规内容与过激发布频率带来的平台风控风险
- 所有风控能力可配置、可关闭，默认保守（开启敏感词与限频，图片审核可选）
- 试运行 2～4 周后，能用数据判断是否需要 D.4

**Non-Goals:**

- D.4 本机 Worker 实现
- 100% 拦截平台侧风控（无法保证，只能降低概率）

## D.4 暂缓策略

### 试运行假设

继续使用 **服务器无头 Chromium**（Docker 推荐）或 **本地开发 Chrome**，配合：

- 人工审核（已具备）
- 敏感词机审（D.2）
- 发布限频（D.3）
- 图片机审（D.5，可选）

### 观测指标（建议试运行期记录）

| 指标 | 来源 | 关注阈值（示例，可配置） |
|------|------|--------------------------|
| 发布失败率 | `publish_tasks.status=failed` / 总执行数 | 连续 7 天 > 15% |
| 平台风控类错误 | `error_message` 含「频繁」「违规」「限制」「风控」等关键词 | 单账号周 ≥ 3 次 |
| 账号 Cookie 失效率 | `platform_accounts.status=expired` 增速 | 月环比明显上升 |
| 限频拦截次数 | 新增 `operation_logs` 或 `publish_task_logs` | 用于评估 D.3 是否过严 |
| 敏感词拦截次数 | 机审日志 | 评估词库质量 |

### 触发重新评估 D.4 的条件（满足任一可考虑立项 D.4）

1. 在 D.2+D.3 已开启且发布量适中时，**风控类失败仍持续偏高**
2. 多账号在 **服务器 IP** 下集中失效，本机 Chrome 试点明显更稳
3. 合规要求「发布动作必须在运营人员本机完成」

### 不触发 D.4 的条件

- 失败主要来自 Cookie 过期、DOM 变更、素材问题等非风控因素
- D.3 限频后失败率下降至可接受范围
- 单服务器 + 低频次发布场景下账号稳定

## Decisions

### D1: 敏感词（D.2）— 本地词库 + 提交/执行双检查

| 选项 | 结论 |
|------|------|
| 仅人工审核 | 不选用。漏检成本高 |
| 云端内容安全 API | 二期可选；MVP 用本地词库降低依赖 |
| **本地词库 + AC 自动机/简单包含匹配** | **选用**。词库存 `system_configs` 或 `sensitive_words` 表 |

**检查时机：**

- `POST/PUT publish-tasks` 创建/更新（title、content、tags、cover_text、comment_guide）
- `submit_task` 提交前（硬拦截）
- `execute_task` 执行前（二次校验，防绕过）
- `POST /api/ai/text/generate` 生成后可选告警（软提示，不阻断生成）

**行为：**

- `sensitive_word_action=block`（默认）：命中则 400，返回命中词（脱敏展示）
- `sensitive_word_action=warn`：仅写 `publish_task_logs`，允许继续

### D2: 发布限频（D.3）— 账号维度 + 全局并发

**配置项（`system_configs`）：**

| Key | 默认 | 说明 |
|-----|------|------|
| `rate_limit_enabled` | `true` | 总开关 |
| `rate_limit_min_interval_seconds` | `300` | 同账号两次成功发布最小间隔 |
| `rate_limit_daily_per_account` | `10` | 单账号每日成功发布上限 |
| `rate_limit_max_concurrent` | `1` | 全局同时 `running` 任务数 |
| `rate_limit_include_retry` | `true` | 自动重试是否计入日上限 |

**检查点：**

- `execute_task` / `task_queue.enqueue_execute` 之前
- `schedule_worker.poll_due_tasks` 定时触发前
- 命中限频：任务保持 `pending`，写日志，**不**改 `failed`（可选手动重试）

**存储：** 优先查 `publish_tasks` 历史（`account_id` + `success` + `updated_at`），无需新表；并发用 `status=running` 计数。

### D3: 图片审核（D.5）— 可插拔 Provider

| 阶段 | 方案 |
|------|------|
| MVP | `image_moderation_enabled=false` 默认关；开启后调用 **Provider 接口** |
| Provider A | 腾讯云/阿里云内容安全 API（配置 Key 后启用） |
| Provider B | `stub`：仅记录日志、一律通过（开发环境） |

**检查时机：**

- `upload_material` 图片上传后
- `generate_image` 文生图入库后
- `submit_task` 前校验任务关联图片素材均已 `moderation_status=passed`

**素材字段扩展：**

- `materials.moderation_status`：`pending` / `passed` / `rejected`
- `materials.moderation_detail`：JSON 或 TEXT

未配置云 API 时，开关保持关闭，不影响现有流程。

### D4: 与 E.2 审核的关系

```
机审（D.2/D.5）→ [可选] 人审（E.2）→ 限频（D.3）→ 服务器执行
```

- 机审失败：**不可**进入 `pending_review` / `pending`
- 人审驳回：与机审独立，已有 `rejected` 状态

### D5: 前端

- 系统设置页：敏感词管理（列表增删）、限频参数、图片审核开关与 Provider 配置
- 发布向导 / 任务详情：展示机审失败原因
- 素材库：展示图片审核状态

## Risks

| 风险 | 缓解 |
|------|------|
| 限频过严导致积压 | 默认保守值 + 日志可观测 + 设置页可调 |
| 敏感词误杀 | 支持 `warn` 模式、词库分「禁止/提醒」两级（二期） |
| 图片云审成本 | 默认关闭；按量配置 |
| 重试与限频冲突 | `rate_limit_include_retry` 可配置；自动重试前也走限频检查 |

## Open Questions

1. 敏感词词库是否需按行业/import 模板（茶叶、电商）预置？→ MVP 提供空词库 + 设置页手工维护 + 可选种子词文件
2. 图片审核首选哪家云 API？→ 实施时按部署环境（腾讯云为主）选型，Provider 抽象便于切换
