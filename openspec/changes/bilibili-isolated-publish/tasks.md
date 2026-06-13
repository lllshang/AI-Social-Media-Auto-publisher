## 1. 分支与环境（全员）

- [x] 1.1 从 `develop_P0` 创建分支：`git checkout develop_P0 && git pull && git checkout -b feature/bilibili-isolated-publish`
- [x] 1.2 在 `.env.example`、`.env.docker.example`、`docs/deployment.md` 补充 `BILIBILI_ENABLED` 说明（默认 `false`，显式 `true` 开启）
- [x] 1.3 确认 API 启动路径无 biliup 预热/全局副作用（`main.py` lifespan 审计）

## 2. 后端专家 — B 站 Adapter 与开关

- [x] 2.1 审计 `adapters/factory.py`：`bilibili_enabled=false` 时返回明确 400，不改动其他平台工厂分支
- [x] 2.2 加固 `adapters/platform/bilibili.py`：登录 `progress_callback` 仅内部使用；发布参数 tid/标签/描述校验
- [x] 2.3 审计 `api/platform_accounts.py` / `platform_account_service.py`：B 站 login/check 走独立分支，`BILIBILI_ENABLED=false` 时 400
- [x] 2.4 确认 `progress_callback` 未传入 xhs/douyin/kuaishou 登录链（回归 `platform_account_service` 调用点）
- [x] 2.5 `publish_service` / `publish_tasks` API：B 站任务校验 `content_type=video` + 视频素材 + `bilibili_tid`；开关关闭时拒绝 execute

## 3. 后端专家 — Vendor biliup

- [x] 3.1 审计 `vendor/.../bilibili_uploader/login.py`：PTY 二维码解析、超时、错误文案
- [x] 3.2 审计 `vendor/.../bilibili_uploader/runtime.py`：biliup 懒加载、GitHub 镜像回退，禁止在 import 时阻塞
- [x] 3.3 本机 Worker 路径验证：`worker_publish_runner` 传递 `bilibili_tid` 与 Cookie 文件正确

## 4. 前端专家 — B 站入口与向导

- [x] 4.1 `constants/platforms.js`：`bilibili_enabled=true` 时展示 B 站；`false` 时与现网一致隐藏
- [x] 4.2 `AccountsView.vue`：B 站扫码 SSE + loading 文案；不影响其他平台登录 UI
- [x] 4.3 `PublishView.vue`：B 站仅视频类型 + 分区 tid 选择；校验与提交字段 `bilibili_tid`
- [x] 4.4 任务列表/详情：B 站任务展示平台、类型、tid（只读展示，不改其他平台列）

## 5. 隔离与回归（全员 — 合入门禁）

- [x] 5.1 **PR 文件白名单自查**：diff 中无 `xhs.py`/`douyin.py`/`kuaishou.py`/`channels.py` 逻辑变更
- [ ] 5.2 `BILIBILI_ENABLED=false` 回归：小红书/抖音/快手各 1 次扫码登录 + 1 次发布（或 execute 冒烟）
- [ ] 5.3 `BILIBILI_ENABLED=true` 端到端：B 站扫码登录 → 检测 Cookie → 创建视频任务 → 执行发布成功
- [ ] 5.4 `BILIBILI_ENABLED=true` 后再测快手/抖音/小红书各 1 次，确认无回归
- [x] 5.5 更新 `docs/daily-usage.md`：B 站开启方式、本机 Worker 建议、已知限制（仅视频、默认关闭）

## 6. 部署与收尾

- [ ] 6.1 开发环境 `.env` 设 `BILIBILI_ENABLED=true` 完成自测；生产默认保持 `false`
- [ ] 6.2 `scripts/sync-to-server.sh` + `upgrade.sh` 验证后，仅在需要 B 站的实例单独开启环境变量
- [x] 6.3 合入 `feature/bilibili-isolated-publish` 前跑 `openspec change validate bilibili-isolated-publish`
