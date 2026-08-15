# 国内视频模型接入实现计划

**目标：** 为可灵 AI、即梦 Dreamina、百度文心一格/视频接入内容创作的视频生成功能。

**架构：** 沿用现有 adapter 模式，在 `app/adapters/ai_video/` 新增三个适配器；在 `AiModelService` 的远程视频提供者列表、`_resolve_video_target` 和 `get_video_adapter` 中注册；前端 `ModelsView.vue` 自动通过 `/api/ai-models/options` 展示新选项。

**技术栈：** Python/FastAPI + httpx + SQLAlchemy + Vue3/ElementPlus

---

## 文件映射

| 文件 | 职责 |
|------|------|
| `app/adapters/ai_video/kling.py` | 可灵 AI 文生视频/图生视频适配器 |
| `app/adapters/ai_video/dreamina.py` | 即梦 Dreamina（火山方舟/Seedance）视频适配器 |
| `app/adapters/ai_video/baidu_video.py` | 百度文心一格/千帆视频适配器 |
| `app/services/ai_model_service.py` | 注册新 provider、解析目标 adapter |
| `app/utils/migrations.py` | 若新增配置字段需要迁移（实际用 provider_config JSON，无需新增列） |
| `ModelsView.vue` | 自动读取后端选项，无需修改 |

---

## 任务

### 任务 1：可灵 AI 适配器

**文件：**
- 创建：`ai-publish/backend/app/adapters/ai_video/kling.py`
- 修改：`ai-publish/backend/app/services/ai_model_service.py`

实现：异步提交文生视频/图生视频任务，轮询状态，下载视频并生成缩略图。未配置 `kling_api_key` 时 fallback 到 stub。

### 任务 2：即梦 Dreamina 适配器

**文件：**
- 创建：`ai-publish/backend/app/adapters/ai_video/dreamina.py`
- 修改：`ai-publish/backend/app/services/ai_model_service.py`

实现：调用火山方舟/Seedance 视频生成接口（通过可配置 base_url/model），轮询下载。

### 任务 3：百度视频适配器

**文件：**
- 创建：`ai-publish/backend/app/adapters/ai_video/baidu_video.py`
- 修改：`ai-publish/backend/app/services/ai_model_service.py`

实现：百度千帆/文心一格视频生成接口，AK/SK 换取 access_token，提交任务并轮询。

### 任务 4：注册到模型服务

**文件：**
- 修改：`ai-publish/backend/app/services/ai_model_service.py`

在 `REMOTE_VIDEO_PROVIDERS`、`_resolve_video_target`、`_pick_best_video`、`get_video_adapter` 中注册三个新 provider。

### 任务 5：验证与提交

**文件：**
- 全部

运行后端导入验证和前端 lint，确保无报错后提交。

---

## 申请入口（参考，以官方最新为准）

| 模型 | 申请地址 |
|------|----------|
| 可灵 AI | https://platform.klingai.com/ |
| 即梦 Dreamina | https://www.volcengine.com/product/ark 或 https://dreamina.capcut.com/ |
| 百度文心一格/视频 | https://console.bce.baidu.com/qianfan/overview |
