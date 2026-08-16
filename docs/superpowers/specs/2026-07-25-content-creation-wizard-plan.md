# 内容创作向导 + 发布向导优化 实现计划

> 日期：2026-07-25
> 基于设计文档：`docs/superpowers/specs/2026-07-25-content-creation-wizard-design.md`

---

## 实现顺序与依赖

```
Phase 1: 后端基础          Phase 2: 前端创作向导       Phase 3: 前端发布优化     Phase 4: 联调收尾
┌─────────────────┐      ┌──────────────────┐      ┌──────────────────┐      ┌───────────┐
│ 1.1 数据模型     │      │ 2.1 页面骨架      │      │ 3.1 移除旧入口     │      │ 4.1 端到端 │
│ 1.2 创作服务     │ ──→  │ 2.2 灵感输入      │ ──→  │ 3.2 加入快捷按钮   │ ──→  │ 4.2 素材  │
│ 1.3 API 路由     │      │ 2.3 文案+润色     │      │ 3.3 素材分类       │      │    衔接   │
│ 1.4 生成任务追踪  │      │ 2.4 内容生成      │      │                    │      │ 4.3 Bug   │
│ 1.5 数据库迁移    │      │ 2.5 异步状态页    │      │                    │      │   修复    │
└─────────────────┘      └──────────────────┘      └──────────────────┘      └───────────┘
```

---

## Phase 1: 后端基础

### Task 1.1 — 数据模型（~30 min）

**文件：** `backend/app/models/__init__.py`

- 新增 `CreativeSession` 表
  - 字段：id, user_id, content_type, keywords, background, theme_style, scene_desc, platforms(JSON), status, final_copy(JSON), output_material_ids(JSON), created_at, updated_at
- 新增 `GenerationTask` 表
  - 字段：id, session_id, gen_type, provider, input_params(JSON), status, progress, result(JSON), error_message, created_at, completed_at

**文件：** `backend/app/schemas/__init__.py`

- 新增 `CreativeSessionCreate`、`CreativeSessionResponse`、`CreativeSessionListResponse`
- 新增 `PolishRequest`（润色请求）、`PolishResponse`
- 新增 `GenerationRequest`、`GenerationTaskResponse`
- 新增 `CopyResponse`（文案状态）、`CopyUpdateRequest`

---

### Task 1.2 — 创作服务（~1.5 hr）

**文件：** `backend/app/services/create_service.py`（新文件）

```
CreateService 类：
├── create_session(user_id, data) → CreativeSession
├── get_session(session_id, user_id) → CreativeSession
├── get_sessions(user_id, page, size) → List[CreativeSession]
├── generate_copy(session_id, user_id) → CopyResult
│   └── 调用现有 AiContentService.generate_text()
├── polish_copy(session_id, user_id, message, quick_action?) → CopyResult
│   └── 对话式：将历史对话+当前文案作为context，送AI润色
├── update_copy(session_id, user_id, copy_data) → CopyResult
│   └── 内联编辑：直接保存用户手动修改
├── start_generation(session_id, user_id, gen_config) → GenerationTask
│   └── 触发异步生成任务
├── get_generations(session_id, user_id) → List[GenerationTask]
├── get_generation_status(gen_id, user_id) → GenerationTask
├── complete_session(session_id, user_id) → Material[]
│   └── 文案+视频/图片入库，标记session完成
└── delete_session(session_id, user_id) → void
```

**关键实现细节**：

1. **润色对话框上下文管理**
   - 每次润色将"当前文案 + 用户指令 + AI 回复"存入 CreativeSession 的对话历史（可用 JSON 字段 `polish_history`）
   - 润色请求时的 context = session 输入参数 + 当前文案 + 最近 N 轮对话

2. **快捷润色按钮映射**
   ```python
   QUICK_ACTIONS = {
       "shorten": "请将文案缩短到原来的一半以内",
       "expand": "请将文案扩写，增加更多细节描述",
       "humorous": "请让文案更幽默有趣",
       "add_emoji": "请在合适位置添加 emoji 表情",
       "formal": "请让文案更正式专业",
       "bilibili_style": "请调整为B站风格（口语化、有梗、适合年轻受众）",
       "xiaohongshu_style": "请调整为小红书风格（种草感、生活化、加emoji、分段落）",
       # ...
   }
   ```

3. **异步生成任务**
   - `start_generation` 创建 GenerationTask(status=pending)，放入后台队列
   - Worker 执行后更新 status 和 progress
   - 复用现有 Redis 队列或 APScheduler

---

### Task 1.3 — API 路由（~45 min）

**文件：** `backend/app/api/create.py`（新文件）

注册到 `main.py`，添加路由前缀 `/api/create`。

| 方法 | 路径 | 处理函数 | 权限 |
|------|------|----------|------|
| POST | `/session` | `create_session` | 登录即可 |
| GET | `/sessions` | `list_sessions` | 登录即可 |
| GET | `/{session_id}` | `get_session` | 所有者或管理员 |
| POST | `/{session_id}/generate-copy` | `generate_copy` | 所有者 |
| POST | `/{session_id}/polish` | `polish_copy` | 所有者 |
| GET | `/{session_id}/copy` | `get_copy` | 所有者 |
| PUT | `/{session_id}/copy` | `update_copy` | 所有者 |
| POST | `/{session_id}/generate` | `start_content_generation` | 所有者 |
| GET | `/{session_id}/generations` | `list_generations` | 所有者 |
| GET | `/generations/{gen_id}` | `get_generation` | 所有者 |
| POST | `/{session_id}/complete` | `complete_session` | 所有者 |
| DELETE | `/{session_id}` | `delete_session` | 所有者 |

---

### Task 1.4 — 生成任务追踪（~1 hr）

**方案：** 优先用轮询，WebSocket 作为可选后续优化。

1. **轮询端点** `GET /api/create/generations/{gen_id}`：
   - 前端每 3 秒轮询
   - 返回 `{status, progress, result?}`

2. **任务执行**：
   - 修改现有 `material_service.py` 的 `generate_video`/`generate_image`，支持传入 `gen_task_id` 参数
   - 每次进度回调时更新 GenerationTask.progress
   - 完成后更新 status=completed，填入 result

3. **降级**：
   - 如果当前没有独立 worker，先用同步方式执行（但轮询端点已有，后续切异步不影响前端）

---

### Task 1.5 — 数据库迁移（~15 min）

**文件：** `backend/app/utils/migrations.py`

- 添加 `CreativeSession` 和 `GenerationTask` 表的创建迁移

---

## Phase 2: 前端创作向导

### Task 2.1 — 页面骨架（~45 min）

**文件：** `web/src/views/CreateView.vue`（新文件）

- 4 步进度条（灵感输入 / 文案创作 / 内容生成 / 完成）
- 步骤间导航，支持上一步
- CSS 沿用 Element Plus 风格，与现有页面一致

**路由注册：** `web/src/router/index.js`
```js
{ path: '/create', name: 'create', component: CreateView },
{ path: '/create/:sessionId', name: 'create-session', component: CreateView }
```

**导航入口：** 侧边栏添加"内容创作"菜单项

---

### Task 2.2 — Step 1: 灵感输入（~45 min）

- 内容类型选择（视频/图文），radio 或卡片选择
- 关键词输入（必填，el-input + 必填校验）
- 背景信息（选填，el-input type=textarea，3行）
- 主题/风格（选填，el-select 下拉 + 自定义输入）
- 场景描述（选填，el-input type=textarea，2行）
- 目标平台（选填，el-checkbox-group 多选）
- 表单验证 → 调用 `POST /api/create/session` → 获得 session_id → 进入 Step 2

**预设风格列表：**
```
故事化、教程类、搞笑幽默、情感共鸣、干货知识、开箱测评、Vlog日常、种草推荐、品牌宣传
```

---

### Task 2.3 — Step 2: 文案创作 + 润色（~2 hr）

这是核心复杂步骤，左右分栏布局：

**左侧：AI 对话润色面板（~40%宽度）**

- 消息列表（el-scrollbar，自动滚动到底部）
  - AI 消息气泡：显示生成的文案预览 + "已应用到右侧编辑区"
  - 用户消息气泡："缩短到100字"
- 底部输入区：
  - el-input + el-button 发送
  - 回车发送
- 快捷按钮栏（el-button-group 或 flex wrap）：
  - 缩短 / 扩写 / 变幽默 / 加 emoji / 变正式
  - 按目标平台动态显示：B站风格 / 小红书风格 / 抖音风格

**右侧：文案编辑区（~60%宽度）**

- 标题：el-input（大字号）
- 正文：el-input type=textarea（rows=12，自动高度）
- 标签：el-input + el-tag 展示
- "重新生成"按钮（重置 AI 初稿）

**状态管理：**
```javascript
const sessionId = ref(null)
const copy = reactive({ title: '', body: '', tags: [] })
const chatMessages = ref([]) // [{role, content}]
const isPolishing = ref(false)
```

**流程：**

1. 进入 Step 2 → 自动调用 `POST /{session_id}/generate-copy` → 展示初稿
2. 用户点击快捷按钮 → 调用 `POST /{session_id}/polish`（带 quick_action）
3. 用户输入自定义指令 → 同样调用 polish
4. 用户在右侧直接编辑 → `PUT /{session_id}/copy`（防抖 1.5s 保存）
5. 点击"定稿"→ 进入 Step 3

---

### Task 2.4 — Step 3: 内容生成（~1.5 hr）

#### 3.4.1 视频 Tab 切换

- 复用 `VideoGenDialog.vue`，移植到此处
- 四种 Tab：文生视频 / 图生视频 / 仿真人 / 数字人(占位)
- 视频描述自动从定稿文案生成（取标题+正文前100字拼接）
- 点击"开始生成" → 调用 `POST /{session_id}/generate` → 进入 Step 4 状态页

#### 3.4.2 图文面板

- 封面生成：
  - 风格下拉 + 品牌色 color picker + 品牌名输入
  - "生成封面"按钮 → 调用 `POST /api/ai/image/generate`
  - 生成后预览
- 配图生成：
  - 风格下拉 + 数量选择(1-9)
  - "生成配图"按钮 → 调用 `POST /api/ai/image/generate`
  - 网格预览
- 上传已有图片（el-upload）
- "完成"→ 进入 Step 4 状态页

---

### Task 2.5 — Step 4: 异步生成状态页（~1 hr）

**布局：**

```
┌───────────── 生成任务状态 ─────────────────┐
│                                             │
│  ▲ 进度条 + 百分比 + 预计剩余时间             │
│  ▲ "在后台生成"按钮（隐藏此页，任务继续）       │
│                                             │
│  ═══════════════════════════════════════    │
│                                             │
│  生成历史                                    │
│  ┌─────────────────────────────────────┐    │
│  │ #1 已完成 ✓  [预览] [选择] [重新生成] │    │
│  │ #2 生成中 ⏳  65%                    │    │
│  └─────────────────────────────────────┘    │
│                                             │
│  [选定产出 → 完成创作]                        │
└─────────────────────────────────────────────┘
```

**轮询逻辑**：
```javascript
// 每3秒轮询
const pollInterval = setInterval(async () => {
  for (const task of generationTasks.value.filter(t => t.status === 'running')) {
    const res = await api.getGenerationStatus(task.id)
    Object.assign(task, res)
  }
  // 全部完成时停止轮询
  if (generationTasks.value.every(t => t.status !== 'running')) {
    clearInterval(pollInterval)
  }
}, 3000)
```

**重新生成**：创建新的 GenerationTask，加入列表

**完成创作**：
- 调用 `POST /{session_id}/complete`
- 文案+选定的视频/图片入库
- 提示"创作已完成" + "去发布"按钮（跳转 `/publish?withSession={sessionId}`）

---

### Task 2.6 — API 封装（~20 min）

**文件：** `web/src/api/index.js` 或独立的 `web/src/api/create.js`

```javascript
export function createSession(data)       → POST /api/create/session
export function getSessions(params)       → GET /api/create/sessions
export function getSession(id)            → GET /api/create/{id}
export function generateCopy(id)          → POST /api/create/{id}/generate-copy
export function polishCopy(id, data)      → POST /api/create/{id}/polish
export function getCopy(id)               → GET /api/create/{id}/copy
export function updateCopy(id, data)      → PUT /api/create/{id}/copy
export function startGeneration(id, data) → POST /api/create/{id}/generate
export function getGenerations(id)        → GET /api/create/{id}/generations
export function getGenerationStatus(gid)  → GET /api/create/generations/{gid}
export function completeSession(id)       → POST /api/create/{id}/complete
export function deleteSession(id)         → DELETE /api/create/{id}
```

---

## Phase 3: 发布向导优化

### Task 3.1 — 移除旧入口（~30 min）

**文件：** `web/src/views/PublishView.vue`

1. 移除 Step 2 中的 `VideoGenDialog` 引用和调用
2. 移除 `showVideoGenDialog` ref 和相关 show/hide 逻辑
3. 移除 `videoCover` 相关的生成入口（`generateVideoCover`、`skipVideoCover`）
4. 保留 `generateCover`（图文快速封面，C 路径）
5. 保留 `showStep3ImageGen`（图文快速配图，C 路径）
6. 清理不再需要的 import 和 computed 属性

---

### Task 3.2 — 加入「去创作」快捷按钮（~20 min）

**文件：** `web/src/views/PublishView.vue`

- Step 1 底部添加：
  ```html
  <el-button @click="goToCreate" type="primary" plain>
    去内容创作 → 获得更专业的文案和素材
  </el-button>
  ```

- Step 2 素材选择区添加：
  ```html
  <el-button @click="goToCreate" type="primary" plain>
    AI 创作新素材 →
  </el-button>
  ```

- `goToCreate()` 方法：
  ```javascript
  const goToCreate = () => {
    // 携带当前平台信息
    router.push({
      path: '/create',
      query: { ref: 'publish', platform: form.platform }
    })
  }
  ```

---

### Task 3.3 — 素材分类 + 创作产出（~25 min）

**文件：** `web/src/views/PublishView.vue`

1. `selectableMaterials` computed 增加"创作产出"分类
2. 素材下拉框增加分组或标签，区分来源
3. 从创作向导跳回发布向导时（`?withSession=xxx`）：
   - 自动请求 session 关联的素材 ID
   - 自动预填充到 `form.material_ids`
   - 如果有文案，自动预填到 Step 1 的文案区

---

## Phase 4: 联调收尾

### Task 4.1 — 端到端测试（~45 min）

1. 完整走通：灵感输入 → 文案生成 → 对话润色 → 手动编辑 → 定稿 → 视频生成 → 等待完成 → 预览 → 入库
2. 完整走通：创作向导图文路径
3. 走通：创作向导完成 → 跳转发布向导 → 素材自动预选 → 发布
4. 走通：发布向导「去创作」→ 创作向导 → 回来 — 完整闭环
5. 走通：图文发布快捷路径（验证没被改动破坏）

---

### Task 4.2 — 素材库素材衔接（~20 min）

1. 验证创作产出的素材在素材库中可被浏览/管理
2. 验证素材库筛选"创作产出"分类正常
3. 验证素材库中删除素材不影响创作会话

---

### Task 4.3 — 边界情况 + Bug 修复（~30 min）

- 会话恢复：访问 `/create/{sessionId}` 能正确恢复各步骤状态
- 空状态：无创作历史时的空状态提示
- 网络断连：润色请求失败的提示和重试
- 生成超时：视频生成超过 10 分钟的超时处理
- 并发限制：同时只能有一个生成任务
- 权限：用户只能访问自己的会话

---

## 工时估算

| Phase | Task | 预计 |
|-------|------|------|
| 1 | 数据模型 | 30 min |
| 1 | 创作服务 | 1.5 hr |
| 1 | API 路由 | 45 min |
| 1 | 生成任务追踪 | 1 hr |
| 1 | 数据库迁移 | 15 min |
| 2 | 页面骨架 | 45 min |
| 2 | 灵感输入 | 45 min |
| 2 | 文案+润色 | 2 hr |
| 2 | 内容生成 | 1.5 hr |
| 2 | 异步状态页 | 1 hr |
| 2 | API 封装 | 20 min |
| 3 | 移除旧入口 | 30 min |
| 3 | 添加快捷按钮 | 20 min |
| 3 | 素材分类 | 25 min |
| 4 | 端到端测试 | 45 min |
| 4 | 素材衔接 | 20 min |
| 4 | 边界+Bug | 30 min |
| **合计** | | **~13 hr** |

---

## 风险与备忘

1. **VideoGenDialog 复用**：确保原组件不依赖 PublishView 特有状态，改为通过 props 传入
2. **AI 润色质量**：依赖提示词模板的质量，可能需要调优
3. **异步轮询**：如果后续并发高，改为 WebSocket
4. **不要改动现有平台适配器、定时发布、权限系统**：聚焦在创作向导模块
