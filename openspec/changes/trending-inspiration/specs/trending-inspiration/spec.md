# Trending Inspiration

## Purpose

Provide daily content inspiration by aggregating Bilibili and Douyin hot topics and popular video metadata (no download), with optional AI recommendations and one-click handoff to the publish wizard—without altering existing publish, account, or adapter behavior.

## ADDED Requirements

### Requirement: 热点总开关

系统 SHALL 通过 `trending_enabled` 系统配置控制热点模块；默认 MUST 为 `false`。

#### Scenario: 开关关闭时无副作用

- **WHEN** `trending_enabled=false`
- **THEN** 系统 MUST NOT 注册热点定时抓取任务；现有发布、账号、素材、审核 API 行为与合入本 change 前一致

#### Scenario: 开关开启后可用

- **WHEN** 管理员在系统设置将 `trending_enabled` 设为 `true` 并保存
- **THEN** 侧栏展示「热点灵感」入口；允许手动与定时抓取（受抓取模式约束）

### Requirement: B 站与抖音热点抓取

系统 SHALL 支持从 B 站、抖音抓取热点话题及热门视频元数据（标题、标签、热度、外链、封面 URL），MUST NOT 下载视频文件。

#### Scenario: 每日抓取成功

- **WHEN** 到达配置的抓取时间或管理员调用 `POST /api/trending/fetch`
- **THEN** 系统写入当日 `snapshot_date` 的快照记录至 `trending_items`，并记录 `trending_fetch_runs` 状态为 `success` 或 `partial`

#### Scenario: 抓取失败不阻塞核心功能

- **WHEN** 全部数据源失败且无可用的历史缓存
- **THEN** 热点 API 返回空列表或带 `stale=true` 的缓存数据；发布、登录等核心 API MUST 不受影响

### Requirement: 滚动周期聚合

系统 SHALL 支持三种查看周期：今日（`daily`）、近 7 天（`rolling_7d`）、近 30 天（`rolling_30d`），后两者为滚动窗口而非自然周/月。

#### Scenario: 近 7 天列表

- **WHEN** 用户请求 `GET /api/trending/items?period=rolling_7d`
- **THEN** 返回过去 7 日内出现过的热点条目，按聚合热度排序

### Requirement: 小游戏关键词筛选

系统 SHALL 支持通过系统配置 `trending_mini_game_keywords`（逗号分隔）对标题与标签进行筛选。

#### Scenario: 小游戏视图

- **WHEN** 用户请求 `GET /api/trending/items?category=mini_game`
- **THEN** 仅返回标题或标签匹配任一关键词的条目

### Requirement: 抓取模式可配置

系统 SHALL 支持 `trending_fetch_mode`：`server`、`local_worker`、`auto`。

#### Scenario: server 模式

- **WHEN** `trending_fetch_mode=server`
- **THEN** 抓取在 API 服务器进程执行，使用免费数据源 Adapter

#### Scenario: local_worker 模式

- **WHEN** `trending_fetch_mode=local_worker` 且存在在线 PublishWorker
- **THEN** 抓取任务派发给 Worker 执行，结果回写服务器数据库

#### Scenario: auto 模式降级

- **WHEN** `trending_fetch_mode=auto` 且 server 抓取失败
- **THEN** 系统尝试派发 Worker；若仍失败且 `trending_paid_api_enabled=true` 则尝试付费 Adapter；否则使用历史缓存

### Requirement: 付费 API 可选兜底

系统 SHALL 通过 `trending_paid_api_enabled` 控制是否启用付费数据源；默认 MUST 为 `false`。

#### Scenario: 付费关闭时不用付费源

- **WHEN** `trending_paid_api_enabled=false`
- **THEN** 抓取流程 MUST NOT 调用 TikHub 等付费 API

#### Scenario: 付费开启需确认

- **WHEN** 用户在系统设置将 `trending_paid_api_enabled` 从 `false` 改为 `true`
- **THEN** 前端 MUST 展示按次计费风险提示并需用户确认后保存

### Requirement: 热点灵感页

管理后台 SHALL 提供热点灵感页面，支持周期 Tab、平台筛选、小游戏筛选、列表展示与最后更新时间。

#### Scenario: 列表展示

- **WHEN** 用户打开热点灵感页
- **THEN** 展示热点条目：排名、标题、平台、热度、标签、持续天数（滚动周期下）

### Requirement: 平台联动创作

系统 SHALL 支持从热点条目一键进入发布向导，并预填与热点来源一致的平台与主题。

#### Scenario: 抖音热点创作

- **WHEN** 用户在抖音热点条目点击「创作」
- **THEN** 跳转至 `/publish?topic={title}&platform=douyin&content_type=video`，发布向导预填对应字段

#### Scenario: B 站热点创作

- **WHEN** 用户在 B 站热点条目点击「创作」
- **THEN** 跳转至 `/publish?topic={title}&platform=bilibili&content_type=video`

### Requirement: 按需 AI 推荐今日选题

系统 SHALL 提供 `POST /api/trending/ai-recommend`，仅在用户主动触发时调用现有文案模型生成推荐选题。

#### Scenario: AI 推荐成功

- **WHEN** 用户点击「AI 推荐今日选题」且文案模型已配置
- **THEN** 返回 3～5 条推荐，每条含 `topic`、`platform`、`content_type`、`reason`；用户可点击「用这个创作」跳转发布向导

#### Scenario: 文案模型未配置

- **WHEN** 文案模型未配置或为 stub
- **THEN** 返回明确错误提示；热榜列表仍正常展示

#### Scenario: 不自动调用 AI

- **WHEN** 定时抓取完成
- **THEN** 系统 MUST NOT 自动调用 AI 推荐接口

### Requirement: 存为内容模板

系统 SHALL 支持将热点条目保存为内容模板，预填 `topic`、`platform`、`content_type`。

#### Scenario: 存模板

- **WHEN** 用户在某热点条目点击「存为模板」
- **THEN** 创建 `ContentTemplate` 记录，用户可在发布向导模板下拉中选择

### Requirement: 扩展字段预留

`trending_items` MUST 包含可空的 `video_url`、`duration_seconds`、`aspect_ratio`、`ref_material_id` 字段，第一期可不写入，供后续下载与加工 change 使用。

#### Scenario: 第一期仅元数据

- **WHEN** 系统完成一次热点抓取
- **THEN** 写入记录的 `video_url`、`ref_material_id` 等预留字段 MAY 为空；列表与创作功能不依赖这些字段

## MODIFIED Requirements

### Requirement: 发布向导 query 预填（publish-wizard）

发布向导 SHALL 支持从 URL query 读取 `topic`、`platform`、`content_type` 并预填表单，且 MUST NOT 改变现有草稿加载、步骤流转与提交逻辑。

#### Scenario: 从热点页跳转

- **WHEN** 用户带 `?topic=xxx&platform=douyin&content_type=video` 进入发布向导
- **THEN** 对应表单项预填；用户仍须完成后续步骤并手动提交

### Requirement: 系统设置热点区块（system-config）

系统设置 SHALL 新增热点相关配置项的可视化编辑，风格与现有布尔/下拉配置一致。

#### Scenario: 保存热点配置

- **WHEN** 管理员修改 `trending_*` 配置并保存
- **THEN** 立即生效；下次调度与抓取使用新配置

## 隔离约束（Normative）

- 本能力 MUST NOT 修改 `PlatformAdapter` 实现文件（`xhs.py`、`douyin.py`、`kuaishou.py`、`channels.py`、`bilibili.py`）的登录与发布逻辑。
- 本能力 MUST NOT 修改 `upload_worker` 发布执行路径。
- `trending_enabled=false` 时，合入方 MUST 能通过现有 E2E 冒烟（账号登录 + 任务创建 + 执行）而无行为变化。
