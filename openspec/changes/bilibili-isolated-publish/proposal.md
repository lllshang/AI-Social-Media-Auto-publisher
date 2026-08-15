## Why

B 站账号与发布能力已在代码中实现，但因稳定性问题被 `BILIBILI_ENABLED=false` 默认关闭，前台入口隐藏。产品仍需要支持 B 站视频投稿，且必须在**独立变更/分支**内交付，避免再次影响已稳定运行的小红书、抖音、快手等平台。

## What Changes

- 以 **feature flag**（`BILIBILI_ENABLED`）控制 B 站能力开关，默认仍关闭；运维显式开启后才暴露入口与 Adapter 路由
- 恢复并加固 B 站专属链路：扫码登录（biliup PTY）、Cookie 检测、视频发布（biliup CLI）、分区 `tid` 选择
- 所有代码改动限定在 B 站相关模块（`BilibiliPlatformAdapter`、B 站登录 API 分支、前端 B 站条件渲染），**禁止**修改小红书/抖音/快手 Adapter 的发布与登录逻辑
- 移除或隔离曾影响全局稳定性的逻辑（如 API 启动时 biliup 预热、向非 B 站平台传递 `progress_callback`）
- 增加 B 站与其他平台的**回归验证清单**，合入前必须确认三平台冒烟通过
- 在独立 Git 分支 `feature/bilibili-isolated-publish` 开发与合并；**从 `develop_P0` 拉出、合回 `develop_P0`**，继承已验收的小红书/抖音/快手最新代码

## Capabilities

### New Capabilities

（无——复用现有能力域，通过 delta spec 扩展 B 站要求。）

### Modified Capabilities

- `platform-account`：补充 B 站扫码登录、Cookie 检测的独立要求；明确 B 站登录不走其他平台 Playwright 路径
- `platform-upload`：补充 B 站视频发布（biliup）、分区 tid、失败可定位等要求；明确与其他平台 Adapter 隔离
- `publish-task`：补充 B 站视频任务创建/执行时的 `bilibili_tid` 与 feature flag 约束

## Impact

- **后端**：`config.py`、`adapters/platform/bilibili.py`、`adapters/factory.py`、`api/platform_accounts.py`、`services/platform_account_service.py`
- **前端**：`constants/platforms.js`、`AccountsView.vue`、`PublishView.vue`（仅 B 站条件分支）
- **Vendor**：`vendor/social-auto-upload/uploader/bilibili_uploader/`（登录与 runtime）
- **部署**：`.env` / `.env.docker.example` 增加 `BILIBILI_ENABLED` 说明；Docker 默认可保持 `false`
- **不受影响**：`xhs.py`、`douyin.py`、`kuaishou.py`、`channels.py` 及对应前端流程（仅做回归测试，不做功能改动）
