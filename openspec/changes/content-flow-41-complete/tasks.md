## 1. 数据库与配置（后端专家）

- [x] 1.1 `publish_tasks` 表新增 `comment_guide TEXT NULL`；更新 `init_db.sql` 与 `migrations.py` 幂等迁移
- [x] 1.2 `config.py` 新增 `require_content_review: bool = False`；`.env.example` 补充说明

## 2. 发布任务 API（后端专家）

- [x] 2.1 `PublishTask` 模型与 Schema 增加 `comment_guide`；列表/详情响应包含 `publish_time`、`comment_guide`
- [x] 2.2 `PublishService` 扩展状态机：`pending_review`、`rejected`、`approved` 流转；`submit_task` 受 `require_content_review` 控制
- [x] 2.3 `execute_task` 拒绝 `draft` / `pending_review` / `rejected`；仅 `pending` 可执行
- [x] 2.4 新增 `PUT /api/publish-tasks/{id}` 更新草稿字段
- [x] 2.5 新增 `POST /api/publish-tasks/{id}/approve` 与 `/reject`（审核预留，无前端页）
- [x] 2.6 任务详情 API 返回关联素材摘要（id/name/url/type）

## 3. AI 文案与文生图（后端专家）

- [x] 3.1 更新 `xhs_text.yaml` 与 Adapter 解析：输出 `comment_guide`；Stub/Tongyi/OpenAI 兼容 Adapter 同步
- [x] 3.2 `POST /api/ai/text/generate` 响应增加 `comment_guide`
- [x] 3.3 文生图服务支持 `cover_text` 参数或 topic 拼接；发布链路默认 `ratio=3:4`、`count=1`

## 4. 发布向导前端（前端专家）

- [x] 4.1 重构 `PublishView.vue` 为 5 步向导（主题账号 → 文案 → 封面 → 素材 → 排期提交）
- [x] 4.2 Step 1 调用文案 API，展示并允许编辑 title/content/tags/cover_text/comment_guide
- [x] 4.3 Step 2 调用 `generateImage`，展示预览，支持重生成与跳过
- [x] 4.4 Step 4 提供 `publish_time` 选择器 + 提示「当前需手动执行」
- [x] 4.5 「保存草稿」→ `createTask(submit=false)`；「提交待发布」→ create/update + submit；**移除** create 后自动 execute
- [x] 4.6 提交成功后跳转 `/tasks`

## 5. 任务与素材页（前端专家）

- [x] 5.1 `TasksView.vue` 展示 `publish_time`、状态中文；详情抽屉展示 `comment_guide`（可复制）
- [x] 5.2 `TasksView.vue` execute 按钮仅 `pending` 可用；`draft` 显示「继续编辑」跳转向导
- [x] 5.3 `MaterialsView.vue` 增加「AI 生成图片」对话框（topic + 生成 + 刷新列表）
- [x] 5.4 `api/index.js` 补充 `updateTask`、`approveTask`、`rejectTask`（如需要）

## 6. 文档与验证

- [x] 6.1 更新 `docs/daily-usage.md`：新发布流程（草稿 → 待发布 → 手动执行）
- [x] 6.2 本地验证：向导全流程 → 任务 pending → 手动 execute → success；草稿保存/继续编辑
- [x] 6.3 构建 `web/dist`；Docker 环境 migration 后冒烟测试

## 7. 明确不在本 change（记录）

- [x] 7.1 审核管理页面、C 方案本机发布 — 后续 change
- [x] 7.2 Celery 定时执行 — 后续 change
- [x] 7.3 RBAC、敏感词、多平台 — 后续 change

## 8. 发布后增量（本会话）

- [x] 8.1 草稿删除：`DELETE /api/publish-tasks/{id}` + 任务列表/发布向导删除按钮
- [x] 8.2 任务操作按钮按状态显示（不可用时隐藏，非 disabled 灰显）
- [x] 8.3 修复 SPA 路由 `/app/tasks` 等子路径 404（`web_admin.py`）
- [x] 8.4 `sync-to-server.sh` 自动构建前端 + `--delete` 清理旧静态资源
- [x] 8.5 待审核任务「通过/驳回」按钮（`pending_review` 状态，API 已有）

## 9. 下一 change 待办（未开始）

- [ ] 9.1 审核管理独立页面（列表筛选、批量审核、审核记录）
- [ ] 9.2 Celery/APScheduler 到点自动执行 `publish_time`
- [ ] 9.3 服务器 Docker 环境小红书扫码登录 + 无头发布完善
- [ ] 9.4 抖音平台 Adapter（见 `docs/multi-platform-roadmap.md` P1）
- [ ] 9.5 RBAC 权限、敏感词检测、数据看板
- [ ] 9.6 已驳回任务支持退回草稿重新编辑
