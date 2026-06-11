# 阶段 D — 服务器端风控（D.4 暂缓）

> 规格：`spec.md`、`design.md`  
> **D.4 本机 Worker 本清单不做**；试运行后再决策  
> **D.1 人工审核** 已由 E.2 完成，不重复

---

## 推荐实施顺序

```
D.2 敏感词  →  D.3 限频/并发  →  D.O 可观测  →  D.5 图片审核（可并行靠后）
         ↘ 试运行 2～4 周 ↙
              评估是否启动 D.4
```

---

## 阶段 D.2 — 敏感词检测（P0，建议先做）

### 后端专家

- [x] D.2.1 `sensitive_words` 表或 `system_configs` 词库存储 + migration + `init_db.sql`
- [x] D.2.2 `SensitiveWordService`：加载、匹配（title/content/tags/cover_text/comment_guide）
- [x] D.2.3 API：`GET/POST/DELETE /api/risk/sensitive-words`（或并入 system configs）
- [x] D.2.4 接入点：`PublishService.submit_task`、`assert_can_execute`、创建/更新任务校验
- [x] D.2.5 配置项：`sensitive_word_enabled`、`sensitive_word_action`（block/warn）
- [x] D.2.6 命中写 `publish_task_logs`（step=`sensitive_word`）
- [x] D.2.7 权限：复用 `settings:write`

### 前端专家

- [x] D.2.8 系统设置 —「敏感词管理」：列表、新增、删除、批量粘贴导入
- [x] D.2.9 发布向导/任务页：机审失败展示命中摘要
- [x] D.2.10 开关与 `block/warn` 模式配置项

### 文档与验证

- [x] D.2.11 `daily-usage.md` 补充敏感词与拦截说明
- [x] D.2.12 验证：含敏感词任务无法 submit；关闭开关后可通过

---

## 阶段 D.3 — 发布频率与并发限制（P0）

### 后端专家

- [ ] D.3.1 `system_configs` 增加限频相关配置（见 design.md）
- [ ] D.3.2 `RateLimitService`：账号间隔、日上限、全局并发查询
- [ ] D.3.3 接入 `execute_task`、`publish_tasks.execute` API、`schedule_worker.poll_due_tasks`
- [ ] D.3.4 自动重试 `poll_auto_retries` 执行前限频检查（尊重 `rate_limit_include_retry`）
- [ ] D.3.5 限频拒绝写 `publish_task_logs`（step=`rate_limit`），任务保持 `pending`
- [ ] D.3.6 确认 `publish_tasks` 查询索引满足限频性能（或补充索引 migration）

### 前端专家

- [ ] D.3.7 系统设置 — 发布限频：间隔、日上限、最大并发、重试是否计入
- [ ] D.3.8 任务执行失败/拒绝时展示限频原因（区分 failed 与 pending 被限）

### 文档与验证

- [ ] D.3.9 `deployment.md` 补充「低频次发布」运维建议
- [ ] D.3.10 验证：短间隔二次 execute 被拒；日上限后次日可发；并发=1 时第二个任务排队

---

## 阶段 D.O — 风控可观测（P1，支撑 D.4 决策）

### 后端专家

- [ ] D.O.1 Dashboard API 扩展：`risk_stats`（敏感词拦截、限频拦截、疑似风控失败计数）
- [ ] D.O.2 失败任务关键词归类（风控 / 技术 / 其他）

### 前端专家

- [ ] D.O.3 工作台展示风控统计卡片或告警提示

### 文档

- [ ] D.O.4 新增 `docs/phase-d-trial-guide.md`：试运行周期、记录表、D.4 评估 checklist
- [ ] D.O.5 更新 `project-overview.md` 路线图（D.4 暂缓说明）

---

## 阶段 D.5 — 图片内容审核（P2，可后置）

### 后端专家

- [ ] D.5.1 `materials` 表增加 `moderation_status`、`moderation_detail` + migration
- [ ] D.5.2 `ImageModerationProvider` 抽象 + `stub` 实现
- [ ] D.5.3 配置：`image_moderation_enabled`、云 API Key（可选）
- [ ] D.5.4 接入 `upload_material`、文生图入库、`submit_task` 前校验
- [ ] D.5.5 （可选）腾讯云/阿里云内容安全 Adapter 其一

### 前端专家

- [ ] D.5.6 系统设置 — 图片审核开关与 Provider 配置
- [ ] D.5.7 素材库展示 `moderation_status`；未通过素材不可选入发布任务

### 文档与验证

- [ ] D.5.8 `daily-usage.md` 图片审核说明
- [ ] D.5.9 验证：开启后违规图标记 rejected；关闭后与现网一致

---

## 阶段 D.4 — 本机发布 Worker（暂缓，不在本 change）

- [ ] D.4.1 ~~本机 Worker 进程~~ → **暂缓**；触发条件见 `design.md`
- [ ] D.4.2 试运行结束后根据 `phase-d-trial-guide.md` 决策是否单独立项

---

## 完成判定（Hard Gates）

- 任务勾选 `[x]` 前须：代码可运行 + 关键路径自检 + 无新增明显静态错误
- 涉及新表/字段须同步 `init_db.sql` 与 `migrations.py`
- 风控开关全部关闭时，现有发布 E2E 仍可通过
- D.4 未做 **不阻塞** 本 change 完成声明

---

## 试运行建议（给用户）

1. 部署 D.2 + D.3 后，开启 `require_content_review` + 保守限频（如间隔 5min、日 5 条）
2. 跑 2～4 周，按 `phase-d-trial-guide.md` 每周记录失败率与账号健康
3. 若风控类失败仍高 → 评估 D.4；若稳定 → 维持服务器执行方案
