## ADDED Requirements

### Requirement: AI 文案生成

系统 SHALL 通过 `AiTextAdapter` 根据主题与目标平台生成标题、正文、标签和封面文案。

#### Scenario: 生成小红书文案

- **WHEN** 用户调用 `POST /api/ai/text/generate`，提交 `topic`、`platform=xhs`
- **THEN** 系统返回 `title`、`content`、`tags[]`、`cover_text`，并写入 `ai_generation_records`

#### Scenario: 切换文案 Provider

- **WHEN** 环境变量 `AI_TEXT_PROVIDER` 设置为已注册的 provider（MVP: `tongyi`）
- **THEN** 系统使用该 provider 的 Adapter 执行生成，无需修改 API 路由代码

### Requirement: AI 文生图

系统 SHALL 通过 `AiImageAdapter` 根据提示词生成封面图或配图，支持指定比例与生成数量。

#### Scenario: 生成小红书封面

- **WHEN** 用户调用 `POST /api/ai/image/generate`，提交 `prompt`、`ratio=3:4`、`count=1`
- **THEN** 系统返回至少 1 张图片 URL（经 StorageAdapter 存储后的地址），并写入 `ai_generation_records`

#### Scenario: 提示词重构

- **WHEN** 用户提交简单描述作为 `topic` 而非完整 prompt
- **THEN** 系统 MUST 先按平台模板重构为结构化 prompt 再调用文生图 API

### Requirement: AI 生成记录

每次 AI 调用 MUST 持久化到 `ai_generation_records`，包含 `type`（text/image）、`provider`、`prompt`、`result_summary`、`cost` 字段（可为占位 0）。

#### Scenario: 记录文案生成

- **WHEN** 文案生成成功
- **THEN** 系统写入一条 type=text 的记录，关联触发用户与输入参数

#### Scenario: 记录文生图

- **WHEN** 文生图成功
- **THEN** 系统写入一条 type=image 的记录，result 包含素材 ID 或 URL 列表

### Requirement: AI Provider 扩展预留

新增 AI 供应商 MUST 仅需实现对应 Adapter 并在工厂注册。

#### Scenario: 注册 OpenAI 文案 Adapter

- **WHEN** 开发者新增 `OpenAiTextAdapter` 并注册 provider `openai`
- **THEN** 设置 `AI_TEXT_PROVIDER=openai` 即可切换（本 change 不要求实现 openai）
