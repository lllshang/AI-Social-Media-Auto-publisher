# Platform Account

## Purpose

Manage platform accounts, login sessions, and encrypted cookie storage.

## Requirements

### Requirement: 平台账号 CRUD

系统 SHALL 支持创建、查询、更新、禁用平台账号，每个账号 MUST 关联唯一平台标识（MVP 支持 `xhs`）。

#### Scenario: 创建小红书账号

- **WHEN** 用户提交 `platform=xhs` 和 `account_name`
- **THEN** 系统创建账号记录并返回 `account_id`，初始状态为 `inactive`

#### Scenario: 查询账号列表

- **WHEN** 用户请求 `GET /api/platform-accounts?platform=xhs`
- **THEN** 系统返回该平台下所有账号及状态、分组信息

### Requirement: 扫码登录与 Cookie 保存

系统 SHALL 为指定账号启动浏览器登录流程，并在登录成功后加密保存 Cookie。

#### Scenario: 触发扫码登录

- **WHEN** 用户调用 `POST /api/platform-accounts/{id}/login`
- **THEN** 系统启动 Playwright 打开小红书创作者登录页，等待用户扫码完成

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

### Requirement: Cookie 安全存储

系统 MUST 对 Cookie 数据进行 AES 加密后存储，加密密钥 MUST 来自环境变量 `COOKIE_ENCRYPTION_KEY`。

#### Scenario: 存储加密

- **WHEN** 系统保存 Cookie
- **THEN** 数据库中 MUST NOT 出现明文 Cookie 字段

#### Scenario: 读取解密

- **WHEN** 发布 Worker 需要 Cookie 执行上传
- **THEN** 系统在内存中解密后传递给 PlatformAdapter，解密后的明文 MUST NOT 写入日志
