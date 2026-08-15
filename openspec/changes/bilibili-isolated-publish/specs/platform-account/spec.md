## ADDED Requirements

### Requirement: B 站账号扫码登录（biliup PTY）

当 `BILIBILI_ENABLED=true` 时，系统 SHALL 为 `platform=bilibili` 账号提供独立于其他平台的扫码登录流程，使用 biliup PTY 生成二维码并通过 SSE 推送给前端。

#### Scenario: 触发 B 站扫码登录

- **WHEN** 用户调用 `POST /api/platform-accounts/{id}/login` 且账号 `platform=bilibili`
- **THEN** 系统启动 `bilibili_cookie_gen`，不启动 Playwright 浏览器，不调用小红书/抖音/快手登录逻辑

#### Scenario: 二维码推送

- **WHEN** B 站登录流程捕获到二维码数据
- **THEN** 系统通过 SSE 事件 `qrcode` 将二维码 payload 推送给前端，供用户用哔哩哔哩 App 扫码

#### Scenario: B 站登录成功

- **WHEN** 用户在时限内完成扫码且 biliup 返回有效 Cookie
- **THEN** 系统加密保存 Cookie，账号状态更新为 `active`

#### Scenario: B 站登录超时

- **WHEN** 用户在配置时限内未完成扫码
- **THEN** 系统终止流程并返回明确超时错误，账号状态不变为 `active`

### Requirement: B 站功能开关隔离

系统 MUST 在 `BILIBILI_ENABLED=false`（默认）时拒绝 B 站账号登录与检测路由，且 MUST NOT 影响其他平台账号 API。

#### Scenario: 开关关闭时拒绝 B 站登录

- **WHEN** `BILIBILI_ENABLED=false` 且用户对 B 站账号调用 login 或 check-cookie
- **THEN** 系统返回 400 及「B 站功能未启用」类说明，小红书/抖音/快手账号 API 行为不变

#### Scenario: 开关关闭时前台无 B 站入口

- **WHEN** runtime 接口返回 `bilibili_enabled=false`
- **THEN** 发布向导与账号筛选不出现 B 站选项

## MODIFIED Requirements

### Requirement: 扫码登录与 Cookie 保存

系统 SHALL 为指定账号启动浏览器登录流程，并在登录成功后加密保存 Cookie。

#### Scenario: 触发扫码登录

- **WHEN** 用户调用 `POST /api/platform-accounts/{id}/login` 且账号 `platform` 为 `xhs`、`douyin` 或 `kuaishou`
- **THEN** 系统启动 Playwright 打开对应平台创作者登录页，等待用户扫码完成

#### Scenario: 触发 B 站扫码登录

- **WHEN** 用户调用 `POST /api/platform-accounts/{id}/login` 且账号 `platform=bilibili` 且 `BILIBILI_ENABLED=true`
- **THEN** 系统 MUST 走路径「B 站账号扫码登录（biliup PTY）」而非 Playwright

#### Scenario: 登录成功保存 Cookie

- **WHEN** 用户完成扫码且会话有效
- **THEN** 系统将 Cookie 加密写入 `account_cookies` 表，账号状态更新为 `active`

#### Scenario: 登录超时

- **WHEN** 用户在配置时限（默认 120 秒）内未完成扫码
- **THEN** 系统终止登录流程，返回明确超时错误，不写入 Cookie

### Requirement: Cookie 有效性检测

系统 SHALL 提供检测账号 Cookie 是否仍有效的能力。

#### Scenario: Cookie 有效

- **WHEN** 用户调用 `POST /api/platform-accounts/{id}/check-cookie` 且 Cookie 未过期
- **THEN** 系统返回 `valid=true`，账号保持 `active`

#### Scenario: Cookie 失效

- **WHEN** 检测发现 Cookie 已失效或平台返回未登录
- **THEN** 系统返回 `valid=false`，账号状态更新为 `expired`，并提示重新登录

#### Scenario: B 站 Cookie 检测

- **WHEN** 用户对 `platform=bilibili` 账号调用 check-cookie 且 `BILIBILI_ENABLED=true`
- **THEN** 系统 MUST 调用 biliup 检测逻辑，不得复用 Playwright 检测其他平台的代码路径
