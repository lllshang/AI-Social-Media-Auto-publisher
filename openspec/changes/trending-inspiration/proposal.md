## Why

运营同学每日需要决定「今天发什么」，目前只能手动想主题再进入发布向导。系统已具备 B 站/抖音发布、AI 文案、内容模板等能力，但缺少**上游选题灵感**层。新增热点抓取与 AI 推荐，可在不改动现有发布链路的前提下，缩短从选题到发布的路径。

## What Changes

本 change 以**增量、隔离**方式新增「热点灵感」模块：

- 抓取 **B 站 + 抖音** 热点（话题与热门视频**元数据**，不下载视频）
- 支持 **今日 / 近 7 天 / 近 30 天**滚动聚合，及「小游戏」关键词筛选
- 新增 **热点灵感** 管理页：列表、筛选、**平台联动**一键创作
- **按需 AI 推荐今日选题**（用户点击触发，复用现有文案模型）
- **系统设置**新增热点配置区：抓取模式（server / local_worker / auto）、付费 API **默认关闭**可手动开启
- 定时抓取挂接现有 `APScheduler`（`trending_enabled=false` 时不注册任务）
- 数据表与 API **全新增**；发布、账号、素材、审核等现有模块**仅只读复用或接收 query 参数**

## Capabilities

### New Capabilities

- `trending-inspiration`：热点抓取、聚合、展示、AI 推荐、平台联动创作、系统配置

### Modified Capabilities

- `publish-wizard`：支持从热点页跳转时通过 query 预填 `topic`、`platform`、`content_type`（**不改变**现有步骤逻辑与提交行为）
- `system-config`：新增 `trending_*` 配置项及设置页展示区块（**不改变**现有配置项语义）

## Impact

- **后端（新增）**：`models/trending_*`、`services/trending_*`、`adapters/trending/*`、`api/trending.py`；`schedule_worker` 增量注册抓取 job
- **后端（微改）**：`system_config_service.ensure_default_system_configs`、`main.py` 注册新 router
- **前端（新增）**：`TrendingView.vue`、路由 `/trending`、侧栏菜单项
- **前端（微改）**：`SettingsView.vue` 热点配置卡片；`PublishView.vue` 读取热点跳转 query（已有 query 逻辑扩展）
- **Worker（可选）**：本机 Worker 新增热点抓取任务类型（`trending_enabled` 且 `fetch_mode` 含 local 时）
- **部署（可选）**：`docker-compose` 可增加 DailyHotApi 侧车（**非必须**，server 模式可选用公共自建镜像）

## Non-Goals（第一期不做）

- 热点视频**下载**入库
- 视频**画中画 / ffmpeg 加工**（见 Future Work）
- 小红书、快手、微博等其他平台热榜
- 修改任何平台 **PlatformAdapter** 登录/发布逻辑
- 修改发布任务状态机、审核流、敏感词、频率限制、图片审核
- 热点数据**强制**走付费 API（付费仅作可选兜底，**默认关闭**）
- 打开热点页即自动调用 AI（仅用户点击「AI 推荐」时调用）

## 隔离与回归要求（合入门禁）

合入前 MUST 验证（`trending_enabled=true` 与 `false` 各测一轮）：

1. 小红书 / 抖音 / 快手 / B 站：账号登录、创建任务、执行发布**无回归**
2. AI 文案 / 文生图、素材上传、审核、定时发布、本机 Worker 发布**无回归**
3. `trending_enabled=false` 时：无热点定时任务、侧栏可隐藏或展示「未启用」；**现有 API 响应与行为与合入前一致**
4. PR diff：**禁止**修改 `xhs.py`、`douyin.py`、`kuaishou.py`、`channels.py`、`bilibili.py` 及对应发布执行链（`upload_worker` 发布路径不变）

## Future Work（后续独立 change）

- `trending-video-ref`：从热点条目下载参考视频 → `materials`（`source=trending_ref`）
- `video-remix`：ffmpeg 画中画/小窗叠加 → 成片入库 → 发布向导
