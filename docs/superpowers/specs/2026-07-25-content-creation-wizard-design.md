# 内容创作向导 + 发布向导优化 设计文档

> 日期：2026-07-25
> 状态：设计完成，待审查

---

## 1. 背景与目标

### 当前问题
- 现有5步发布向导将内容创作（AI文案/视频生成）和发布操作混在一起，页面臃肿（PublishView.vue 34.5KB）
- 缺少"关键词→文案→润色→定稿→视频/图文"的结构化创作流程
- 文案润色只有基础的一次性生成，不支持对话式微调和内联编辑
- 视频生成缺少异步状态页，用户只能同步等待

### 目标
新增独立的"内容创作向导"，与发布向导解耦，形成 **创作 → 发布** 两段式工作流。

---

## 2. 整体架构

```
[内容创作向导（新增）]              [发布向导（优化后）]
                                    
灵感输入 → 文案创作+润色            Step 0: 选平台/账号
    ↓                                   ↓
内容生成(视频/图文)                  Step 1: 文案(微调/去创作)
    ↓                                   ↓
异步状态页(可重生成)                Step 2: 素材(三来源)
    ↓                                   ↓
定稿入库                            Step 3: 预览确认
                                        ↓
                                    Step 4: 排期/发布
```

### 决策记录

| 决策 | 结论 |
|------|------|
| 创作 vs 发布关系 | 独立向导，通过素材库+快捷按钮衔接 |
| 润色交互 | 对话式(A) + 内联编辑(B) 结合 |
| 视频生成等待 | 异步生成 + 状态页，可后台运行(C) |
| 发布向导视频来源 | 创作产出 + 本地上传 + 素材库(保留三者) |
| 数字人搬家 | 整体搬到创作向导，视频生成保持占位 |
| 图文处理 | 发布向导保留快速模式 + 创作向导也支持图文 |
| 视频封面生成 | 从发布向导移到创作向导 |

---

## 3. 新增：内容创作向导

### 3.1 前端页面

- 文件：`web/src/views/CreateView.vue`
- 路由：`/create`
- 独立导航入口，与发布向导平级

### 3.2 后端

- API：`backend/app/api/create.py`（新增）
- Service：`backend/app/services/create_service.py`（新增）
- 模型：新增 `CreativeSession` 表（会话持久化）

### 3.3 步骤 1 - 灵感输入

**字段：**

| 字段 | 必填 | 说明 |
|------|------|------|
| 内容类型 | 是 | 视频 / 图文 |
| 关键词 | 是 | 核心卖点、话题、产品名 |
| 背景信息 | 否 | 品牌定位、受众、调性 |
| 主题/风格 | 否 | 故事化、教程、搞笑、情感等 |
| 场景描述 | 否 | 使用场景画面描述 |
| 目标平台 | 否 | 多选，影响文案风格 |

**交互**：表单提交后调用 `POST /api/create/session`，返回 session_id。

### 3.4 步骤 2 - 文案创作 + 润色

**布局**：左侧 AI 对话润色面板 + 右侧文案编辑区

**功能**：
- AI 根据 Step 1 输入自动生成初稿（标题+正文+标签）
- 左侧对话式润色：输入自然语言描述（"短一点""更像B站风格"）
- 快捷润色按钮：缩短、扩写、变幽默、加 emoji、变正式、按平台风格切换
- 右侧内联编辑：直接修改标题/正文/标签
- 支持重新生成（重置AI初稿）
- AI 每次响应自动更新右侧内容

**API**：
- `POST /api/create/{session_id}/generate-copy` — 生成初稿
- `POST /api/create/{session_id}/polish` — 对话润色一轮
- `GET /api/create/{session_id}/copy` — 获取当前文案状态

### 3.5 步骤 3 - 内容生成

根据 Step 1 选择的内容类型走不同分支。

#### 3.5a 视频内容

**生成方式（Tab 切换）：**

| 方式 | 状态 | 输入 |
|------|------|------|
| 文生视频 | 可用（MiniMax/万相） | 视频描述(自动从文案生成) + 时长/分辨率/帧率 |
| 图生视频 | 可用（MiniMax） | 驱动图片 + 视频描述 |
| 仿真人 | 可用（MiniMax S2V-01） | 选择仿真人 + 口播文案 |
| 数字人 | 占位桩 | 选择数字人 + 口播文案 |

**API**：复用现有 `POST /api/ai/video/generate`

### 3.5b 图文内容

- AI 生成封面：风格/品牌色/品牌说明配置
- AI 生成配图：风格/数量(1-9)
- 支持上传已有图片
- 复用现有 `POST /api/ai/image/generate`

### 3.6 步骤 4 - 异步生成状态页

**功能**：
- 实时进度展示（百分比/预计剩余时间）
- 生成历史列表（已完成/生成中）
- 预览已完成的视频/图片
- 不满意可重新生成（入历史列表）
- "在后台生成，稍后查看" — 用户可离开，任务继续
- 选定产出后点击「完成创作」

**API**：
- `GET /api/create/{session_id}/generations` — 获取生成任务列表
- `GET /api/create/generations/{gen_id}/status` — 查询单个任务状态
- `POST /api/create/{session_id}/complete` — 完成创作，产出入库

**WebSocket（可选优化）**：推送生成进度更新

### 3.7 完成入库

- 定稿文案 → 素材库（type=article, category=创作产出）
- 生成的视频/图片 → 素材库（type=video/image, category=创作产出）
- 关联关系通过 CreativeSession 记录
- 可一键跳转发布向导，自动预选产出素材

---

## 4. 变更：发布向导

### 4.1 移除的内容

- Step 2 中 AI 视频生成入口（`showVideoGenDialog`）
- `VideoGenDialog` 组件调用（组件本身保留，搬到创作向导复用）
- 视频封面生成（小红书/视频号的 `generateVideoCover`）
- 数字人/仿真人在发布向导中的选择入口

### 4.2 保留的内容

- 文案快速生成/编辑（Step 1）
- 本地上传视频/图片（Step 2/3）
- 素材库选择已有素材（Step 2/3）
- 图文类型的快速 AI 封面生成（C 路径保留）
- 图文 AI 配图生成（弹窗模式保留）

### 4.3 新增的内容

| 位置 | 新增 | 说明 |
|------|------|------|
| Step 1 | 「去创作」按钮 | 点击跳转 `/create`，携带当前平台信息 |
| Step 2 | 「去创作」按钮 | 点击跳转 `/create` |
| 素材列表 | "创作产出"分类 | 按 category=创作产出 筛选 |
| 素材下拉 | 来源标记 | 显示素材来源（创作/上传/AI生成） |

### 4.4 发布向导与创作向导衔接

```
发布向导 Step 2                   创作向导
┌──────────────┐                 ┌─────────────┐
│ 素材来源：    │   点击「去创作」  │             │
│ [创作产出] ───┼───────────────→ │ 走完创作流程 │
│ [本地上传]   │                 │             │
│ [素材库]     │←─ 完成创作回来 ──│ 入库         │
│              │   自动预选素材   │             │
└──────────────┘                 └─────────────┘
```

---

## 5. 数据模型

### CreativeSession（新增）

```python
class CreativeSession(Base):
    __tablename__ = "creative_sessions"
    
    id            = Column(Integer, primary_key=True)
    user_id       = Column(Integer, ForeignKey("users.id"))
    content_type  = Column(String(20))     # video / note
    keywords      = Column(Text)
    background    = Column(Text, nullable=True)
    theme_style   = Column(String(100), nullable=True)
    scene_desc    = Column(Text, nullable=True)
    platforms     = Column(JSON, nullable=True)  # ["douyin", "bilibili"]
    status        = Column(String(20))     # drafting / generating / completed
    final_copy    = Column(JSON, nullable=True)  # {title, body, tags}
    output_material_ids = Column(JSON, nullable=True)  # 产出素材ID列表
    created_at    = Column(DateTime)
    updated_at    = Column(DateTime)
```

### GenerationTask（新增，或在发布任务表复用/扩展）

```python
class GenerationTask(Base):
    __tablename__ = "generation_tasks"
    
    id            = Column(Integer, primary_key=True)
    session_id    = Column(Integer, ForeignKey("creative_sessions.id"))
    gen_type      = Column(String(30))     # text_to_video / image_to_video / simulation_human / digital_human / cover / images
    provider      = Column(String(50))     # minimax / wanxiang / hunyuan / stub
    input_params  = Column(JSON)
    status        = Column(String(20))     # pending / running / completed / failed
    progress      = Column(Integer, default=0)
    result        = Column(JSON, nullable=True)  # {material_id, video_url, ...}
    error_message = Column(Text, nullable=True)
    created_at    = Column(DateTime)
    completed_at  = Column(DateTime, nullable=True)
```

---

## 6. API 接口

### 新增 API

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/create/session` | 创建创作会话 |
| GET | `/api/create/sessions` | 获取用户创作会话列表 |
| GET | `/api/create/{session_id}` | 获取会话详情 |
| POST | `/api/create/{session_id}/generate-copy` | AI生成文案初稿 |
| POST | `/api/create/{session_id}/polish` | 对话润色（一轮） |
| GET | `/api/create/{session_id}/copy` | 获取当前文案 |
| PUT | `/api/create/{session_id}/copy` | 手动更新文案（内联编辑保存） |
| POST | `/api/create/{session_id}/generate` | 触发内容生成（视频/图文） |
| GET | `/api/create/{session_id}/generations` | 获取生成任务列表 |
| GET | `/api/create/generations/{gen_id}` | 查询生成任务状态 |
| POST | `/api/create/{session_id}/complete` | 完成创作（产出入库） |
| DELETE | `/api/create/{session_id}` | 删除创作会话 |

### 现有 API 变更

| 路径 | 变更 |
|------|------|
| `POST /api/ai/video/generate` | 保持不变，创作向导复用 |
| `POST /api/ai/image/generate` | 保持不变，创作向导复用 |
| `POST /api/ai/text/generate` | 保持不变，创作向导复用 |

---

## 7. 路由与导航

### 新路由

```
/create              → CreateView.vue（内容创作向导）
/create/:sessionId   → CreateView.vue（恢复已有会话）
```

### 导航栏新增

"内容创作"入口，位于"发布任务"旁边或前面。

---

## 8. 组件复用

| 现有组件 | 使用位置 |
|----------|----------|
| `VideoGenDialog.vue` | 搬到创作向导 Step 3 |
| AI 生成图片弹窗（PublishView 内） | 创作向导 Step 3 图文分支复用 |
| 素材选择下拉 | 创作向导完成页 + 发布向导保持 |

---

## 9. 自审结果

- [x] 占位符扫描：无 TBD/TODO
- [x] 内部一致性：VideoGenDialog 搬走后发布向导的视频封面生成也一并移除，一致
- [x] 范围检查：聚焦在创作向导+发布向导优化，不涉及账号管理/平台适配器/定时任务
- [x] 模糊检查：
  - "对话润色"的上下文管理明确了是同一会话内的多轮对话
  - 异步生成的轮询/WebSocket策略明确了优先轮询，WS 作为可选优化
  - 图文快速路径 vs 创作向导图文的关系明确了并存，用户自行选择
