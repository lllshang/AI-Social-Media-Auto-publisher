## ADDED Requirements

### Requirement: B 站视频发布（biliup CLI）

当 `BILIBILI_ENABLED=true` 时，系统 SHALL 通过 `BilibiliPlatformAdapter` 使用 biliup 子进程向 B 站投稿视频，业务层 MUST NOT 为此调用 Playwright。

#### Scenario: 获取 B 站适配器

- **WHEN** 发布任务指定 `platform=bilibili` 且 `BILIBILI_ENABLED=true`
- **THEN** 系统通过工厂返回 `BilibiliPlatformAdapter` 实例

#### Scenario: B 站功能未启用

- **WHEN** 发布任务指定 `platform=bilibili` 且 `BILIBILI_ENABLED=false`
- **THEN** 系统返回 400 错误，说明 B 站功能未启用

#### Scenario: B 站视频发布成功

- **WHEN** 任务包含有效 Cookie、标题、描述、至少 1 个视频素材、有效 `bilibili_tid`
- **THEN** Adapter 调用 biliup 完成上传与投稿，返回 `success`

#### Scenario: B 站仅支持视频

- **WHEN** 用户创建 `platform=bilibili` 且 `content_type=note`（图文）的发布任务
- **THEN** 系统在校验阶段拒绝并提示 B 站仅支持视频投稿

### Requirement: B 站 Adapter 隔离

新增或修改 B 站发布逻辑时，系统 MUST NOT 修改 `XhsPlatformAdapter`、`DouyinPlatformAdapter`、`KuaishouPlatformAdapter` 的实现文件；共享工具函数的改动 MUST 保持对非 B 站平台的入参与行为兼容。

#### Scenario: 三平台发布不受 B 站改动影响

- **WHEN** `BILIBILI_ENABLED=true` 且用户执行 `platform=xhs|douyin|kuaishou` 的发布任务
- **THEN** 系统路由到对应 Adapter，发布步骤与启用 B 站前一致（回归测试通过）

#### Scenario: progress_callback 仅用于 B 站登录

- **WHEN** 系统执行抖音或快手账号扫码登录
- **THEN** 登录调用链 MUST NOT 传入 `progress_callback` 参数（该参数仅 B 站 biliup 登录使用）

## MODIFIED Requirements

### Requirement: 平台发布适配层

系统 SHALL 通过 `PlatformAdapter` 抽象层执行各平台发布，业务层 MUST NOT 直接调用 Playwright API。

#### Scenario: 获取适配器

- **WHEN** 发布任务指定 `platform=xhs`
- **THEN** 系统通过工厂方法返回 `XhsPlatformAdapter` 实例

#### Scenario: 获取 B 站适配器

- **WHEN** 发布任务指定 `platform=bilibili` 且 `BILIBILI_ENABLED=true`
- **THEN** 系统通过工厂方法返回 `BilibiliPlatformAdapter` 实例

#### Scenario: 不支持的平台

- **WHEN** 发布任务指定未注册的平台（如 `tiktok`）
- **THEN** 系统返回 400 错误，说明该平台尚未支持

### Requirement: 平台扩展预留

新增平台 MUST 仅需实现 `PlatformAdapter` 接口并在工厂注册，无需修改 `PublishService` 核心逻辑。

#### Scenario: 注册新平台

- **WHEN** 开发者新增 `DouyinPlatformAdapter` 并在工厂注册 `douyin`
- **THEN** 创建 `platform=douyin` 的发布任务时可路由到该适配器

#### Scenario: B 站注册不侵入 PublishService

- **WHEN** 开发者启用 `BilibiliPlatformAdapter`
- **THEN** 仅需工厂注册与 feature flag；`PublishService.execute` 核心状态机逻辑 MUST NOT 为 B 站添加分支
