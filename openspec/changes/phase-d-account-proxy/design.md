## Context

当前 `PlatformAccount` 无网络字段；Playwright `launch` / `new_context` 与 biliup `-p` 均未接入账号级代理。

执行路径：

```
pending 任务 → Redis 队列 → UploadWorker → Adapter.publish(context)
                                              ↑ 需注入 proxy
```

登录路径：

```
扫码登录 → Adapter.login → vendor cookie_gen
                              ↑ 需同一 proxy（与发布一致）
```

## Goals / Non-Goals

**Goals:**

- 运营可为每个账号单独配置代理（留空=走服务器默认出口）
- **登录与发布必须使用同一代理**，避免 Cookie 因 IP 跳变失效
- 对客户展示为「网络线路（选填）」，支持 `http://` / `socks5://` URL
- 与 D.3 限频、D.2 敏感词无冲突

**Non-Goals:**

- 内置代理采购/售卖
- 自动检测代理是否为住宅 IP
- 发布过程实时视频流（仍用现有任务日志）

## Decisions

### D1: 存储 — `platform_accounts.publish_proxy`

| 字段 | 类型 | 说明 |
|------|------|------|
| `publish_proxy` | `VARCHAR(512) NULL` | 完整 URL，如 `http://user:pass@host:port`、`socks5://host:port` |

空值表示不使用代理。密码含特殊字符需 URL 编码（文档说明）。

### D2: Playwright 平台（xhs / douyin / kuaishou / channels）

在 `browser.new_context(proxy=...)` 或 `chromium.launch(proxy=...)` 传入 Playwright 标准结构：

```python
{"server": "http://host:port", "username": "...", "password": "..."}
```

从 URL 解析后注入；**登录与 publish 共用** `resolve_account_proxy(account_id)`。

vendor 层改动点：

- 各 `*_cookie_gen` 增加可选 `proxy` 参数
- `TencentVideo` / 小红书等 upload 路径同样传入

### D3: B站 biliup

`run_biliup_command` 增加代理参数：`["-p", proxy_url, "-u", cookie_file, "login"]`（与 biliup CLI 一致）。

登录（`bilibili_cookie_gen`）与 `upload` / `renew` 均带 `-p`。

### D4: 前端 — 账号编辑

| 表单项 | 客户文案 |
|--------|----------|
| 网络线路 | 「选填。为此账号单独指定网络，与其他账号区分。向服务商索取线路地址后粘贴。」 |
| 占位符 | `http://用户名:密码@地址:端口` 或 `socks5://地址:端口` |

**不展示** Cookie、Playwright、biliup 等术语。

列表页可选展示「已配置线路」标签（不展示明文密码）。

### D5: 安全

- API 返回账号详情时，`publish_proxy` **脱敏**（仅显示 host:port，隐藏 user:pass）
- 操作日志记录 proxy 变更，不记录密码

### D6: 校验（MVP）

- 格式校验：合法 URL scheme
- 可选二期：`POST /accounts/{id}/test-proxy` 用 HEAD 请求或 Playwright 打开 `https://api.ipify.org` 回显出口 IP 给运营确认

## Risks

| 风险 | 缓解 |
|------|------|
| 劣质代理导致登录失败 | 文档建议住宅/独享；测试按钮（二期） |
| 登录未走代理、发布走代理 | 强制 login/publish 共用 resolver |
| vendor 未统一传 proxy | 各 Adapter 清单 + E2E 抽检 |
| 代理费用 | 客户自备；系统不提供 |

## Open Questions

1. 代理是否按平台默认模板（如「茶叶号用 A 线路」）→ MVP 仅 per-account 手工配置
2. 是否支持「账号分组默认代理」→ 二期
