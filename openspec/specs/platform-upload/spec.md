# Platform Upload

## Purpose

Abstract platform-specific browser automation for content publishing.

## Requirements

### Requirement: 平台发布适配层

系统 SHALL 通过 `PlatformAdapter` 抽象层执行各平台发布，业务层 MUST NOT 直接调用 Playwright API。

#### Scenario: 获取适配器

- **WHEN** 发布任务指定 `platform=xhs`
- **THEN** 系统通过工厂方法返回 `XhsPlatformAdapter` 实例

#### Scenario: 不支持的平台

- **WHEN** 发布任务指定未注册的平台（如 `tiktok`）
- **THEN** 系统返回 400 错误，说明该平台尚未支持

### Requirement: 小红书内容发布

MVP 阶段系统 SHALL 支持通过 `XhsPlatformAdapter` 向小红书创作者后台发布内容（图文或视频，具体类型由 spike 决定，至少支持一种）。

#### Scenario: 图文笔记发布成功

- **WHEN** 发布任务包含有效 Cookie、标题、正文、至少 1 张图片素材
- **THEN** PlatformAdapter 自动完成上传、填表、提交，返回 `success` 及平台侧可见标识（如有）

#### Scenario: 发布失败可定位

- **WHEN** Playwright 在某步骤失败（如元素未找到、上传超时）
- **THEN** 系统记录失败步骤名称与错误信息，任务状态为 `failed`，错误信息 MUST 可供运营人员理解

### Requirement: 发布步骤日志

PlatformAdapter MUST 在每个关键步骤写入 `publish_task_logs`（如 `open_page`、`upload_media`、`fill_title`、`submit`）。

#### Scenario: 步骤级日志

- **WHEN** 发布任务执行中
- **THEN** 每个步骤完成后系统写入一条日志，包含 `step`、`status`、`message`、`created_at`

### Requirement: 平台扩展预留

新增平台 MUST 仅需实现 `PlatformAdapter` 接口并在工厂注册，无需修改 `PublishService` 核心逻辑。

#### Scenario: 注册新平台

- **WHEN** 开发者新增 `DouyinPlatformAdapter` 并在工厂注册 `douyin`
- **THEN** 创建 `platform=douyin` 的发布任务时可路由到该适配器（本 change 不要求实现 douyin）
