## Context

- 现有主链路：手动主题 → AI 文案 → 素材 → 发布任务 → 各平台 Adapter（Playwright / biliup）。
- 已有 `APScheduler`（`schedule_worker.py`）负责定时发布、自动重试、素材清理；可**增量**注册热点抓取 job，且仅在 `trending_enabled=true` 时生效。
- 已有 `PublishWorker` 本机心跳与任务认领模式（B 站发布已验证）；热点抓取可复用「服务器派发 / 本机执行」模式，但**与发布队列隔离**（独立 Redis key 或 DB 任务表）。
- 已有 `SystemConfig` + `SettingsView` 开关模式（参考 `image_moderation_enabled`）；付费热点 API 沿用「默认关 + 开启确认 + 密钥区」交互。
- 用户明确要求：**不影响目前正常使用的功能**。

## Goals / Non-Goals

**Goals:**

- 新增独立「热点灵感」能力域，默认可通过 `trending_enabled` 总开关关闭，关闭时零运行时开销
- B 站 + 抖音热点：日快照 + 近 7/30 天滚动聚合 + 小游戏关键词筛选
- 平台联动：抖音热点 → 创作默认 `platform=douyin`；B 站同理
- 按需 AI 推荐今日选题（复用 `AiModelService.get_text_adapter()`，不新增厂商）
- 抓取：免费优先（DailyHotApi 自建 / 本机抓取）；付费 API（如 TikHub）仅在 `trending_paid_api_enabled=true` 时作兜底
- 表结构预留 `video_url`、`ref_material_id` 等字段，供后期下载/加工 change 使用

**Non-Goals:**

- 视频下载、ffmpeg 加工
- 改动现有 PlatformAdapter、发布状态机、审核、敏感词
- 默认开启付费 API
- 热点抓取失败时阻塞或影响发布/登录等核心 API

## Decisions

### 1. 模块隔离（首要）

- **决策**：热点能力以**纯增量**交付：
  - 新表：`trending_fetch_runs`、`trending_items`
  - 新 API 前缀：`/api/trending/*`
  - 新前端页：`/trending`
  - **不修改** `upload_worker`、`publish_service` 执行链、`PlatformAdapter` 实现
- **理由**：满足「不影响现有功能」；故障域隔离，热点挂了不影响发布。
- **PublishView 唯一触点**：读取 URL query `topic` / `platform` / `content_type` 预填表单（与现有草稿加载逻辑并列，不覆盖已有行为）。

### 2. 总开关与默认可关闭

- **决策**：`trending_enabled` 默认 `false`；运维显式开启后才注册调度、展示侧栏、执行抓取。
- **理由**：新功能默认不扰动现网；与 `BILIBILI_ENABLED` 策略一致。
- **备选**：默认 `true` —— 拒绝，避免未配置数据源时产生无意义调度与 UI 噪音。

### 3. 数据源 Adapter 链

```
TrendingFetchService
    │
    ├─ FreeDailyHotAdapter     → GET dailyhot /bilibili, /douyin（自建或内网侧车）
    ├─ LocalScrapeAdapter      → 本机 Worker Playwright/HTTP 轻量抓取（可选）
    └─ PaidTikHubAdapter       → 仅 trending_paid_api_enabled=true 且前述失败时
```

- **决策**：`trending_fetch_mode`：
  - `server`：仅 FreeDailyHot（+ Paid 兜底若开启）
  - `local_worker`：仅派发给在线 Worker
  - `auto`：server 先试 → 失败派 Worker → 再失败 Paid（若开启）→ 仍失败用缓存
- **理由**：免费优先；高风险抓取可走本机 IP；付费可控。

### 4. 滚动聚合（非自然周月）

- **决策**：
  - `daily`：每次抓取写入 `snapshot_date=当天` 的快照行
  - `rolling_7d` / `rolling_30d`：查询窗口 `[today-7, today]` / `[today-30, today]`，按 `heat_score` 聚合（出现天数 × 排名权重）
- **理由**：与用户确认的「近 7/30 天」一致；实现简单，无需日历边界逻辑。

### 5. 小游戏筛选

- **决策**：全量入库后，用 `trending_mini_game_keywords`（逗号分隔，系统配置）对 `title` + `tags` 做子串匹配；前端「小游戏」Tab 为过滤视图，非独立数据源。
- **理由**：避免维护独立爬虫；关键词可运营配置。

### 6. AI 推荐（按需）

- **决策**：
  - API：`POST /api/trending/ai-recommend`，body 含 `period`、`platform` 过滤、`limit`
  - 使用专用 prompt 模板 `templates/prompts/trending_recommend.yaml`
  - 输出 JSON：`recommendations[]` 含 `topic`、`platform`、`content_type`、`reason`、`reference_trend_ids`
  - **不**在定时抓取后自动调用 AI
- **理由**：控制成本；用户明确「可以」但非每次自动。

### 7. 平台联动

- **决策**：
  - `trending_items.platform` ∈ `douyin` | `bilibili`
  - 「创作」跳转：`/publish?topic={title}&platform={platform}&content_type=video`
  - AI 推荐结果同理携带 `platform`
- **理由**：抖音/B 站热点与发布平台一一对应；视频为默认内容类型。

### 8. 付费 API 设置

- **决策**：配置项（`system_configs`）：

| key | 默认 | 说明 |
|-----|------|------|
| `trending_enabled` | `false` | 总开关 |
| `trending_fetch_mode` | `auto` | server / local_worker / auto |
| `trending_fetch_cron_hour` | `8` | 每日抓取小时（本地时区 UTC+8 或配置化） |
| `trending_mini_game_keywords` | `小游戏,手游,休闲游戏,试玩` | 筛选词 |
| `trending_paid_api_enabled` | `false` | 付费兜底 |
| `trending_paid_provider` | `tikhub` | 目前仅 tikhub |
| `trending_paid_api_key` | `` | 加密存储（复用 `encrypt_text`） |

- 开启 `trending_paid_api_enabled` 时前端 MUST 弹确认（参考图片审核计费提示）。
- **理由**：用户要求设置里可选开关；默认零付费风险。

### 9. 本机 Worker 扩展（隔离队列）

- **决策**：Worker 新增命令 `fetch-trending`（或 HTTP 轮询 `/api/trending/worker/jobs`），与发布任务**不同队列**。
- Worker 环境变量不强制变更；仍用现有 `worker.env` Token。
- **理由**：复用认证与心跳，不污染 `publish_task` Redis 队列。

### 10. 数据模型（预留扩展）

**`trending_fetch_runs`**

| 字段 | 说明 |
|------|------|
| id | PK |
| source | dailyhot / local_scrape / tikhub |
| mode | server / local_worker |
| status | success / partial / failed |
| item_count | 写入条数 |
| error_message | 可空 |
| started_at / finished_at | |

**`trending_items`**

| 字段 | 说明 |
|------|------|
| id | PK |
| platform | douyin / bilibili |
| snapshot_date | 抓取日 |
| rank | 榜单位置 |
| title | 话题/标题 |
| tags | JSON 数组 |
| heat_score | 数值热度 |
| source_url | 外链（不下载） |
| cover_url | 可空 |
| video_url | 可空，**预留** |
| duration_seconds | 可空，**预留** |
| aspect_ratio | 可空，**预留** |
| ref_material_id | 可空，**预留** |
| first_seen_at / last_seen_at | 滚动聚合用 |
| created_at | |

唯一约束建议：`(platform, snapshot_date, title)` 或加 `source_url` 去重。

## Risks / Trade-offs

| 风险 | 缓解 |
|------|------|
| 免费热榜 API 失效 | auto 模式切 Worker；付费兜底可选；展示上次缓存 + 更新时间 |
| 爬虫违反平台 ToS | 仅元数据、低频（日 1 次）；文档注明合规；不下载视频 |
| 新调度 job 拖慢 API | `trending_enabled=false` 不注册；抓取异步、超时独立 |
| 改动 PublishView 引入回归 | 仅只读 query 预填；合入前跑发布向导全路径回归 |
| 付费 API 误开产生费用 | 默认关 + 确认框 + 设置页说明 |
| AI 推荐 JSON 解析失败 | 降级为展示原始热榜；记录日志，不阻塞页面 |

## Migration Plan

1. 执行 DDL 新增 `trending_*` 表（`init_db.sql` + 迁移脚本）
2. 部署后 `trending_enabled` 保持 `false`，验证现有功能无变化
3. 运维在设置页开启热点、配置抓取模式，手动触发一次 `POST /api/trending/fetch` 验证
4. 开启 AI 推荐前确认文案模型已配置
5. **回滚**：`trending_enabled=false` → 停止调度、隐藏菜单；新表可保留，不影响发布

## Open Questions

- DailyHotApi 是否作为 docker-compose 侧车默认可选？**暂定：文档说明自建方式，compose 提供 commented 示例，不默认拉起。**
- 侧栏菜单权限码：`trending:read` / `trending:write` 是否复用 `publish:read`？**暂定：新增 `trending:read`，管理员默认拥有；抓取触发需 `trending:write` 或 `settings:write`。**
