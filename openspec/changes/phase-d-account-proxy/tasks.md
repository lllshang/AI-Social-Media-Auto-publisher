# 阶段 D.4.1 — 每账号发布代理（方案 1）

> 依赖：现有多平台 Adapter、扫码登录、D.3 限频（建议保持开启）

## 后端专家

- [ ] D.4.1.1 `platform_accounts.publish_proxy` 字段 + SQL 迁移
- [ ] D.4.1.2 `proxy_utils.py`：URL 解析 → Playwright proxy dict / biliup `-p` 字符串
- [ ] D.4.1.3 `PlatformAccountService`：读写、脱敏、resolve_proxy
- [ ] D.4.1.4 Playwright 平台：login + publish 注入 proxy（xhs/douyin/kuaishou/channels vendor 或 Adapter 层）
- [ ] D.4.1.5 B站：bilibili login / renew / upload 传 `-p`
- [ ] D.4.1.6 API：账号更新接口 + 响应脱敏
- [ ] D.4.1.7 （可选二期）`test-proxy` 回显出口 IP

## 前端专家

- [ ] D.4.1.8 账号编辑：「网络线路（选填）」+ 帮助文案
- [ ] D.4.1.9 账号列表：已配置线路标识（不显示密码）

## 文档

- [ ] D.4.1.10 `daily-usage.md`、`deployment.md`：代理配置步骤（客户向服务商索取线路）
- [ ] D.4.1.11 `phase-d-trial-guide.md`：补充「方案1 代理」与 D.4 本机 Worker 对比

## 验证

- [ ] D.4.1.12 未配置代理：现有 E2E / 扫码回归通过
- [ ] D.4.1.13 配置代理后：至少 1 个 Playwright 平台 + B 站 login 链路冒烟（需测试代理）

## 完成判定

- 登录与发布共用同一 `publish_proxy`
- 前端无 Cookie/CLI 必填流程（B 站已网页扫码）
- 任务勾选 `[x]` 前须代码可运行 + 关键路径自检
