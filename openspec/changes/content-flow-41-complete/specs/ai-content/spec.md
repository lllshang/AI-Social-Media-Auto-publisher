# AI Content Generation (Delta)

## MODIFIED Requirements

### Requirement: AI 文案生成

系统 SHALL 通过 `AiTextAdapter` 根据主题与目标平台生成标题、正文、标签、封面文案和评论引导。

#### Scenario: 生成小红书文案

- **WHEN** 用户调用 `POST /api/ai/text/generate`，提交 `topic`、`platform=xhs`
- **THEN** 系统返回 `title`、`content`、`tags[]`、`cover_text`、`comment_guide`，并写入 `ai_generation_records`

#### Scenario: 切换文案 Provider

- **WHEN** 环境变量或运行时配置指定已注册的 provider（如 `tongyi`、`ollama`、`openai`）
- **THEN** 系统使用该 provider 的 Adapter 执行生成，无需修改 API 路由代码

## ADDED Requirements

### Requirement: 评论引导生成

AI 文案生成 MUST 输出 `comment_guide` 字段，内容为适合该平台笔记的首条评论引导语（50 字以内）。

#### Scenario: 返回评论引导

- **WHEN** AI 文案生成成功
- **THEN** API 响应 JSON 包含非空 `comment_guide`（Adapter 解析失败时可为 topic 摘要占位）

### Requirement: 发布链路文生图参数

发布向导内调用文生图时，系统 MUST 默认使用小红书封面比例 `3:4` 与 `count=1`，并将 `cover_text` 纳入绘图 prompt 上下文。

#### Scenario: 向导内文生图

- **WHEN** 发布向导 Step 2 调用文生图且已存在 `cover_text`
- **THEN** 系统使用「主题 + 封面文案」构造 prompt，比例 `3:4`，生成 1 张图并入库
