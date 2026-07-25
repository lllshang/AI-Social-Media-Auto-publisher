<template>
  <div class="create-wizard">
    <h2>内容创作</h2>

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
      <div class="editor-panel">
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
            <el-select v-model="videoDuration">
              <el-option :value="5" label="5秒" />
              <el-option :value="8" label="8秒" />
              <el-option :value="10" label="10秒" />
            </el-select>
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

        <el-button type="primary" :loading="genStarting" @click="startImageGen(1)">生成封面</el-button>

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
          :percentage="activeTask.progress"
          :stroke-width="16"
          :text-inside="true"
          :status="activeTask.status === 'running' ? '' : undefined"
        />
        <div v-if="activeTask.status === 'failed'" class="error-msg">
          {{ activeTask.error_message }}
        </div>
        <div class="progress-hint">
          {{ activeTask.status === 'running' ? '预计还需 2 分钟...' : '' }}
        </div>
      </div>

      <el-divider />

      <!-- 生成历史 -->
      <h4>生成历史</h4>
      <div v-if="generationTasks.length === 0" class="empty">暂无生成记录</div>
      <div v-for="gen in sortedGenerations" :key="gen.id" class="gen-item">
        <span>{{ genTypeLabel(gen.gen_type) }}</span>
        <el-tag size="small" :type="gen.status === 'completed' ? 'success' : gen.status === 'failed' ? 'danger' : gen.status === 'running' ? 'warning' : 'info'">
          {{ gen.status === 'pending' ? '队列中' : gen.status === 'running' ? `${gen.progress}%` : gen.status === 'completed' ? '已完成' : '失败' }}
        </el-tag>
        <span class="gen-time">{{ formatTime(gen.created_at) }}</span>
        <div class="gen-actions">
          <el-button v-if="gen.status === 'completed' && gen.result?.material_ids?.length" size="small" @click="previewGeneration(gen)">预览</el-button>
          <el-button size="small" @click="regenerateWith(gen)">重新生成</el-button>
          <el-button
            v-if="gen.status === 'completed' && gen.result?.material_ids?.length"
            :type="isSelected(gen) ? 'primary' : 'default'"
            size="small"
            @click="toggleSelect(gen)"
          >{{ isSelected(gen) ? '已选定' : '选定' }}</el-button>
        </div>
      </div>

      <div class="step-actions">
        <el-button @click="goBackToGen">← 返回生成</el-button>
        <el-button type="primary" size="large" :loading="completing" :disabled="selectedGenIds.length === 0" @click="finishCreation">
          选定产出 → 完成创作
        </el-button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
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

// ── 状态 ──────────────────────────────────────────────────────
const step = ref(0)
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

const generationTasks = ref([])
const selectedGenIds = ref([])
let pollTimer = null

// ── 计算属性 ──────────────────────────────────────────────────
const canStart = computed(() => form.keywords.trim())

const activeTask = computed(() =>
  generationTasks.value.find(t => t.status === 'pending' || t.status === 'running') || null
)

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

// ── Step 0: 开始创作 ──────────────────────────────────────────
async function startSession() {
  starting.value = true
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
    // 自动生成初始文案
    await generateInitialCopy()
  } catch (e) {
    ElMessage.error(e.message || '创建失败')
  } finally {
    starting.value = false
  }
}

// ── Step 1: 文案 ──────────────────────────────────────────────
async function generateInitialCopy() {
  generatingCopy.value = true
  try {
    const res = await api.generateCopy(sessionId.value)
    copy.title = res.title || ''
    copy.body = res.body || ''
    copy.tagsText = (res.tags || []).join(' ')
    chatMessages.value = [{ role: 'assistant', content: `已根据你的输入生成初稿：「${copy.title}」` }]
  } catch (e) {
    ElMessage.error(e.message || '生成文案失败')
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
    ElMessage.error(e.message || '润色失败')
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
  const label = quickActions.find(a => a.key === action)?.label || action
  chatMessages.value.push({ role: 'user', content: `[${label}]` })

  try {
    const res = await api.polishCopy(sessionId.value, { quick_action: action })
    copy.title = res.title || ''
    copy.body = res.body || ''
    copy.tagsText = (res.tags || []).join(' ')
    chatMessages.value.push({ role: 'assistant', content: `已按「${label}」风格润色` })
  } catch (e) {
    ElMessage.error(e.message || '润色失败')
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
  } catch (e) {
    ElMessage.error(e.message || '启动生成失败')
  } finally {
    genStarting.value = false
  }
}

async function startImageGen(count) {
  genStarting.value = true
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
  } catch (e) {
    ElMessage.error(e.message || '启动生成失败')
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
  pollTimer = setInterval(async () => {
    if (!sessionId.value) return
    try {
      const tasks = await api.getGenerations(sessionId.value)
      generationTasks.value = tasks
      // 全部完成或失败，停止轮询
      if (tasks.every(t => t.status === 'completed' || t.status === 'failed')) {
        stopPolling()
      }
    } catch { /* ignore */ }
  }, 3000)
}

function stopPolling() {
  if (pollTimer) { clearInterval(pollTimer); pollTimer = null }
}

function goBackToGen() {
  stopPolling()
  step.value = 2
}

function previewGeneration(gen) {
  if (gen.result?.video_url) window.open(gen.result.video_url, '_blank')
  else {
    const ids = gen.result?.material_ids || []
    if (ids.length) ElMessage.info(`素材ID: ${ids.join(', ')}，可在素材库中查看`)
  }
}

async function regenerateWith(gen) {
  genStarting.value = true
  try {
    const params = gen.input_params || {}
    await api.startGeneration(sessionId.value, params)
    loadGenerations()
  } catch (e) {
    ElMessage.error(e.message || '重新生成失败')
  } finally {
    genStarting.value = false
    startPolling()
  }
}

async function finishCreation() {
  completing.value = true
  try {
    const res = await api.completeSession(sessionId.value)
    ElMessage.success(`创作完成！产出 ${res.materials?.length || 0} 个素材`)
    // 可选：跳转到发布向导
    router.push({ path: '/publish', query: { withSession: sessionId.value } })
  } catch (e) {
    ElMessage.error(e.message || '完成失败')
  } finally {
    completing.value = false
  }
}

// ── 生命周期 ──────────────────────────────────────────────────
onMounted(() => {
  // 检查是否有 ref 参数（从发布向导跳转过来）
  if (route.query.platform) {
    form.platforms = [route.query.platform]
  }
})

onBeforeUnmount(() => {
  stopPolling()
  clearTimeout(saveTimer)
})
</script>

<style scoped>
.create-wizard { max-width: 960px; margin: 0 auto; }
.steps { margin: 24px 0 32px; }
.step-card {
  background: #fff;
  border-radius: 8px;
  padding: 24px;
  box-shadow: 0 1px 4px rgba(0,0,0,0.08);
}
.type-radio { margin-bottom: 20px; }
.input-form { margin-top: 12px; }

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
  display: flex; align-items: center; gap: 12px;
  padding: 10px 0; border-bottom: 1px solid #f0f0f0;
}
.gen-time { color: #999; font-size: 12px; margin-left: auto; }
.gen-actions { display: flex; gap: 6px; }
.empty { color: #999; padding: 20px 0; }
</style>
