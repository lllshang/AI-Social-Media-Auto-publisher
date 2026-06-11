# 多平台扩展路线图

MVP 已完成小红书（xhs）图文发布。扩展其他平台遵循同一 Adapter 模式。

## 扩展步骤（每个平台）

1. Spike：验证登录 + 一种内容类型发布
2. 实现 `{Platform}PlatformAdapter`（login / check_cookie / publish）
3. 在 `AdapterFactory.get_platform_adapter` 注册
4. 补充平台专属 prompt 模板（`templates/prompts/`）
5. E2E 验证 + OpenSpec change

## 候选平台

| 平台 | 标识 | Adapter | E2E 脚本 | 验收状态 |
|------|------|---------|----------|----------|
| 小红书 | xhs | ✅ | `e2e_publish.py --platform xhs` | 已验收 |
| 抖音 | douyin | ✅ | `e2e_publish.py --platform douyin` | 脚本就绪，需有效 Cookie 实测 |
| 快手 | kuaishou | ✅ | `e2e_publish.py --platform kuaishou` | 脚本就绪，需有效 Cookie 实测 |
| 视频号 | channels | 待 spike | — | 未开始 |
| B站 | bilibili | 待实现 | — | P3 |

> E2E 脚本支持 `--skip-execute` 仅验证 API 链路；`--cookie` 指定 Cookie JSON 路径。

## 共用能力（无需重复实现）

- AI 文案/文生图（`AiTextAdapter` / `AiImageAdapter`）
- 素材中心、发布任务、日志
- Cookie 加密存储
- 模型自动检测（`AiModelService`）

## 平台差异点

- 登录方式（扫码 / 短信 / Cookie 导入）
- 内容类型（图文 / 短视频 / 长视频）
- DOM 选择器维护周期

建议每个平台独立 OpenSpec change，避免单 PR 过大。
