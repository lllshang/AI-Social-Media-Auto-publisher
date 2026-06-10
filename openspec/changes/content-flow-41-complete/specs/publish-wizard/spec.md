# Publish Wizard

## Purpose

Provide a multi-step frontend workflow aligned with product document §4.1: topic → AI text → AI image → material binding → schedule → submit to queue.

## ADDED Requirements

### Requirement: 多步发布向导

系统 SHALL 在管理后台提供多步发布向导页面，步骤顺序 MUST 为：主题与账号 → AI 文案 → AI 封面 → 素材确认 → 排期提交。

#### Scenario: 完成向导全流程

- **WHEN** 用户从「一键发布」入口进入并完成全部步骤后点击「提交待发布」
- **THEN** 系统创建或更新发布任务，状态为 `pending`，并跳转至任务列表页，**不**自动触发 execute

#### Scenario: 中途保存草稿

- **WHEN** 用户在任意步骤点击「保存草稿」且已填写标题
- **THEN** 系统创建或更新 `status=draft` 的任务并提示成功，不触发发布执行

### Requirement: AI 文生图步骤

向导 MUST 在文案步骤之后提供 AI 文生图步骤，调用后端文生图 API 并将结果素材自动选中。

#### Scenario: 文生图成功

- **WHEN** 用户在 Step 2 点击「生成封面」且 AI 文生图 Key 已配置
- **THEN** 系统展示生成图片预览，并将对应 `material_id` 加入任务素材列表

#### Scenario: 文生图不可用时可跳过

- **WHEN** 文生图 API 失败或返回 stub 占位图
- **THEN** 向导 MUST 允许用户跳过或改用手动上传图片，不阻塞后续步骤

### Requirement: 计划发布时间选择

向导 MUST 提供可选的 `publish_time` 日期时间选择器。

#### Scenario: 设置计划时间

- **WHEN** 用户选择未来某时刻作为计划发布时间并提交任务
- **THEN** 任务保存 `publish_time`；UI MUST 提示当前版本需手动执行任务（尚未自动调度）

### Requirement: 禁止向导内直接执行发布

发布向导 MUST NOT 在提交时调用 `POST /api/publish-tasks/{id}/execute`。

#### Scenario: 提交后不自动发布

- **WHEN** 用户点击「提交待发布」
- **THEN** 仅调用创建/更新与 submit API，任务停留在 `pending`，由用户在任务列表手动执行
