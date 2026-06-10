# Publish Task

## Purpose

Create, execute, and track multi-platform content publish tasks with step-level logging.

## Requirements

### Requirement: 发布任务创建

系统 SHALL 支持创建发布任务，包含标题、正文、标签、目标平台、目标账号、关联素材及可选计划发布时间。

#### Scenario: 创建草稿任务

- **WHEN** 用户调用 `POST /api/publish-tasks` 提交完整必填字段
- **THEN** 系统创建任务，初始状态为 `draft`，返回 `task_id`

#### Scenario: 缺少必填字段

- **WHEN** 用户未提供 `platform`、`account_id` 或 `title`
- **THEN** 系统返回 422 校验错误

### Requirement: 任务状态机

发布任务 MUST 遵循状态流转：`draft` → `pending` → `running` → `success` | `failed`；`failed` 可重试回到 `pending`。

#### Scenario: 提交待发布

- **WHEN** 用户将任务从 `draft` 提交（或创建时直接 `pending`）
- **THEN** 任务状态变为 `pending`，等待手动执行

#### Scenario: 执行中

- **WHEN** 用户触发任务执行
- **THEN** 状态变为 `running`，完成后变为 `success` 或 `failed`

### Requirement: 手动触发执行

MVP 阶段系统 SHALL 支持通过 API 手动触发发布，不要求定时调度。

#### Scenario: 手动执行

- **WHEN** 用户调用 `POST /api/publish-tasks/{id}/execute` 且任务为 `pending`
- **THEN** 系统启动 Upload Worker 执行发布，异步更新状态与日志

#### Scenario: 重复执行防护

- **WHEN** 任务已处于 `running` 状态
- **THEN** 系统返回 409 冲突，不启动第二个 Worker

### Requirement: 失败重试

系统 SHALL 支持对失败任务发起重试。

#### Scenario: 重试失败任务

- **WHEN** 用户调用 `POST /api/publish-tasks/{id}/retry` 且任务为 `failed`
- **THEN** 任务状态变为 `pending`，可再次 execute

### Requirement: 发布日志查询

系统 SHALL 提供任务级执行日志查询。

#### Scenario: 查看任务日志

- **WHEN** 用户调用 `GET /api/publish-tasks/{id}/logs`
- **THEN** 系统按时间顺序返回该任务所有 `publish_task_logs` 记录

### Requirement: 计划发布时间字段预留

任务 MUST 包含 `publish_time` 字段；MVP 不实现自动调度，但字段 MUST 可写入和查询。

#### Scenario: 写入计划时间

- **WHEN** 用户创建任务时设置 `publish_time`
- **THEN** 系统保存该字段；MVP 阶段不会自动触发，仅作展示与后续 Celery 扩展
