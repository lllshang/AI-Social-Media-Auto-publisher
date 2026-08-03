<template>
  <div class="create-wizard">
    <h2>内容创作</h2>

    <!-- ========== 草稿列表（无活跃会话时显示） ========== -->
    <div v-if="showDraftList" class="step-card draft-list-card">
      <div class="draft-list-header">
        <h3>草稿箱</h3>
        <el-button type="primary" @click="startNewSession">新建创作</el-button>
      </div>
      <div v-if="drafts.length === 0" class="empty-drafts">
        <p>暂无草稿，点击"新建创作"开始</p>
      </div>
      <div v-for="draft in drafts" :key="draft.id" class="draft-item">
        <div class="draft-info">
          <span class="draft-keywords">{{ draft.keywords || '未命名草稿' }}</span>
          <el-tag size="small" :type="draft.content_type === 'video' ? '' : 'success'">
            {{ draft.content_type === 'video' ? '视频' : '图文' }}
          </el-tag>
          <el-tag v-if="draft.status === 'completed'" size="small" type="success">已完成</el-tag>
          <el-tag v-else-if="draft.status === 'drafting'" size="small" type="info">草稿中</el-tag>
          <el-tag v-else size="small" type="warning">生成中</el-tag>
          <span class="draft-time">{{ formatDraftTime(draft.updated_at) }}</span>
        </div>
        <div class="draft-actions">
          <el-button v-if="draft.status === 'completed'" size="small" type="success" @click="viewSession(draft)">查看成果</el-button>
          <el-button v-else size="small" type="primary" @click="resumeDraft(draft)">继续创作</el-button>
          <el-popconfirm title="确定删除这个草稿？" @confirm="removeDraft(draft.id)">
            <template #reference>
              <el-button size="small" type="danger">删除</el-button>
            </template>
          </el-popconfirm>
        </div>
      </div>
    </div>

    <!-- ========== 创作向导（有活跃会话时显示） ========== -->
    <template v-if="!showDraftList">
    <!-- 顶部工具条：返回草稿箱 -->
    <div class="wizard-toolbar">
      <el-button text @click="backToDrafts">
        <span>← 返回草稿箱</span>
      </el-button>
    </div>
    <!-- 步骤条 -->
    <el-steps :active="step" align-center finish-status="success" class="steps">
      <el-step title="灵感输入" />
      <el-step title="文案创作" />
      <el-step title="内容生成" />
      <el-step title="生成状态" />
    </el-steps>

    <!-- ========== Step 0: 灵感输入 ========== -->
    <div v-if="step === 0" class="step-card">
      <el-radio-group v-model="form.content_type" class="type-radio">
        <el-radio-button value="video">视频内容</el-radio-button>
        <el-radio-button value="note">图文内容</el-radio-button>
      </el-radio-group>

      <el-form label-width="100px" class="input-form">
        <el-form-item label="关键词" required>
          <el-input v-model="form.keywords" placeholder="产品卖点、核心话题、产品名称..." />
        </el-form-item>
        <el-form-item label="背景信息">
          <el-input v-model="form.background" type="textarea" :rows="3" placeholder="品牌定位、目标受众、调性..." />
        </el-form-item>
        <el-form-item label="主题/风格">
          <el-input v-model="form.theme_style" placeholder="故事化、教程类、搞笑、情感共鸣..." />
        </el-form-item>
        <el-form-item label="场景描述">
          <el-input v-model="form.scene_desc" type="textarea" :rows="2" placeholder="办公室日常、户外旅行..." />
        </el-form-item>
        <el-form-item label="目标平台">
          <el-checkbox-group v-model="form.platforms">
            <el-checkbox v-for="p in availablePlatforms" :key="p.value" :label="p.value" :value="p.value">
              {{ p.label }}
            </el-checkbox>
          </el-checkbox-group>
        </el-form-item>
      </el-form>

      <el-button type="primary" size="large" :disabled="!canStart" :loading="starting" @click="startSession">
        开始创作 →
      </el-button>
      <el-alert v-if="sessionError" type="error" :closable="true" :title="sessionError" @close="sessionError = ''" show-icon style="margin-top: 12px" />
    </div>

    <!-- ========== Step 1: 文案创作 + 润色 ========== -->
    <div v-if="step === 1" class="step-card split-layout">
      <!-- 左侧：AI 对话润色 -->
      <div class="chat-panel">
        <div class="chat-header">AI 润色对话</div>
        <div class="chat-messages" ref="chatBox">
          <div v-for="(msg, i) in chatMessages" :key="i" :class="['msg', msg.role]">
            <div class="msg-content">{{ msg.content }}</div>
          </div>
          <div v-if="generatingCopy && chatMessages.length === 0" class="msg assistant loading-bubble">
            <div class="msg-content">
              <span class="loading-spinner"></span>
              <span>AI 正在生成初稿文案...</span>
            </div>
          </div>
          <div v-else-if="generatingCopy" class="msg assistant loading-bubble">
            <div class="msg-content">
              <span class="loading-spinner"></span>
              <span>AI 正在重新生成...</span>
            </div>
          </div>
        </div>
        <!-- 快捷按钮 -->
        <div class="quick-actions">
          <el-button
            v-for="btn in quickActions"
            :key="btn.key"
            size="small"
            :disabled="isPolishing"
            @click="quickPolish(btn.key)"
          >{{ btn.label }}</el-button>
        </div>
        <div class="chat-input-row">
          <el-input v-model="polishMessage" placeholder="输入润色需求..." :disabled="isPolishing" @keyup.enter="doPolish" />
          <el-button type="primary" :disabled="!polishMessage.trim() || isPolishing" :loading="isPolishing" @click="doPolish">发送</el-button>
        </div>
      </div>

      <!-- 右侧：文案编辑区 -->
      <div class="editor-panel" v-loading="generatingCopy" element-loading-text="AI 正在生成文案，请稍候...">
        <div class="editor-header">
          <span>文案编辑</span>
          <el-button size="small" :loading="generatingCopy" @click="regenerateCopy">重新生成</el-button>
        </div>
        <el-form label-width="60px">
          <el-form-item label="标题">
            <el-input v-model="copy.title" placeholder="文章标题..." />
          </el-form-item>
          <el-form-item label="正文">
            <el-input v-model="copy.body" type="textarea" :rows="12" placeholder="正文内容..." />
          </el-form-item>
          <el-form-item label="标签">
            <el-input v-model="copy.tagsText" placeholder="#tag1 #tag2" />
          </el-form-item>
        </el-form>
        <div class="editor-actions">
          <el-button @click="step = 0">← 返回修改输入</el-button>
          <el-button type="primary" size="large" :disabled="!copy.body.trim()" @click="finalizeCopy">
            定稿文案，进入下一步 →
          </el-button>
        </div>
        <el-alert v-if="copyError" type="error" :closable="true" :title="copyError" @close="copyError = ''" show-icon style="margin-top: 12px" />
      </div>
    </div>

    <!-- ========== Step 2: 内容生成 ========== -->
    <div v-if="step === 2" class="step-card">
      <!-- 视频分支 -->
      <template v-if="form.content_type === 'video'">
        <h3>生成视频</h3>
        <el-radio-group v-model="videoGenType" class="type-radio">
          <el-radio-button value="text_to_video">文生视频</el-radio-button>
          <el-radio-button value="image_to_video">图生视频</el-radio-button>
          <el-radio-button value="simulation_human">仿真人</el-radio-button>
          <el-radio-button value="digital_human">数字人(开发中)</el-radio-button>
        </el-radio-group>

        <el-form label-width="100px" class="output-form">
          <el-form-item label="视频描述">
            <el-input v-model="videoDesc" type="textarea" :rows="3" />
          </el-form-item>
          <template v-if="videoGenType === 'image_to_video'">
            <el-form-item label="驱动图片">
              <el-upload :auto-upload="false" :show-file-list="false" :on-change="onImageChange" accept="image/*">
                <el-button>选择图片</el-button>
              </el-upload>
              <img v-if="imagePreview" :src="imagePreview" class="preview-img" />
            </el-form-item>
          </template>
          <template v-if="videoGenType === 'simulation_human'">
            <el-form-item label="选择仿真人">
              <el-select v-model="selectedAvatarId" placeholder="选择已创建的仿真人" @focus="loadAvatars">
                <el-option v-for="av in avatars.filter(a => a.type === 'simulation_human')" :key="av.id" :label="av.name" :value="av.id" />
              </el-select>
            </el-form-item>
          </template>
          <template v-if="videoGenType === 'digital_human'">
            <el-form-item label="选择数字人">
              <el-select v-model="selectedAvatarId" placeholder="选择已创建的数字人" @focus="loadAvatars">
                <el-option v-for="av in avatars.filter(a => a.type === 'digital_human')" :key="av.id" :label="av.name" :value="av.id" />
              </el-select>
              <el-tag size="small" type="warning" style="margin-top:4px">视频生成服务开发中，将产出占位视频</el-tag>
            </el-form-item>
          </template>
          <el-form-item label="时长">
            <el-input-number v-model="videoDuration" :min="1" :max="60" :step="1" style="width: 160px" />
            <span class="cost-tag" style="margin-left: 8px">预估 ¥{{ videoCostEstimate }}</span>
          </el-form-item>
          <el-form-item label="分辨率">
            <el-select v-model="videoResolution">
              <el-option value="720p" label="720p" />
              <el-option value="1080p" label="1080p" />
              <el-option value="portrait" label="竖屏" />
            </el-select>
          </el-form-item>
        </el-form>

        <div class="step-actions">
          <el-button @click="step = 1">← 返回文案</el-button>
          <el-button type="primary" size="large" :loading="genStarting" @click="startVideoGen">
            开始生成视频 →
          </el-button>
        </div>
      </template>

      <!-- 图文分支 -->
      <template v-else>
        <h3>生成图文</h3>
        <el-form label-width="100px" class="output-form">
          <el-form-item label="封面风格">
            <el-select v-model="imageStyle" placeholder="选择风格">
              <el-option v-for="s in imageStyles" :key="s" :label="s" :value="s" />
            </el-select>
          </el-form-item>
          <el-form-item label="品牌色">
            <el-input v-model="brandColor" placeholder="#FF6B35" />
          </el-form-item>
          <el-form-item label="品牌说明">
            <el-input v-model="brandHint" placeholder="品牌简短描述" />
          </el-form-item>
        </el-form>

        <div class="step-actions">
          <el-button type="primary" :loading="genStarting" @click="startImageGen(1)">生成封面</el-button>
          <span class="cost-tag" style="margin-left: 8px">预估 ¥{{ imageCostEstimate }}</span>
        </div>

        <el-divider />

        <h4>生成配图</h4>
        <el-form label-width="100px" class="output-form">
          <el-form-item label="配图风格">
            <el-select v-model="imageStyle" placeholder="选择风格">
              <el-option v-for="s in imageStyles" :key="s" :label="s" :value="s" />
            </el-select>
          </el-form-item>
          <el-form-item label="数量">
            <el-select v-model="imageCount">
              <el-option v-for="n in [1,2,3,4,6,9]" :key="n" :label="`${n}张`" :value="n" />
            </el-select>
            <span class="cost-tag" style="margin-left: 8px">预估 ¥{{ multiImageCostEstimate }}</span>
          </el-form-item>
        </el-form>

        <div class="step-actions">
          <el-button @click="step = 1">← 返回文案</el-button>
          <el-button type="primary" size="large" :loading="genStarting" @click="startImageGen(imageCount)">
            生成配图，进入状态页 →
          </el-button>
        </div>
      </template>
    </div>

    <el-alert v-if="genError" type="error" :closable="true" :title="genError" @close="genError = ''" show-icon style="margin-top: 12px" />

    <!-- ========== Step 3: 生成状态页 ========== -->
    <div v-if="step === 3" class="step-card">
      <h3>内容生成状态</h3>

      <!-- 进行中的任务 -->
      <div v-if="activeTask" class="progress-card">
        <div class="progress-header">
          <span>{{ genTypeLabel(activeTask.gen_type) }} — {{ activeTask.provider || '准备中...' }}</span>
          <el-tag :type="activeTask.status === 'completed' ? 'success' : activeTask.status === 'failed' ? 'danger' : 'warning'">
            {{ activeTask.status === 'pending' ? '队列中' : activeTask.status === 'running' ? '生成中' : activeTask.status === 'completed' ? '已完成' : '失败' }}
          </el-tag>
        </div>
        <el-progress
          v-if="activeTask.status !== 'completed' && activeTask.status !== 'failed'"
          :percentage="displayProgress"
          :stroke-width="16"
          :text-inside="true"
          :status="activeTask.status === 'running' ? '' : undefined"
        />
        <div v-if="activeTask.status === 'failed'" class="error-msg">
          {{ activeTask.error_message }}
        </div>
        <div class="progress-hint">
          {{
            activeTask.status === 'pending'
              ? '排队中，等待生成槽位...'
              : activeTask.progress <= 5
                ? '排队中，等待生成槽位...'
                : displayProgress < 30
                  ? '正在调用 AI 生成服务...'
                  : displayProgress >= 99
                    ? '即将完成...'
                    : `预计还需 ${remainingMinutes} 分钟...`
          }}
        </div>
      </div>

      <el-divider />

      <!-- 生成历史 -->
      <h4>生成历史</h4>
      <div v-if="generationTasks.length === 0" class="empty">暂无生成记录</div>
      <div v-for="gen in sortedGenerations" :key="gen.id" class="gen-item">
        <div class="gen-item-head">
          <span>{{ genTypeLabel(gen.gen_type) }}</span>
          <el-tooltip v-if="gen.status === 'failed' && gen.error_message" :content="gen.error_message" placement="top" effect="light">
            <el-tag size="small" type="danger" style="cursor: help;">
              失败
            </el-tag>
          </el-tooltip>
          <el-tag v-else size="small" :type="gen.status === 'completed' ? 'success' : gen.status === 'failed' ? 'danger' : gen.status === 'running' ? 'warning' : 'info'">
            {{ gen.status === 'pending' ? '队列中' : gen.status === 'running' ? `${gen.progress}%` : gen.status === 'completed' ? '已完成' : '失败' }}
          </el-tag>
          <span class="gen-time">{{ formatTime(gen.created_at) }}</span>
          <div class="gen-actions">
            <el-button v-if="gen.status === 'completed' && gen.result?.material_ids?.length" size="small" :loading="gen._previewing" @click="previewGeneration(gen)">
              {{ gen._previewOpen ? '收起' : '预览' }}
            </el-button>
            <el-button size="small" @click="regenerateWith(gen)">重新生成</el-button>
            <el-button
              v-if="gen.status === 'completed' && gen.result?.material_ids?.length"
              :type="isSelected(gen) ? 'primary' : 'default'"
              size="small"
              @click="toggleSelect(gen)"
            >{{ isSelected(gen) ? '已选定' : '选定' }}</el-button>
          </div>
        </div>

        <!-- 内联预览区 -->
        <div v-if="gen._previewOpen && gen.status === 'completed'" class="gen-preview">
          <template v-for="mid in (gen.result?.material_ids || [])" :key="mid">
            <div v-if="materialCache[mid]" class="preview-block">
              <div class="preview-name">{{ materialCache[mid].name || ('素材 #' + mid) }}</div>
              <video v-if="materialCache[mid].type === 'video' && materialCache[mid].url" :src="materialCache[mid].url" controls class="preview-media" />
              <img v-else-if="materialCache[mid].type === 'image' && materialCache[mid].url" :src="materialCache[mid].url" class="preview-media" alt="预览" />
              <a v-else-if="materialCache[mid].url" :href="materialCache[mid].url" target="_blank" class="preview-link">打开素材</a>
              <span v-else class="preview-empty">无可用预览</span>
            </div>
          </template>
        </div>
      </div>

      <div class="step-actions">
        <el-button @click="goBackToGen">← 返回生成</el-button>
        <el-button type="primary" size="large" :loading="completing" :disabled="selectedGenIds.length === 0" @click="finishCreation">
          选定产出 → 完成创作
        </el-button>
      </div>
      <el-alert v-if="statusError" type="error" :closable="true" :title="statusError" @close="statusError = ''" show-icon style="margin-top: 12px" />
    </div>
    </template>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { onBeforeRouteLeave, useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { api } from '@/api'

const route = useRoute()
const router = useRouter()

// ── 常量 ──────────────────────────────────────────────────────
const availablePlatforms = [
  { value: 'douyin', label: '抖音' },
  { value: 'bilibili', label: 'B站' },
  { value: 'xhs', label: '小红书' },
  { value: 'kuaishou', label: '快手' },
  { value: 'channels', label: '视频号' },
]

const imageStyles = ['科技感', '简约', '清新', '复古', '卡通风', '高级感', '美食风', '潮流']
const quickActions = [
  { key: 'shorten', label: '缩短' },
  { key: 'expand', label: '扩写' },
  { key: 'humorous', label: '变幽默' },
  { key: 'add_emoji', label: '加 Emoji' },
  { key: 'formal', label: '变正式' },
  { key: 'bilibili_style', label: 'B站风格' },
  { key: 'xiaohongshu_style', label: '小红书风格' },
  { key: 'douyin_style', label: '抖音风格' },
]

// ── 草稿列表 ──────────────────────────────────────────────────
const showDraftList = ref(false)
const drafts = ref([])

async function loadDrafts() {
  try {
    const res = await api.getSessions({ page: 1, page_size: 20 })
    drafts.value = res.items || []
  } catch { drafts.value = [] }
}

function formatDraftTime(ts) {
  if (!ts) return ''
  const d = new Date(ts)
  const now = new Date()
  const diffMs = now - d
  const diffMin = Math.floor(diffMs / 60000)
  if (diffMin < 1) return '刚刚'
  if (diffMin < 60) return `${diffMin}分钟前`
  const diffH = Math.floor(diffMin / 60)
  if (diffH < 24) return `${diffH}小时前`
  const diffD = Math.floor(diffH / 24)
  if (diffD < 7) return `${diffD}天前`
  return d.toLocaleDateString()
}

function startNewSession() {
  showDraftList.value = false
  step.value = 0
  sessionId.value = null
  resetForm()
}

function backToDrafts() {
  showDraftList.value = true
  loadDrafts()
}

async function removeDraft(id) {
  try {
    await api.deleteSession(id)
    ElMessage.success('草稿已删除')
    loadDrafts()
  } catch (e) {
    ElMessage.error(e.message || '删除失败')
  }
}

async function viewSession(draft) {
  sessionId.value = draft.id
  showDraftList.value = false
  step.value = 3
  // 恢复基础信息
  try {
    const res = await api.getSession(draft.id)
    const s = res.session || res
    form.keywords = s.keywords || ''
    form.background = s.background || ''
    form.content_type = s.content_type || 'video'
    loadAvatars()
    await refreshTasks()
    ElMessage.success('已加载创作成果')
  } catch (e) {
    ElMessage.error(e.message || '加载失败')
  }
}

function resetForm() {
  form.content_type = 'video'
  form.keywords = ''
  form.background = ''
  form.theme_style = ''
  form.scene_desc = ''
  form.platforms = []
  copy.title = ''
  copy.body = ''
  copy.tagsText = ''
  chatMessages.value = []
  polishMessage.value = ''
  videoGenType.value = 'text_to_video'
  videoDesc.value = ''
  videoDuration.value = 5
  videoResolution.value = '720p'
  imagePreview.value = ''
  imageFile.value = null
  selectedAvatarId.value = null
  avatars.value = []
  imageStyle.value = '科技感'
  brandColor.value = ''
  brandHint.value = ''
  imageCount.value = 4
  generationTasks.value = []
  selectedGenIds.value = []
  starting.value = false
}

async function resumeDraft(draft) {
  sessionId.value = draft.id
  showDraftList.value = false

  // 恢复 Step 0 表单
  form.content_type = draft.content_type || 'video'
  form.keywords = draft.keywords || ''
  form.background = draft.background || ''
  form.theme_style = draft.theme_style || ''
  form.scene_desc = draft.scene_desc || ''
  form.platforms = draft.platforms || []

  // 恢复文案
  if (draft.final_copy) {
    copy.title = draft.final_copy.title || ''
    copy.body = draft.final_copy.body || ''
    copy.tagsText = (draft.final_copy.tags || []).join(' ')
  }

  // 恢复 draft_data
  const dd = draft.draft_data
  if (dd) {
    // 恢复 Step 2 参数
    if (dd.video_params) {
      videoGenType.value = dd.video_params.genType || 'text_to_video'
      videoDesc.value = dd.video_params.desc || ''
      videoDuration.value = dd.video_params.duration || 5
      videoResolution.value = dd.video_params.resolution || '720p'
    }
    if (dd.image_params) {
      imageStyle.value = dd.image_params.style || '科技感'
      brandColor.value = dd.image_params.brandColor || ''
      brandHint.value = dd.image_params.brandHint || ''
      if (dd.image_params.count) imageCount.value = dd.image_params.count
    }

    // 恢复步骤
    step.value = dd.step || 0
  } else {
    // 无 draft_data 时，根据状态推断
    if (draft.status === 'generating') {
      step.value = 3
      loadGenerations()
      startPolling()
    } else if (draft.final_copy && draft.final_copy.body) {
      step.value = 1
    } else {
      step.value = 0
    }
  }

  ElMessage.success('已恢复草稿，继续创作')
}

// ── 状态 ──────────────────────────────────────────────────────
const step = ref(0)
const sessionError = ref('')
const copyError = ref('')
const genError = ref('')
const statusError = ref('')

// 切换步骤时清除对应错误
watch(step, (newStep) => {
  if (newStep !== 1) copyError.value = ''
  if (newStep !== 2) genError.value = ''
  if (newStep !== 3) statusError.value = ''
  if (newStep !== 0) sessionError.value = ''
})
const sessionId = ref(null)
const starting = ref(false)
const generatingCopy = ref(false)
const isPolishing = ref(false)
const genStarting = ref(false)
const completing = ref(false)

const form = reactive({
  content_type: 'video',
  keywords: '',
  background: '',
  theme_style: '',
  scene_desc: '',
  platforms: [],
})

const copy = reactive({ title: '', body: '', tagsText: '' })
const chatMessages = ref([])
const polishMessage = ref('')
const chatBox = ref(null)

const videoGenType = ref('text_to_video')
const videoDesc = ref('')
const videoDuration = ref(5)
const videoResolution = ref('720p')
const imagePreview = ref('')
const imageFile = ref(null)
const selectedAvatarId = ref(null)
const avatars = ref([])

const imageStyle = ref('科技感')
const brandColor = ref('')
const brandHint = ref('')
const imageCount = ref(4)

// 费用预估（以常见默认价格估算）
const videoCostEstimate = computed(() => (videoDuration.value * 0.5).toFixed(2))
const imageCostEstimate = computed(() => '0.02')
const multiImageCostEstimate = computed(() => (imageCount.value * 0.02).toFixed(2))

const generationTasks = ref([])
const selectedGenIds = ref([])
let pollTimer = null

// ── 计算属性 ──────────────────────────────────────────────────
const canStart = computed(() => form.keywords.trim())

const activeTask = computed(() =>
  generationTasks.value.find(t => t.status === 'pending' || t.status === 'running') || null
)

// 显示进度：后端 progress 优先级最高；如果卡在低值但任务在 running，前端按 elapsed
// 时间在 [20%, 95%] 区间线性增长，避免 UI 一直停在 20%。
// 后端一旦推 100% 或 completed 状态会立即接管。
const nowTick = ref(Date.now())
let progressTicker = null

// 视频/图片生成大概耗时估计（毫秒）。用于前端把 20%→95% 线性铺到这段时间。
const ESTIMATED_VIDEO_MS = 90 * 1000       // 90 秒
const ESTIMATED_IMAGE_MS = 30 * 1000       // 30 秒

const displayProgress = computed(() => {
  const t = activeTask.value
  if (!t) return 0
  if (t.status === 'completed') return 100
  if (t.status === 'failed') return t.progress || 0
  // 后端推到 95% 以上就以它为准（避免 100% 假完成被前端覆盖）
  if (t.progress >= 95) return Math.min(99, t.progress)
  // 凡是后端已经"进入生成阶段"（status=running 且 progress >= 3），无论
  // progress 卡在 3% 还是 20%，前端都按 elapsed 时间在 [20%, 95%] 平滑铺
  if (t.status === 'running' && t.progress >= 3) {
    const start = new Date(t.created_at).getTime()
    const totalMs = t.gen_type && t.gen_type.includes('video')
      ? ESTIMATED_VIDEO_MS : ESTIMATED_IMAGE_MS
    const elapsed = nowTick.value - start
    const fraction = Math.min(0.95, Math.max(0, elapsed / totalMs))
    return Math.floor(20 + (95 - 20) * fraction)
  }
  return t.progress || 0
})

const remainingMinutes = computed(() => {
  const t = activeTask.value
  if (!t) return 0
  // 按当前 displayProgress 反推总剩余时间（displayProgress 范围 20~95）
  const dp = displayProgress.value
  if (dp >= 95) return 0
  const totalMs = t.gen_type && t.gen_type.includes('video')
    ? ESTIMATED_VIDEO_MS : ESTIMATED_IMAGE_MS
  // 把 [20%, 95%] 映射到 [0, totalMs] 剩余时间
  const remainMs = Math.max(0, ((95 - dp) / (95 - 20)) * totalMs)
  if (remainMs < 30 * 1000) return 1   // 不足 30 秒也显示"1 分钟内"
  return Math.max(1, Math.ceil(remainMs / 60000))
})

const sortedGenerations = computed(() =>
  [...generationTasks.value].sort((a, b) => new Date(b.created_at || 0) - new Date(a.created_at || 0))
)

// ── 辅助 ──────────────────────────────────────────────────────
function genTypeLabel(type) {
  const map = {
    text_to_video: '文生视频', image_to_video: '图生视频',
    simulation_human: '仿真人', digital_human: '数字人',
    cover: '封面图', images: '配图',
  }
  return map[type] || type
}

function formatTime(ts) {
  if (!ts) return ''
  return new Date(ts).toLocaleTimeString()
}

function isSelected(gen) {
  return generationTasks.value
    .filter(g => selectedGenIds.value.includes(g.id))
    .includes(gen)
}

function toggleSelect(gen) {
  const idx = selectedGenIds.value.indexOf(gen.id)
  if (idx > -1) selectedGenIds.value.splice(idx, 1)
  else selectedGenIds.value.push(gen.id)
}

// ── 收集草稿数据 ──────────────────────────────────────────────
function collectDraftData() {
  return {
    step: step.value,
    form: { ...form },
    copy_data: { title: copy.title, body: copy.body, tagsText: copy.tagsText },
    video_params: {
      genType: videoGenType.value,
      desc: videoDesc.value,
      duration: videoDuration.value,
      resolution: videoResolution.value,
    },
    image_params: {
      style: imageStyle.value,
      brandColor: brandColor.value,
      brandHint: brandHint.value,
      count: imageCount.value,
    },
  }
}

// ── 保存草稿（带防重入） ──────────────────────────────────────
let savingDraft = false
async function doSaveDraft() {
  if (!sessionId.value || savingDraft) return
  savingDraft = true
  try {
    await api.saveDraft(sessionId.value, collectDraftData())
  } catch {
    // 静默失败，不影响用户操作
  } finally {
    savingDraft = false
  }
}

// ── Step 0: 开始创作 ──────────────────────────────────────────
async function startSession() {
  starting.value = true
  sessionError.value = ''
  try {
    const session = await api.createSession({
      content_type: form.content_type,
      keywords: form.keywords,
      background: form.background || null,
      theme_style: form.theme_style || null,
      scene_desc: form.scene_desc || null,
      platforms: form.platforms.length ? form.platforms : ['douyin'],
    })
    sessionId.value = session.id
    step.value = 1
    showDraftList.value = false
    // 自动生成初始文案
    await generateInitialCopy()
  } catch (e) {
    sessionError.value = e.message || '创建失败'
  } finally {
    starting.value = false
  }
}

// ── Step 1: 文案 ──────────────────────────────────────────────
async function generateInitialCopy() {
  generatingCopy.value = true
  copyError.value = ''
  try {
    const res = await api.generateCopy(sessionId.value)
    copy.title = res.title || ''
    copy.body = res.body || ''
    copy.tagsText = (res.tags || []).join(' ')
    chatMessages.value = [{ role: 'assistant', content: `已根据你的输入生成初稿：「${copy.title}」` }]
  } catch (e) {
    copyError.value = e.message || '生成文案失败'
  } finally {
    generatingCopy.value = false
  }
}

async function regenerateCopy() {
  await generateInitialCopy()
}

async function doPolish() {
  if (!polishMessage.value.trim()) return
  isPolishing.value = true
  copyError.value = ''
  const msg = polishMessage.value.trim()
  polishMessage.value = ''
  chatMessages.value.push({ role: 'user', content: msg })

  try {
    const res = await api.polishCopy(sessionId.value, { message: msg })
    copy.title = res.title || ''
    copy.body = res.body || ''
    copy.tagsText = (res.tags || []).join(' ')
    chatMessages.value.push({ role: 'assistant', content: `已根据「${msg}」润色文案` })
  } catch (e) {
    copyError.value = e.message || '润色失败'
    chatMessages.value.push({ role: 'assistant', content: `润色失败：${e.message || '未知错误'}` })
  } finally {
    isPolishing.value = false
    nextTick(() => {
      if (chatBox.value) chatBox.value.scrollTop = chatBox.value.scrollHeight
    })
  }
}

async function quickPolish(action) {
  isPolishing.value = true
  copyError.value = ''
  const label = quickActions.find(a => a.key === action)?.label || action
  chatMessages.value.push({ role: 'user', content: `[${label}]` })

  try {
    const res = await api.polishCopy(sessionId.value, { quick_action: action })
    copy.title = res.title || ''
    copy.body = res.body || ''
    copy.tagsText = (res.tags || []).join(' ')
    chatMessages.value.push({ role: 'assistant', content: `已按「${label}」风格润色` })
  } catch (e) {
    copyError.value = e.message || '润色失败'
  } finally {
    isPolishing.value = false
    nextTick(() => {
      if (chatBox.value) chatBox.value.scrollTop = chatBox.value.scrollHeight
    })
  }
}

// 内联编辑防抖保存
let saveTimer = null
watch([() => copy.title, () => copy.body, () => copy.tagsText], () => {
  if (!sessionId.value) return
  clearTimeout(saveTimer)
  saveTimer = setTimeout(() => {
    api.updateCopy(sessionId.value, {
      title: copy.title,
      body: copy.body,
      tags: copy.tagsText.split(/\s+/).filter(Boolean),
    }).catch(() => {})
  }, 1500)
})

function finalizeCopy() {
  // 定稿保存
  api.updateCopy(sessionId.value, {
    title: copy.title,
    body: copy.body,
    tags: copy.tagsText.split(/\s+/).filter(Boolean),
  }).catch(() => {})
  // 初始化生成描述
  if (form.content_type === 'video') {
    videoDesc.value = `${copy.title} ${copy.body}`.slice(0, 200)
  }
  step.value = 2
}

// ── Step 2: 生成 ──────────────────────────────────────────────
function onImageChange(file) {
  imageFile.value = file.raw
  imagePreview.value = URL.createObjectURL(file.raw)
}

async function loadAvatars() {
  if (avatars.value.length) return
  try {
    avatars.value = await api.listAvatars()
  } catch { /* ignore */ }
}

async function uploadImageIfNeeded() {
  if (!imageFile.value) return null
  const fd = new FormData()
  fd.append('file', imageFile.value)
  fd.append('name', imageFile.value.name || '驱动图')
  fd.append('category', '创作素材')
  const material = await api.uploadMaterial(fd)
  return material.url || null
}

async function startVideoGen() {
  genStarting.value = true
  genError.value = ''
  try {
    const imageUrl = videoGenType.value === 'image_to_video' ? await uploadImageIfNeeded() : null
    const payload = {
      gen_type: videoGenType.value,
      description: videoDesc.value,
      duration: videoDuration.value,
      resolution: videoResolution.value,
      fps: 24,
      image_url: imageUrl,
    }
    if (videoGenType.value === 'simulation_human' || videoGenType.value === 'digital_human') {
      payload.avatar_id = selectedAvatarId.value || undefined
      payload.avatar_type = videoGenType.value
    }
    await api.startGeneration(sessionId.value, payload)
    step.value = 3
    loadGenerations()
    startPolling()
  } catch (e) {
    genError.value = e.message || '启动生成失败'
  } finally {
    genStarting.value = false
  }
}

async function startImageGen(count) {
  genStarting.value = true
  genError.value = ''
  try {
    await api.startGeneration(sessionId.value, {
      gen_type: count === 1 ? 'cover' : 'images',
      description: `${copy.title} ${copy.body}`.slice(0, 200),
      style: imageStyle.value,
      brand_color: brandColor.value || null,
      brand_hint: brandHint.value || null,
      count,
    })
    step.value = 3
    loadGenerations()
    startPolling()
  } catch (e) {
    genError.value = e.message || '启动生成失败'
  } finally {
    genStarting.value = false
  }
}

// ── Step 3: 状态页 ────────────────────────────────────────────
async function loadGenerations() {
  if (!sessionId.value) return
  try {
    generationTasks.value = await api.getGenerations(sessionId.value)
  } catch { /* ignore */ }
}

function startPolling() {
  stopPolling()
  // 1 秒一刷本地时间，配合 displayProgress 让进度条在生成中平滑推进
  nowTick.value = Date.now()
  progressTicker = setInterval(() => { nowTick.value = Date.now() }, 1000)
  // 3 秒一拉后端
  pollTimer = setInterval(async () => {
    if (!sessionId.value) return
    try {
      const tasks = await api.getGenerations(sessionId.value)
      generationTasks.value = tasks
      if (tasks.every(t => t.status === 'completed' || t.status === 'failed')) {
        stopPolling()
      }
    } catch { /* ignore */ }
  }, 3000)
}

function stopPolling() {
  if (pollTimer) { clearInterval(pollTimer); pollTimer = null }
  if (progressTicker) { clearInterval(progressTicker); progressTicker = null }
}

function goBackToGen() {
  stopPolling()
  step.value = 2
}

const materialCache = ref({}) // { [materialId]: { url, type, name } }

async function previewGeneration(gen) {
  const ids = gen.result?.material_ids || []
  if (!ids.length) {
    if (gen.result?.video_url) window.open(gen.result.video_url, '_blank')
    return
  }
  // 内联展示：逐条拉取素材 url
  gen._previewing = true
  try {
    for (const mid of ids) {
      if (!materialCache.value[mid]) {
        const m = await api.getMaterial(mid)
        materialCache.value[mid] = {
          url: m.url,
          type: m.type, // 'video' | 'image' | 'text'
          name: m.name,
          thumbnail_url: m.thumbnail_url,
        }
      }
    }
    gen._previewOpen = !gen._previewOpen
  } catch (e) {
    ElMessage.error('预览加载失败：' + (e.message || ''))
  } finally {
    gen._previewing = false
  }
}

async function regenerateWith(gen) {
  genStarting.value = true
  statusError.value = ''
  try {
    const params = {
      gen_type: gen.gen_type,
      ...(gen.input_params || {}),
    }
    await api.startGeneration(sessionId.value, params)
    loadGenerations()
  } catch (e) {
    statusError.value = e.message || '重新生成失败'
  } finally {
    genStarting.value = false
    startPolling()
  }
}

async function finishCreation() {
  completing.value = true
  statusError.value = ''
  try {
    const res = await api.completeSession(sessionId.value)
    ElMessage.success(`创作完成！产出 ${res.materials?.length || 0} 个素材`)
    router.push({ path: '/publish', query: { withSession: sessionId.value } })
  } catch (e) {
    statusError.value = e.message || '完成失败'
  } finally {
    completing.value = false
  }
}

// ── 路由守卫：离开页面前自动保存草稿 ──────────────────────────
onBeforeRouteLeave(async (_to, _from, next) => {
  if (sessionId.value) {
    await doSaveDraft()
  }
  next()
})

// ── 浏览器关闭/刷新：尽力保存草稿 ────────────────────────────
function onBeforeUnload() {
  if (sessionId.value && !savingDraft) {
    // 使用 keepalive fetch 在页面关闭时发送请求
    const data = collectDraftData()
    fetch(`/api/create/${sessionId.value}/save-draft`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
      keepalive: true,
    })
  }
}

// ── 生命周期 ──────────────────────────────────────────────────
onMounted(async () => {
  window.addEventListener('beforeunload', onBeforeUnload)

  // 检查是否有恢复参数
  if (route.query.resume) {
    try {
      const session = await api.getSession(parseInt(route.query.resume))
      if (session && session.status !== 'completed') {
        await resumeDraft(session)
        return
      }
    } catch { /* ignore */ }
  }

  if (route.query.platform) {
    form.platforms = [route.query.platform]
  }

  // 加载草稿列表
  await loadDrafts()
  // 如果没有活跃 session 且有草稿，显示草稿列表
  if (!sessionId.value && route.query.resume === undefined) {
    showDraftList.value = true
  }
})

onBeforeUnmount(() => {
  stopPolling()
  clearTimeout(saveTimer)
  window.removeEventListener('beforeunload', onBeforeUnload)
  // 离开时保存草稿
  if (sessionId.value) {
    // 立即保存（非异步等待）
    const data = collectDraftData()
    api.saveDraft(sessionId.value, data).catch(() => {})
  }
})
</script>

<style scoped>
.create-wizard { max-width: 960px; margin: 0 auto; }
.steps { margin: 24px 0 32px; }
.wizard-toolbar { display: flex; justify-content: flex-start; padding: 8px 0 0 4px; }
.step-card {
  background: #fff;
  border-radius: 8px;
  padding: 24px;
  box-shadow: 0 1px 4px rgba(0,0,0,0.08);
}
.type-radio { margin-bottom: 20px; }
.input-form { margin-top: 12px; }

/* 草稿列表 */
.draft-list-card { min-height: 200px; }
.draft-list-header {
  display: flex; justify-content: space-between; align-items: center;
  margin-bottom: 20px; padding-bottom: 12px; border-bottom: 1px solid #eee;
}
.draft-list-header h3 { margin: 0; }
.empty-drafts { text-align: center; color: #999; padding: 60px 0; }
.draft-item {
  display: flex; justify-content: space-between; align-items: center;
  padding: 14px 16px; border: 1px solid #eee; border-radius: 8px;
  margin-bottom: 10px; transition: background 0.2s;
}
.draft-item:hover { background: #f9fafb; }
.draft-info { display: flex; align-items: center; gap: 12px; flex: 1; min-width: 0; }
.draft-keywords { font-weight: 600; font-size: 15px; max-width: 260px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.draft-time { color: #999; font-size: 13px; margin-left: auto; }
.draft-actions { display: flex; gap: 8px; margin-left: 16px; flex-shrink: 0; }

/* Step 1 左右分栏 */
.split-layout { display: flex; gap: 20px; min-height: 520px; }
.chat-panel { width: 38%; display: flex; flex-direction: column; border-right: 1px solid #eee; padding-right: 16px; }
.editor-panel { flex: 1; display: flex; flex-direction: column; }
.chat-header, .editor-header { font-weight: 600; margin-bottom: 12px; display: flex; align-items: center; justify-content: space-between; }
.chat-messages {
  flex: 1; overflow-y: auto; border: 1px solid #eee; border-radius: 6px;
  padding: 10px; margin-bottom: 10px; max-height: 280px; background: #fafafa;
}
.msg { margin-bottom: 8px; }
.msg.user .msg-content { background: #1d9bf0; color: #fff; padding: 6px 10px; border-radius: 8px; display: inline-block; max-width: 90%; }
.msg.assistant .msg-content { background: #e8ecf0; padding: 6px 10px; border-radius: 8px; display: inline-block; max-width: 90%; }
.quick-actions { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 10px; }
.chat-input-row { display: flex; gap: 8px; }
.editor-actions { margin-top: auto; padding-top: 16px; display: flex; justify-content: space-between; }
.loading-bubble .msg-content { display: inline-flex !important; align-items: center; gap: 6px; color: #666; }
.loading-spinner {
  display: inline-block; width: 12px; height: 12px;
  border: 2px solid #c8c8c8; border-top-color: #1d9bf0;
  border-radius: 50%; animation: spin 0.8s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }
.step-actions { margin-top: 20px; display: flex; justify-content: space-between; }

/* Step 2 */
.output-form { margin-top: 16px; }
.preview-img { width: 120px; margin-top: 8px; border-radius: 4px; border: 1px solid #ddd; }

/* Step 3 */
.progress-card { background: #f5f7fa; padding: 20px; border-radius: 8px; margin-bottom: 16px; }
.progress-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
.progress-hint { margin-top: 8px; color: #999; font-size: 13px; }
.error-msg { color: #f56c6c; margin-top: 6px; font-size: 13px; }
.gen-item {
  padding: 10px 0; border-bottom: 1px solid #f0f0f0;
}
.gen-item-head {
  display: flex; align-items: center; gap: 12px;
}
.gen-time { color: #999; font-size: 12px; margin-left: auto; }
.gen-actions { display: flex; gap: 6px; }
.gen-preview {
  margin-top: 10px; padding: 12px; background: #fafafa; border-radius: 8px;
  display: flex; flex-wrap: wrap; gap: 12px;
}
.preview-block { max-width: 320px; }
.preview-name { font-size: 12px; color: #666; margin-bottom: 4px; }
.preview-media {
  max-width: 300px; max-height: 220px; border-radius: 6px; background: #000;
}
.preview-link { font-size: 13px; color: #409eff; }
.preview-empty { font-size: 12px; color: #999; }
.empty { color: #999; padding: 20px 0; }
.cost-tag {
  font-size: 12px;
  color: #e6a23c;
  white-space: nowrap;
  padding: 2px 8px;
  background: #fdf6ec;
  border: 1px solid #faecd8;
  border-radius: 4px;
}
</style>
