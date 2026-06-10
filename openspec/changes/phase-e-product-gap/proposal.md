## Why

阶段 A/B/C 已完成产品文档主链路（AI 生成 → 素材 → 任务 → 队列/定时发布 → Web 后台）。对照 `docs/AI多平台内容自动发布系统产品文档.docx`，除 **阶段 D 风控** 外仍有账号/用户管理细化、审核独立模块、文生图高级参数、多平台验收与扩展、运维监控等待补齐项。

## What Changes

本 change 聚焦 **阶段 E**：在产品文档范围内、**不包含 D 阶段敏感词/频率限制/本机 Worker/图片审核**，分 P1～P3 逐步交付。

## Capabilities

- `user-admin`：用户管理（新增/禁用/改密/角色分配）
- `account-edit`：平台账号编辑与审计完善
- `review-module`：审核管理独立页面（复用现有 approve/reject API）
- `ai-image-advanced`：文生图风格/品牌参数、中英文负面 Prompt
- `platform-e2e`：抖音/快手发布验收
- `platform-extend`：B 站等平台 Adapter（P3）
- `ops-enhance`：失败自动重试、素材清理、监控与 HTTPS 运维

## Impact

- 后端：用户 API、账号 PUT、日志 IP、重试策略、Prompt 响应扩展
- 前端：用户管理页、审核页、文生图/发布向导参数 UI
- 文档：`project-overview.md` 路线图更新
- **不在范围**：阶段 D 全部项（敏感词、频率限制、本机 Worker、图片审核）
