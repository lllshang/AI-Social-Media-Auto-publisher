## 1. 规格与隔离基线（全员）

- [ ] 1.1 创建分支 `feature/trending-inspiration`（从当前主开发分支拉出）
- [ ] 1.2 阅读 `proposal.md`、`design.md`；PR 自查禁止改动 `PlatformAdapter` 发布链与 `upload_worker` 发布逻辑
- [ ] 1.3 确认 `trending_enabled` 默认 `false` 的合入策略（现网升级后默认不启用新功能）

## 2. 后端专家 — 数据层与配置

- [ ] 2.1 新增 DDL：`trending_fetch_runs`、`trending_items`（含预留字段 `video_url`、`ref_material_id` 等），更新 `scripts/init_db.sql`
- [ ] 2.2 新增 SQLAlchemy 模型与 Pydantic schema
- [ ] 2.3 `system_config_service.ensure_default_system_configs` 追加 `trending_*` 默认值（`trending_enabled=false`，`trending_paid_api_enabled=false`）
- [ ] 2.4 实现 `TrendingConfigService` 读取配置（封装 bool/int/关键词列表）

## 3. 后端专家 — 抓取 Adapter 链

- [ ] 3.1 实现 `TrendingSourceAdapter` 基类与 `FreeDailyHotAdapter`（bilibili、douyin）
- [ ] 3.2 实现 `PaidTikHubAdapter`（仅 `trending_paid_api_enabled=true` 时调用）
- [ ] 3.3 实现 `TrendingFetchService`：去重入库、写入 `trending_fetch_runs`、失败缓存策略
- [ ] 3.4 实现 `auto` 降级链：server → worker → paid（可选）→ stale cache
- [ ] 3.5 `schedule_worker` 增量：仅 `trending_enabled=true` 时注册每日抓取 job（**不修改**现有 publish/retry/cleanup job 逻辑）

## 4. 后端专家 — 查询、AI 与 API

- [ ] 4.1 实现 `TrendingQueryService`：`daily` / `rolling_7d` / `rolling_30d` 聚合与 `mini_game` 筛选
- [ ] 4.2 新增 prompt `templates/prompts/trending_recommend.yaml` 与 `TrendingAiRecommendService`（复用 `AiModelService`）
- [ ] 4.3 新增 `api/trending.py`：`GET /items`、`POST /fetch`、`POST /ai-recommend`、`GET /status`
- [ ] 4.4 实现「存为模板」：`POST /api/trending/items/{id}/save-template` → `ContentTemplateService`
- [ ] 4.5 `main.py` 注册 router；权限：`trending:read` / `trending:write`（或合入 RBAC 默认给 admin）

## 5. 后端专家 — Worker 抓取（可选路径）

- [ ] 5.1 Worker 新增热点抓取任务轮询/执行（独立队列，**不共用**发布 execute 队列）
- [ ] 5.2 `LocalScrapeAdapter` 或 HTTP 回传抓取结果 API
- [ ] 5.3 `trending_fetch_mode=local_worker|auto` 时派发逻辑与在线 Worker 检测

## 6. 前端专家 — 热点灵感页

- [ ] 6.1 新增 `TrendingView.vue`：周期 Tab、平台筛选、小游戏筛选、列表、最后更新时间
- [ ] 6.2 操作按钮：「创作」（平台联动 query）、「存为模板」、「AI 推荐今日选题」
- [ ] 6.3 路由 `/trending`、侧栏菜单（`trending_enabled` 或权限控制显示）
- [ ] 6.4 `api/index.js` 新增 trending 相关接口

## 7. 前端专家 — 设置与发布向导微改

- [ ] 7.1 `SettingsView.vue` 新增「热点抓取」卡片：`trending_enabled`、`fetch_mode`、cron hour、关键词、付费开关与 API Key
- [ ] 7.2 开启 `trending_paid_api_enabled` 时计费确认弹窗（对齐图片审核交互）
- [ ] 7.3 `PublishView.vue`：解析 URL query `topic`/`platform`/`content_type` 预填（**不改变**现有草稿/提交流程）

## 8. 隔离回归（全员 — 合入门禁）

- [ ] 8.1 **`trending_enabled=false`**：小红书/抖音/快手/B 站各 1 次登录 + 发布（或 execute）冒烟通过
- [ ] 8.2 **`trending_enabled=false`**：AI 文案、文生图、素材上传、审核、定时发布、Worker 发布无回归
- [ ] 8.3 **`trending_enabled=true`**：手动 `POST /fetch` 成功写入数据；列表三种周期正确
- [ ] 8.4 平台联动：抖音/B 站热点「创作」跳转发布向导字段正确
- [ ] 8.5 AI 推荐：已配置文案模型时返回推荐；未配置时友好错误
- [ ] 8.6 付费开关：`trending_paid_api_enabled=false` 时日志/网络无 TikHub 请求
- [ ] 8.7 PR diff 白名单：无 `xhs/douyin/kuaishou/channels/bilibili` Adapter 逻辑变更、无 `upload_worker` 发布路径变更

## 9. 文档与部署

- [ ] 9.1 `docs/daily-usage.md` 补充：热点模块开启步骤、DailyHotApi 自建说明、付费 API 可选说明
- [ ] 9.2 `docker-compose.yml` 提供 DailyHotApi 侧车 **注释示例**（默认不启用）
- [ ] 9.3 运行 `openspec change validate trending-inspiration`
