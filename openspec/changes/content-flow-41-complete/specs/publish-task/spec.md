# Publish Task (Delta)

## MODIFIED Requirements

### Requirement: 任务状态机

发布任务 MUST 遵循状态流转：`draft` → `pending` → `running` → `success` | `failed`；`failed` 可重试回到 `pending`。当 `require_content_review=true` 时，MUST 支持 `draft` → `pending_review` → `approved` → `pending` 的扩展流转（本 change 默认关闭审核开关）。

#### Scenario: 提交待发布

- **WHEN** 用户将任务从 `draft` 提交（或创建时 `submit=true`）且 `require_content_review=false`
- **THEN** 任务状态变为 `pending`，等待手动执行

#### Scenario: 提交进入审核预留状态

- **WHEN** 用户提交任务且 `require_content_review=true`
- **THEN** 任务状态变为 `pending_review`，不可 execute，直至 approve

#### Scenario: 执行中

- **WHEN** 用户触发任务执行且任务为 `pending`
- **THEN** 状态变为 `running`，完成后变为 `success` 或 `failed`

#### Scenario: 草稿不可执行

- **WHEN** 用户调用 execute 且任务为 `draft` 或 `pending_review`
- **THEN** 系统返回 400 错误，不启动 Worker

### Requirement: 手动触发执行

系统 SHALL 支持通过 API 手动触发发布；execute MUST 仅对 `pending` 状态任务生效。

#### Scenario: 手动执行

- **WHEN** 用户调用 `POST /api/publish-tasks/{id}/execute` 且任务为 `pending`
- **THEN** 系统启动 Upload Worker 执行发布，异步更新状态与日志

#### Scenario: 重复执行防护

- **WHEN** 任务已处于 `running` 状态
- **THEN** 系统返回 409 冲突，不启动第二个 Worker

## ADDED Requirements

### Requirement: 评论引导字段

发布任务 MUST 包含 `comment_guide` 字段，用于存储 AI 生成的评论引导文案。

#### Scenario: 创建任务含评论引导

- **WHEN** 用户创建或更新任务并提交 `comment_guide`
- **THEN** 系统持久化该字段并在任务详情 API 中返回

### Requirement: 审核流转预留

系统 SHALL 提供 `approve` 与 `reject` API，将 `pending_review` 任务转为 `pending` 或 `rejected`（本 change 不实现审核管理前端页面）。

#### Scenario: 审核通过

- **WHEN** 管理员调用 `POST /api/publish-tasks/{id}/approve` 且任务为 `pending_review`
- **THEN** 任务状态变为 `pending`，可 execute

#### Scenario: 审核驳回

- **WHEN** 管理员调用 `POST /api/publish-tasks/{id}/reject` 且任务为 `pending_review`
- **THEN** 任务状态变为 `rejected`，不可 execute

### Requirement: 草稿更新

系统 SHALL 支持对 `draft` 状态任务的字段更新（标题、正文、标签、素材、计划时间等）。

#### Scenario: 更新草稿

- **WHEN** 用户调用 `PUT /api/publish-tasks/{id}` 且任务为 `draft`
- **THEN** 系统更新任务字段并保持 `draft` 状态
