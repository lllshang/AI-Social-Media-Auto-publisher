## Why

多账号集中从**同一服务器 IP** 发布，易触发平台风控（Cookie 失效、限流、发布失败）。客户为非技术用户，不适合手动导入 Cookie 或运维多机拆分。

**方案 1（每账号代理）** 在后台为每个平台账号配置独立 HTTP/SOCKS5 代理，使**登录与发布**共用同一出口 IP，无需客户理解 Cookie 或 IP 原理。

## What Changes

| 项 | 说明 |
|----|------|
| 账号级代理配置 | `platform_accounts` 增加 `publish_proxy`（可选） |
| 登录走代理 | 扫码登录 Playwright / biliup 登录与代理一致 |
| 发布走代理 | 各 Platform Adapter 创建浏览器或 biliup 时传入代理 |
| 管理页 UI | 平台账号编辑：代理地址（可选）、一键检测连通性（可选二期） |
| 文档 | `daily-usage.md`、`deployment.md` 补充代理配置说明 |

## Capabilities

- `account-publish-proxy`：按账号配置、校验、应用发布/登录代理

## Impact

- 后端：账号 CRUD、Adapter、vendor 登录/发布链路
- 前端：账号编辑表单（非技术文案：「网络线路（选填）」）
- 数据库：`platform_accounts.publish_proxy` 或独立配置表

## Non-Goals

- 代理池自动轮换、按地区智能选址（二期）
- 替代合规审核与 D.3 限频
- D.4 本机 Worker 本体（可后续叠加：本机 Chrome + 账号代理）

## 与 D.4 本机 Worker 的关系

| 模式 | 执行位置 | IP 隔离 |
|------|----------|---------|
| 仅方案 1 | 服务器无头 + 每账号代理 | ✅ 每号不同代理 IP |
| 仅 D.4 | 本机 Chrome，无代理 | ⚠️ 多号同本机宽带 IP |
| 方案 1 + D.4 | 本机 Chrome + 每账号代理 | ✅ 最稳（成本高） |

**建议优先级：** 先做方案 1（服务器即可用，客户零额外软件）；试运行后若仍不稳再评估 D.4。
