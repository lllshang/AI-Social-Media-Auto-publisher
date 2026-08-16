# 阶段 D.4 — 本机发布 Worker + 方案 1 代理

## 变更摘要

在服务器托管任务编排的前提下，将**绑定账号**的浏览器发布派发到本机 Worker 执行；每账号可配置独立代理线路（方案 1）。

## 服务端如何知道哪台机器执行

1. **注册**：管理员在「系统设置 → 本机发布 Worker」创建 Worker，获得唯一 **Token**（哈希存库）。
2. **绑定**：账号编辑页选择 `worker_id`；未绑定则仍在服务器执行。
3. **在线**：本机进程用 Token 调 `POST /api/publish-workers/heartbeat`，上报 `hostname`，90 秒内视为在线。
4. **路由**：执行发布时，若账号有 `worker_id`，任务 ID 入 Redis 队列 `ai-publish:queue:worker:{worker_key}`（非服务器默认队列）。
5. **认领**：本机 `local_publish_worker.py` 长轮询 `POST /api/publish-workers/claim`；服务端用 Token 识别 Worker 身份，从**该 Worker 专属队列** `BLPOP` 取任务。
6. **观测**：任务日志写回 `publish_task_logs`（步骤含 `dispatch` / `worker_claim`），前台「发布任务 → 任务日志」不变。

## 与方案 1 组合

本机执行时仍读取账号 `publish_proxy`，登录与发布共用同一线路（Playwright `conf.PLAYWRIGHT_PROXY` / biliup `-p`）。
