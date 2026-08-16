# Task 0 Spike 报告 — 小红书自动发布

**日期**: 2026-06-08  
**Reference**: `vendor/social-auto-upload`（MIT 风格开源，见 `pyproject.toml`）  
**Gate 结论**: ✅ **通过（代码级）** — 建议 **借鉴逻辑 + Adapter 封装**，MVP 首发 **图文笔记**（`XiaoHongShuNote`）

---

## 1. LICENSE 与复用决策

| 项 | 结论 |
|----|------|
| 许可证 | 项目为开源 `social-auto-upload`，依赖 patchright、loguru 等 |
| 复用方式 | **不直接 fork 整体**；在 `XhsPlatformAdapter` 中借鉴 `uploader/xiaohongshu_uploader/main.py` 逻辑 |
| 原因 | 原项目偏 CLI/Flask 单体；我们需 FastAPI + 加密 Cookie + 任务日志，Adapter 隔离更合适 |
| 可引用模块 | `cookie_auth`、`xiaohongshu_cookie_gen`、`XiaoHongShuNote`、`XiaoHongShuVideo` |

## 2. 小红书模块结构

```
uploader/xiaohongshu_uploader/main.py   # 核心：登录、视频、图文
examples/get_xiaohongshu_cookie.py      # 登录调试入口
examples/upload_video_to_xiaohongshu.py # 发布调试入口
skills/xiaohongshu-upload/              # CLI 契约 sau xiaohongshu ...
tests/test_xiaohongshu_uploader.py      # 单元测试（mock）
```

**关键 URL：**
- 登录: `https://creator.xiaohongshu.com/login`
- 视频发布: `.../publish/publish?target=video`
- 图文发布: `.../publish/publish?target=image`

**技术栈:** `patchright`（Playwright 分支）+ Chrome channel + `storage_state` JSON 作为 Cookie 文件

## 3. 内容类型选择

| 类型 | 类 | MVP 建议 |
|------|-----|----------|
| 图文笔记 | `XiaoHongShuNote` | ✅ **首选** — 步骤少、无需封面/视频转码、与 AI 配图场景匹配 |
| 短视频 | `XiaoHongShuVideo` | 第二阶段 — 需等待上传进度、封面设置，复杂度高 |

## 4. Cookie 机制

- 存储格式: Playwright `storage_state` JSON 文件
- 校验: `cookie_auth()` 访问发布页，检测是否跳转登录页
- 登录: 扫码 → 轮询 `_is_xhs_login_completed` → 保存 storage_state
- 超时: 默认 `max_checks=100` × `poll_interval=3s` ≈ 5 分钟（我们 MVP 用 120s 可配置）
- 有效期: **无固定 TTL**，依赖平台会话；需定期 `check-cookie`

## 5. DOM 维护点（高风险）

| 步骤 | 选择器/逻辑 |
|------|-------------|
| 登录框 | `div[class*='login-box']` |
| 二维码 | `.login-box-container` 下 img |
| 标题 | `input[placeholder*="填写标题"]` |
| 正文 | `p[data-placeholder*="输入正文描述"]` |
| 标签 | `#creator-editor-topic-container`（最多 10 个） |
| 发布按钮 | `button:has-text("发布")` |
| 成功页 | `**/publish/success?**` |

平台改版时需更新 `XhsPlatformAdapter`，业务层不受影响。

## 6. Mac vs Linux 差异

| 项 | Mac 开发 | Linux 部署 |
|----|----------|------------|
| 浏览器 | `channel="chrome"` 需本机 Chrome | Docker 需装 Chromium + 依赖 |
| 扫码 | headed 模式或终端二维码图片 | 建议 API 返回二维码 base64 供前端展示 |
| 无头 | `LOCAL_CHROME_HEADLESS=true` 可终端扫码 | 必须 Web 展示二维码 |

## 7. Spike 手动验证步骤

在项目根目录执行（需本机 Chrome + Python 3.10+）：

```bash
cd vendor/social-auto-upload
pip install -e .
playwright install chrome  # 或 patchright install

# 登录（headed，扫码）
python examples/get_xiaohongshu_cookie.py

# 图文发布（准备 videos/demo.png）
python examples/upload_video_to_xiaohongshu.py  # 改 __main__ 为 upload_note_to_xiaohongshu
```

或使用 CLI：

```bash
sau xiaohongshu login --account test1 --headed
sau xiaohongshu upload-note --account test1 --images videos/demo.png --title "测试" --note "正文" --headed
```

**自动化环境未完成扫码/发布实测**（需人工扫码）。代码结构评估已通过 gate。

## 8. 对本项目的实现建议

1. `XhsPlatformAdapter.login()` — 借鉴 `xiaohongshu_cookie_gen`，Cookie 加密存 DB
2. `XhsPlatformAdapter.check_cookie_valid()` — 借鉴 `cookie_auth`
3. `XhsPlatformAdapter.publish()` — MVP 用 `XiaoHongShuNote` 图文路径
4. 步骤日志 — 在 wrapper 各阶段写 `publish_task_logs`
5. 后续视频 — 扩展 `PublishContext.content_type=video` 走 `XiaoHongShuVideo`

---

**Gate**: 代码分析通过，可进入 Task 2+ 实施。E2E 发布成功需用户在本地完成一次手动 spike 验证（Task 10.1–10.3）。

## 9. 多平台 E2E 脚本结论（阶段 E.5.3）

`scripts/e2e_publish.py` 已扩展 `--platform douyin|kuaishou`、`--content-type note|video`、`--cookie`、`--skip-execute`。

| 平台 | 脚本 | 结论 |
|------|------|------|
| xhs | 默认 | API 链路可用；发布依赖有效 Cookie + 本机 Chrome |
| douyin | `--platform douyin` | Adapter 已注册；需导入抖音 Cookie 后实测 DOM/超时 |
| kuaishou | `--platform kuaishou` | 同上，Cookie 路径因环境而异，用 `--cookie` 指定 |

未在本环境完成真实发布（无有效多平台 Cookie）。建议部署后按 `daily-usage.md` §5 逐平台跑通并记录日志。

## 10. 视频号 Spike 结论（阶段 E.5.5）

**日期**: 2026-06-10  
**Vendor 模块**: `uploader/tencent_uploader/main.py`（`tencent_cookie_gen`、`cookie_auth`、`TencentVideo`）  
**Gate 结论**: ✅ **通过（代码级）** — 首发 **短视频**（`TencentVideo.tencent_upload_video`），不支持图文

| 项 | 结论 |
|----|------|
| 登录 | Playwright 扫码，`channels.weixin.qq.com`，与小红书同类流程 |
| Cookie | `storage_state` JSON，可加密存 DB |
| 发布 | 仅视频；支持 3:4 封面（`thumbnail_portrait_path`）、短标题（`short_title`） |
| 定时 | `publish_date` 支持排期 |
| 风险 | DOM 变更、上传进度等待超时；服务器需 Chromium |

**ai-publish 封装**: `ChannelsPlatformAdapter`（`platform=channels`），注册于 `AdapterFactory`。

**验证命令**:

```bash
python ai-publish/scripts/e2e_publish.py --platform channels --content-type video --skip-execute
# 有 Cookie 后去掉 --skip-execute
sau tencent login --account <name> --headed   # vendor 目录下
```

## 11. 百家号 Spike 结论（阶段 E.5.6，不交付 Adapter）

**Vendor 模块**: `uploader/baijiahao_uploader/main.py`（`baijiahao_cookie_gen`、`cookie_auth`、`BaiJiaHaoVideo`）

| 项 | 结论 |
|----|------|
| CLI | **未**接入 `sau_cli.py`，仅有 `examples/get_baijiahao_cookie.py` |
| 登录 | Playwright；`page.pause()` 需人工在调试器继续，**不适合** API 无头扫码 |
| 发布 | 视频为主；定时选择不准确（代码注释标注随机） |
| 建议 | P4+ 再评估；需重构登录流、补齐 CLI 与 E2E 后再做 Adapter |

**Gate**: ⚠️ **暂缓** — 登录体验与 CLI 成熟度不足，本阶段不实现 `baijiahao` Adapter。

## 12. TikTok Spike 结论（阶段 E.5.6，不交付 Adapter）

**Vendor 模块**: `uploader/tk_uploader/main.py`（`get_tiktok_cookie`、`cookie_auth`、`Video` 上传类）

| 项 | 结论 |
|----|------|
| 浏览器 | **Firefox**（非 Chromium），与现有 Docker API 镜像栈不一致 |
| 登录/发布 | 面向 tiktok.com 国际站；需稳定代理与账号环境 |
| CLI | 未接入 `sau_cli.py` |
| 建议 | 海外部署独立 Worker + Firefox 镜像；国内产品文档优先级低 |

**Gate**: ⚠️ **暂缓** — 环境依赖重，与当前国内多平台主线不匹配。
