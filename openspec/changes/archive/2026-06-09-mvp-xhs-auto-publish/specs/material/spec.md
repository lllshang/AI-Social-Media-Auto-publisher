## ADDED Requirements

### Requirement: 素材上传

系统 SHALL 支持上传视频、图片文件并入库到素材中心。

#### Scenario: 上传图片

- **WHEN** 用户调用 `POST /api/materials/upload` 并提交图片文件
- **THEN** 系统通过 StorageAdapter 保存文件，创建 `materials` 记录，返回 `material_id` 和访问 URL

#### Scenario: 上传视频

- **WHEN** 用户上传视频文件
- **THEN** 系统保存文件并生成缩略图占位（MVP 可为空），记录 `type=video`

### Requirement: AI 生成图自动入库

AI 文生图产出的图片 MUST 自动创建素材记录，无需用户二次上传。

#### Scenario: 文生图入库

- **WHEN** `AiImageAdapter` 成功生成图片
- **THEN** 系统自动创建 `materials` 记录，`source=ai_generated`，关联对应 `ai_generation_records.id`

### Requirement: 素材与发布任务关联

发布任务 MUST 能够引用一个或多个素材 ID（封面图、配图、视频）。

#### Scenario: 创建任务绑定素材

- **WHEN** 用户创建发布任务并指定 `material_ids[]`
- **THEN** 系统校验素材存在且类型匹配，任务记录保存素材关联

#### Scenario: 素材不存在

- **WHEN** 用户指定不存在的 `material_id`
- **THEN** 系统返回 404 错误，不创建任务

### Requirement: 存储扩展预留

文件存储 MUST 通过 `StorageAdapter` 抽象，MVP 使用本地目录，后续可切换对象存储。

#### Scenario: 本地存储

- **WHEN** `STORAGE=local`
- **THEN** 文件保存在配置的 `STORAGE_LOCAL_PATH` 目录，URL 通过 API 静态路由或路径返回

#### Scenario: 切换 COS

- **WHEN** 后续设置 `STORAGE=cos` 并实现 `CosStorageAdapter`
- **THEN** 新上传文件走 COS，已有 local 素材仍可通过原 URL 访问（迁移策略留后续 change）
