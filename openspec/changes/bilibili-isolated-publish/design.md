## Context

- B 站能力已通过 `BilibiliPlatformAdapter` + `vendor/bilibili_uploader` 接入，与小红书/抖音/快手的 Playwright 路径**天然分离**（B 站走 biliup CLI + PTY 扫码）。
- 近期因 biliup 启动预热拖慢 API、登录超时、以及 `progress_callback` 误传给快手等共享代码路径，临时将 `BILIBILI_ENABLED` 默认设为 `false` 并隐藏前台入口。
- 用户要求：在**独立分支**恢复 B 站发布，且合入前小红书、抖音、快手功能不得回退。

## Goals / Non-Goals

**Goals:**

- 运维可通过 `BILIBILI_ENABLED=true` 显式开启 B 站，未开启时行为与当前一致（无入口、Adapter 拒绝路由）
- B 站完整链路可用：账号扫码登录 → Cookie 检测 → 视频任务创建（含 tid）→ 本机/服务器 Worker 发布
- 所有改动文件可枚举为「B 站专属」；PR diff 中不出现 xhs/douyin/kuaishou Adapter 逻辑变更
- 提供合入前回归清单（三平台冒烟 + B 站端到端）

**Non-Goals:**

- B 站图文/专栏投稿（仅视频）
- 改造小红书/抖音/快手登录或发布实现
- 默认对全部部署开启 B 站（仍默认 `false`）
- 视频号（channels）能力

## Decisions

### 1. Feature Flag 守门（首选）

- **决策**：继续用 `BILIBILI_ENABLED` 控制后端工厂、runtime API、前端 `platformsForRuntime()`。
- **理由**：零风险默认；生产可按环境单独开启，不影响未启用 B 站的实例。
- **备选**：永久开启并仅靠 UI「实验」标签 —— 拒绝，无法隔离故障域。

### 2. 代码隔离边界

- **决策**：允许改动的模块白名单：
  - `adapters/platform/bilibili.py`
  - `api/platform_accounts.py` 中 `platform == "bilibili"` 分支
  - `services/platform_account_service.py` 中 B 站分支
  - `adapters/factory.py` 仅保留既有 `bilibili_enabled` 判断（不重构工厂）
  - `web` 中 `BILIBILI_PLATFORM`、`AccountsView`/`PublishView` 的 `bilibili` 条件块
  - `vendor/.../bilibili_uploader/*`
- **禁止**：修改 `xhs.py`、`douyin.py`、`kuaishou.py`、`channels.py` 及 `XhsPlatformAdapter` 基类共享逻辑。
- **理由**：用户明确要求不影响已验收平台；B 站已是独立 Adapter 类。

### 3. 登录与发布技术栈保持 biliup

- **决策**：B 站登录继续 `bilibili_cookie_gen`（PTY + 二维码 SSE）；发布继续 `run_biliup_command` 子进程。
- **理由**：与 Playwright 栈解耦，避免牵动其他平台；vendor 已有 `sau bilibili` CLI。
- **约束**：B 站登录**不**走账号 `publish_proxy`（历史决策，避免 biliup 代理复杂度）；其他平台代理逻辑不变。

### 4. 禁止全局副作用

- **决策**：
  - API `main.py` / `lifespan` **不得**在启动时预热 biliup 或下载 GitHub 依赖
  - `progress_callback` **仅**在 `BilibiliPlatformAdapter.login()` 内使用，禁止传入 `douyin`/`kuaishou`/`xhs` 登录调用链
- **理由**：此前快手扫码报错、服务启动卡死的根因。

### 5. Git 分支策略

- **决策**：实现分支名 `feature/bilibili-isolated-publish`，**从 `develop_P0` 拉出**；仅本 change 相关提交；合入前 rebase `develop_P0` 并跑回归，**合并目标为 `develop_P0`**（不直接合 `main`）。
- **理由**：满足用户「一个分支实现 B 站」的交付方式，便于 code review 时一眼识别范围。

### 6. 测试与合入门禁

- **决策**：合入 checklist（手工或脚本）：
  1. `BILIBILI_ENABLED=false`：三平台账号登录/发布冒烟通过；前台无 B 站选项
  2. `BILIBILI_ENABLED=true`：B 站扫码登录、检测 Cookie、创建视频任务、执行发布
  3. 开启 B 站后再测快手/抖音/小红书各 1 次，确认无回归
- **理由**：feature flag 不应改变其他平台代码路径，但需实证。

## Risks / Trade-offs

| 风险 | 缓解 |
|------|------|
| biliup 依赖 GitHub 镜像，网络不稳导致登录慢 | 登录超时文案 + 可重试；依赖下载懒加载于首次 B 站操作，非启动时 |
| B 站扫码长时间无二维码 | PTY 输出解析加固；前端 loading 与 SSE 超时提示（已有基础） |
| 误改共享工具函数影响三平台 | PR 文件白名单 review；禁止改非 B 站 Adapter |
| Docker 服务器无图形环境，B 站登录需本机 Worker | 文档说明：B 站登录/发布推荐本机 Worker；与小红书混合部署一致 |
| `bilibili_enabled=true` 后 API 内存/子进程增加 | 保持懒加载；不设全局 biliup 守护进程 |

## Migration Plan

1. 在 `feature/bilibili-isolated-publish` 分支按 `tasks.md` 实施
2. 开发环境 `.env` 设 `BILIBILI_ENABLED=true` 验证 B 站；生产默认保持 `false`
3. 需要 B 站的生产实例：升级后单独设置环境变量并重启 API
4. **回滚**：设 `BILIBILI_ENABLED=false` 并重启 → 立即恢复当前隐藏行为，无需数据迁移

## Open Questions

- 是否在系统设置页增加「启用 B 站（实验）」开关（写 `bilibili_enabled` 到 DB），还是仅环境变量？**暂定：本 change 仅环境变量**，避免动 system_config 影响面。
- B 站是否必须绑定本机 Worker？**暂定：与小红书一致，可选绑定；未绑定则在服务器执行 biliup（需 Chromium/依赖齐全）。**
