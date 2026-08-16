## Why

阶段 A～E 已跑通「AI 生成 → 素材 → 审核 → 服务器队列执行发布」主链路。产品文档中的 **风控 C 方案** 包含五项（审核、敏感词、频率限制、本机 Worker、图片审核），其中 **E.2 已覆盖人工审核**。

本 change 在 **暂不实施 D.4 本机 Worker** 的前提下，先补齐 **D.2 / D.3 / D.5**，用现有 **Redis 队列 + 服务器/Docker Chromium** 执行模式试运行，观测封号、限流、失败率后再决定是否启动 D.4。

## What Changes

| 子项 | 本 change | 说明 |
|------|-----------|------|
| D.1 审核模块 | ✅ 已完成（E.2） | 不重复开发 |
| D.2 敏感词检测 | **交付** | 提交/执行前机审文案 |
| D.3 发布频率与并发 | **交付** | 按账号/平台限频、限并发 |
| D.4 本机 Worker | **暂缓** | 非永久放弃；见 `design.md` 观测指标与触发条件 |
| D.5 图片内容审核 | **交付** | 上传/文生图后机审（可配置开关） |

## Capabilities

- `sensitive-word-filter`：敏感词库管理 + 文案拦截
- `publish-rate-limit`：单账号发布间隔、日上限、全局并发上限
- `image-moderation`：图片素材机审（MVP 可接云 API 或规则占位，须可关闭）
- `risk-observability`：风控相关失败归类、工作台/日志可观测

## Impact

- 后端：`submit_task` / `execute_task` / 素材上传与文生图链路增加校验；`system_configs` 扩展
- 前端：系统设置增加风控配置；任务/审核页展示机审结果
- 文档：`daily-usage.md`、`deployment.md` 补充风控配置与试运行建议
- **执行架构不变**：仍由 API 内置 Consumer 在服务器执行发布

## Non-Goals

- D.4 本机发布 Worker（本 change 不做，留待观测后决策）
- 平台播放/转化/ROI 数据采集（仍 Out of Scope，见 E.7 proposal）
- 绕过平台验证码、批量注册等非合规能力
