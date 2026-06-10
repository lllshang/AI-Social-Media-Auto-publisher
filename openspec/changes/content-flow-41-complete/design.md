## Context

`ai-publish` 已有 FastAPI + Vue3 管理后台、小红书图文发布、AI 文案/文生图 API、素材中心与任务管理。当前 `PublishView` 在创建任务后立即调用 `execute`，跳过 §4.1 中的文生图、草稿确认与待发布队列步骤。

产品文档 §4.1 要求：

```
主题 → AI 文案 → AI 文生图 → 素材绑定草稿 → 选账号/时间 → 审核或待发布 → Worker 执行
```

本 change 实现 §4.1 **至「待发布队列」**，审核与 Worker 调度分属后续 change。

**约束：**

- 风控 C 方案（审核后本机发）**不做**
- Celery 定时发布**不做**（`publish_time` 仅存储展示）
- 仍仅支持小红书图文 `note`

## Goals / Non-Goals

**Goals:**

- 前端发布向导与 §4.1 步骤一一对应
- 文生图结果自动入库并绑定到同一发布任务（草稿）
- 创建与执行分离：`draft`/`pending` 才允许在任务页手动 execute
- AI 文案增加 `comment_guide` 并持久化
- 状态机预留 `pending_review` → `approved` → `pending`（配置开关，默认关闭）

**Non-Goals:**

- 审核管理页面、批准/驳回 API、本机发布 Worker
- Celery / APScheduler 到点执行
- 敏感词检测、发布频率限制
- 多平台、视频发布、RBAC

## Decisions

### D1: 草稿实体 — 复用 `publish_tasks`，不新建表

| 选项 | 结论 |
|------|------|
| 新建 `content_drafts` 表 | 不选用。增加关联复杂度 |
| **`publish_tasks.status=draft` 即草稿** | **选用**。与现有 API 一致，素材通过 `material_ids` 绑定 |

向导中途「保存草稿」调用 `POST /api/publish-tasks`（`submit=false`）；最后一步「提交待发布」调用 `POST /{id}/submit`。

### D2: 文生图 — 复用现有 API，向导内串联

发布向导 Step 3 调用 `POST /api/materials/generate-image`（`topic`、`platform=xhs`、`ratio=3:4`、`count=1`），将返回的 `materials[].id` 写入表单的 `material_ids`。用户可重新生成或改选手动上传素材。

封面文案 `cover_text` 来自 Step 1 文案结果，作为文生图 `topic` 的补充参数（拼接进 prompt 或通过现有模板 `{topic}` 传递）。

### D3: 状态机 — 预留审核，默认直连 pending

```python
# settings.require_content_review = False（默认）
draft → submit → pending → execute → running → success|failed

# settings.require_content_review = True（预留，本 change 仅实现流转，无 UI）
draft → submit → pending_review → approve → pending → execute → ...
```

`PublishService.submit_task`：

- `require_content_review=False`：`draft` → `pending`
- `require_content_review=True`：`draft` → `pending_review`

新增 `approve_task` / `reject_task` 方法占位（本 change 实现 API，前端暂不暴露）。

`execute_task` **仅允许** `status in {pending}`，拒绝 `draft` / `pending_review`。

### D4: 评论引导 — 文案 JSON 新字段

Prompt 模板与 Adapter 解析增加 `comment_guide`（评论引导语，50 字以内）。存入 `publish_tasks.comment_guide`。小红书 Adapter 暂不写入平台表单（平台字段不稳定），仅存档供运营复制。

### D5: 前端向导步骤

| Step | 标题 | 动作 |
|------|------|------|
| 0 | 主题与账号 | 输入 topic、选择 account_id |
| 1 | AI 文案 | 生成 title/content/tags/cover_text/comment_guide，可编辑 |
| 2 | AI 封面 | 调用文生图，展示预览，可重生成 |
| 3 | 素材确认 | 确认 material_ids，可上传补充 |
| 4 | 排期提交 | 可选 publish_time；「保存草稿」或「提交待发布」 |

移除「创建并发布」单按钮；成功提交后跳转 `/tasks`。

### D6: 数据库变更

```sql
ALTER TABLE publish_tasks ADD COLUMN comment_guide TEXT NULL AFTER content;
```

`init_db.sql` 同步更新；`migrations.py` 增加幂等迁移。

## Risks / Trade-offs

| 风险 | 缓解 |
|------|------|
| 用户习惯「一键发布」被打破 | 任务页保留明显的「执行」按钮；daily-usage 文档说明新流程 |
| 文生图 Key 未配置导致 Step 2 失败 | 允许跳过文生图，改用手动上传；stub 占位图给出明确提示 |
| `pending_review` 预留但无 UI 造成困惑 | 默认 `require_content_review=false`；环境变量文档说明 |
| 计划时间设置了但不会自动发 | UI 标注「到点自动发布即将支持，当前需手动执行」 |

## Migration Plan

1. 部署前执行 DB migration（`comment_guide` 列）
2. 构建并部署新 `web/dist`
3. 已在进行中的 `running` 任务不受影响
4. 回滚：还原前端 + 后端；新列可保留（nullable）

## Open Questions

- 文生图默认比例是否固定 `3:4`（小红书封面）——**暂定是**，向导不提供高级选项（后续 change）
- `comment_guide` 是否需要在任务详情页可复制——**是**，TasksView 抽屉展示
