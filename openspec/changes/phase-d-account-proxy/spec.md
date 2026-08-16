# 阶段 D.4.1 — 每账号发布代理（方案 1）

## 用户故事

### US-P1 运营 — 为账号配置独立网络

作为运营，我在编辑平台账号时可填写「网络线路」，使该账号登录和发布使用与其他账号不同的出口 IP，无需懂 Cookie 或服务器。

**验收：**

- 留空时行为与现网一致
- 填写合法代理 URL 并保存成功
- 列表/详情对密码脱敏

### US-P2 客户 — 扫码登录与发布同一线路

作为非技术客户，我扫码登录某账号后，该账号的发布应自动走同一条线路，我不需要额外操作。

**验收：**

- 配置代理后扫码登录成功（或明确失败提示）
- 发布任务日志有 `validate` → `upload` → `submit` 正常或可读错误
- 未出现「登录 IP 与发布 IP 不一致」导致的即时 Cookie 失效（抽检）

### US-P3 运维 — B 站同样支持

作为运维，B 站账号也可配置代理，登录与 biliup 上传均生效。

## 功能需求

### 1. 数据模型

- `platform_accounts.publish_proxy` 可空字符串
- `init_db.sql` + `migrations.py` 幂等迁移

### 2. API

- `PUT /api/platform-accounts/{id}` 接受 `publish_proxy`
- 响应脱敏

### 3. 后端执行

- `PlatformAccountService.resolve_proxy(account) -> dict | None`
- 所有 `Adapter.login` / `Adapter.publish` 传入 proxy
- biliup：`-p` 与 `-u` 同时使用

### 4. 前端

- 账号编辑弹窗增加「网络线路（选填）」
- B 站账号页说明与小红书一致（不再强调本地终端）

## 非功能

- 配置错误时错误信息对客户友好（「网络线路不可用，请检查地址或联系服务商」）
- 不改变未配置代理账号的默认路径
