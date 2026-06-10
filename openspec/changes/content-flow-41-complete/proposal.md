## Why

MVP 已跑通「小红书 + AI 文案 + 手动发布」，但与产品文档 **§4.1 内容生成到发布流程** 不一致：发布页跳过 AI 文生图、无草稿与待发布分离、创建后立刻执行发布。需要在不引入风控 C 方案（审核队列 + 本机发）的前提下，补齐 §4.1 主链路，并为后续审核/Celery 扩展预留状态机。

## What Changes

- **发布向导重构**：`PublishView` 改为多步流程——主题 → AI 文案 → AI 文生图 → 素材确认 → 账号/计划时间 → 保存草稿或提交待发布（**不再一键 execute**）
- **任务状态机扩展**：`draft` → `pending` → `running` → `success`|`failed` 保持不变；新增可选状态 `pending_review` / `approved` 的**字段与流转预留**（本 change 默认关闭，不实现审核 UI）
- **AI 文生图接入发布链路**：发布流程内调用现有 `POST /api/materials/generate-image`，自动绑定素材到任务
- **评论引导文案**：AI 文案生成增加 `comment_guide` 字段；任务表与 API 持久化（MVP 发布可不写入平台，仅展示与存档）
- **计划发布时间 UI**：创建/提交任务时可设置 `publish_time`（仍不实现 Celery 自动调度，仅保存与展示）
- **素材页 AI 生图入口**：素材中心增加「AI 生成图片」对话框，复用文生图 API
- **BREAKING**：`PublishView` 默认行为从「创建并立即发布」改为「创建草稿或提交待发布」；用户须在任务列表手动点「执行」

## Capabilities

### New Capabilities

- `publish-wizard`：前端多步发布向导，对齐产品文档 §4.1 步骤与交互

### Modified Capabilities

- `publish-task`：状态机预留审核节点；提交与执行分离；新增 `comment_guide`；禁止 draft 直接 execute
- `ai-content`：文案生成输出 `comment_guide`；发布链路内文生图参数（比例/数量）规范
- `material`：素材与发布任务/草稿的双向关联展示；素材页 AI 生图入口

## Impact

- **后端**：`publish_tasks` 表新增 `comment_guide`；`PublishService` 状态流转与 execute 校验；`material_service` / AI 文案 Adapter 与 Schema
- **前端**：`PublishView.vue` 重构为多步向导；`TasksView.vue` 展示 `publish_time` / `comment_guide`；`MaterialsView.vue` 增加 AI 生图
- **数据库**：`init_db.sql` + migration 脚本
- **文档**：`docs/daily-usage.md` 更新操作流程
- **不在范围**：Celery Worker、审核管理页、本机发布 Worker、RBAC、多平台
