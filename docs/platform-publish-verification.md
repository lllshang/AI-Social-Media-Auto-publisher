# 多平台发布验收记录（E.5.9）

本文档记录各平台 **API 链路** 与 **真实发布** 验收状态。真实发布需有效 Cookie 与本机/服务器 Chromium（或 B站 biliup）。

## 自动化检查

```bash
# 1. Adapter 注册与依赖导入
cd ai-publish/backend && python ../scripts/verify_platform_adapters.py

# 2. 健康检查（DB / Redis / 队列深度）
curl -s http://127.0.0.1:8765/health | python -m json.tool

# 3. 各平台 API 链路（需 API 已启动 + 有效 Cookie）
python ai-publish/scripts/e2e_publish.py --platform xhs --skip-execute --cookie <path>
python ai-publish/scripts/e2e_publish.py --platform douyin --skip-execute --cookie <path>
# ... 其他平台同理
```

## 验收状态表

| 平台 | API 链路 | 真实发布 | 备注 |
|------|----------|----------|------|
| 小红书 xhs | ✅ 脚本就绪 | 待运维实测 | 图文/视频均支持 |
| 抖音 douyin | ✅ 脚本就绪 | 待运维实测 | 需抖音 Cookie |
| 快手 kuaishou | ✅ 脚本就绪 | 待运维实测 | 需快手 Cookie |
| 视频号 channels | ✅ 脚本就绪 | 待运维实测 | 仅短视频 |
| B站 bilibili | ✅ 脚本就绪 | 待运维实测 | biliup + tid |
| 百家号 baijiahao | — | 不交付 | Spike 暂缓 |
| TikTok tiktok | — | 不交付 | Spike 暂缓 |

**真实发布完成判定**：任务状态 `success` + `publish_task_logs` 含 `submit/success` 步骤；建议截图或保存日志片段填入下方。

### 运维填写区（可选）

| 平台 | 任务 ID | 日期 | 操作人 | 日志/截图 |
|------|---------|------|--------|-----------|
| xhs | | | | |
| douyin | | | | |
| kuaishou | | | | |
| channels | | | | |
| bilibili | | | | |
