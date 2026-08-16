## ADDED Requirements

### Requirement: B 站视频任务字段

当 `platform=bilibili` 时，发布任务 MUST 包含 `bilibili_tid`（分区 ID）；未提供时系统 SHALL 使用系统配置 `bilibili_default_tid`（默认 21）。

#### Scenario: 创建 B 站视频任务

- **WHEN** 用户创建 `platform=bilibili`、`content_type=video` 的任务并选择分区 tid
- **THEN** 系统保存 `bilibili_tid` 并在执行时传递给 `BilibiliPlatformAdapter`

#### Scenario: B 站任务缺少视频素材

- **WHEN** 用户创建 B 站任务但未关联视频类型素材
- **THEN** 系统在校验阶段返回 400，提示必须上传视频

### Requirement: B 站任务与功能开关联动

系统 MUST 在 `BILIBILI_ENABLED=false` 时拒绝创建或执行 `platform=bilibili` 的发布任务。

#### Scenario: 开关关闭时拒绝 B 站任务执行

- **WHEN** 用户对历史 B 站任务调用 execute 且当前 `BILIBILI_ENABLED=false`
- **THEN** 系统返回 400，说明 B 站功能未启用；其他平台任务执行不受影响

#### Scenario: 开关开启时可执行 B 站任务

- **WHEN** `BILIBILI_ENABLED=true` 且 B 站任务为 `pending`、账号 Cookie 有效
- **THEN** 用户可正常 execute，任务进入 `running` 或 `dispatching`（绑定 Worker 时）流程

## MODIFIED Requirements

### Requirement: 发布任务创建

系统 SHALL 支持创建发布任务，包含标题、正文、标签、目标平台、目标账号、关联素材及可选计划发布时间。

#### Scenario: 创建草稿任务

- **WHEN** 用户调用 `POST /api/publish-tasks` 提交完整必填字段
- **THEN** 系统创建任务，初始状态为 `draft`，返回 `task_id`

#### Scenario: 创建 B 站视频草稿

- **WHEN** 用户提交 `platform=bilibili`、`content_type=video`、`bilibili_tid` 及视频素材
- **THEN** 系统创建任务并保存 `bilibili_tid`；`BILIBILI_ENABLED=false` 时前台不应提供该创建入口

#### Scenario: 缺少必填字段

- **WHEN** 用户未提供 `platform`、`account_id` 或 `title`
- **THEN** 系统返回 422 校验错误
