<template>
  <div>
    <div class="page-header">
      <h2 class="page-title">{{ pageTitle }}</h2>
      <el-button v-if="draftId" type="danger" plain @click="removeDraft">删除草稿</el-button>
    </div>
    <el-steps :active="step" finish-status="success" align-center style="margin-bottom: 24px">
      <el-step title="主题账号" />
      <el-step title="AI 文案" />
      <el-step :title="videoCoverStepTitle" />
      <el-step title="素材确认" />
      <el-step title="排期提交" />
    </el-steps>

    <!-- Step 0 -->
    <div v-show="step === 0" class="page-card">
      <el-form label-width="100px">
        <el-form-item label="内容模板">
          <el-select
            v-model="selectedTemplateId"
            clearable
            filterable
            placeholder="可选：从模板快速填充"
            style="width: 100%"
            @change="applyTemplate"
          >
            <el-option
              v-for="t in contentTemplates"
              :key="t.id"
              :label="`${t.name}（${t.industry}）`"
              :value="t.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="发布平台">
          <el-select v-model="form.platform" style="width: 100%" @change="onPlatformChange">
            <el-option
              v-for="p in PLATFORMS"
              :key="p.value"
              :label="p.experimental ? `${p.label}（实验）` : p.label"
              :value="p.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="内容类型">
          <el-radio-group v-model="form.content_type">
            <el-radio v-for="ct in currentContentTypes" :key="ct.value" :value="ct.value">{{ ct.label }}</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="平台账号">
          <el-select v-model="form.account_id" placeholder="选择账号" style="width: 100%">
            <el-option v-for="a in accounts" :key="a.id" :label="`${a.account_name} (${a.status})`" :value="a.id" />
          </el-select>
          <p v-if="!accounts.length" class="muted">暂无账号，请先在「平台账号」页创建并登录。</p>
        </el-form-item>
        <el-form-item label="内容主题">
          <el-input v-model="form.topic" placeholder="如：春茶上新" />
        </el-form-item>
        <el-form-item v-if="isBilibili" label="投稿分区">
          <el-select v-model="form.bilibili_tid" style="width: 100%">
            <el-option v-for="t in BILIBILI_TIDS" :key="t.value" :label="`${t.label} (${t.value})`" :value="t.value" />
          </el-select>
        </el-form-item>
        <p v-if="isVideo" class="muted">{{ platformVideoHint(form.platform) }}</p>
        <p v-if="isBilibili" class="muted">{{ platformLoginHint(form.platform) }}</p>
      </el-form>
      <el-button type="primary" :disabled="!canGoStep1" @click="step = 1">下一步：生成文案</el-button>
    </div>

    <!-- Step 1 -->
    <div v-show="step === 1" class="page-card">
      <el-form label-width="100px">
        <el-form-item label="主题">
          <el-input v-model="form.topic" disabled />
          <div style="margin-top: 8px; display: flex; gap: 8px; flex-wrap: wrap">
            <el-button :loading="generating" @click="generateText">AI 生成文案</el-button>
            <el-button
              v-if="can('materials:write')"
              :loading="savingTextMaterial"
              :disabled="!form.title && !form.content"
              @click="saveTextToMaterial"
            >
              保存到素材库
            </el-button>
          </div>
        </el-form-item>
        <el-form-item label="标题">
          <el-input v-model="form.title" />
        </el-form-item>
        <el-form-item label="正文">
          <el-input v-model="form.content" type="textarea" :rows="5" />
        </el-form-item>
        <el-form-item label="标签">
          <el-input v-model="form.tagsText" placeholder="逗号分隔" />
        </el-form-item>
        <el-form-item v-if="!isVideo || needsVideoCover" :label="isChannelsVideo ? '短标题' : '封面文案'">
          <el-input
            v-model="form.cover_text"
            :placeholder="isChannelsVideo ? '视频号短标题 6-16 字，可选' : isXhsVideo ? '用于生成视频封面，可选' : ''"
          />
        </el-form-item>
        <el-form-item label="评论引导">
          <el-input v-model="form.comment_guide" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <el-button @click="step = 0">上一步</el-button>
      <el-button :loading="saving" @click="saveDraft">保存草稿</el-button>
      <el-button type="primary" :disabled="!form.title" @click="goAfterText">下一步</el-button>
    </div>

    <!-- Step 2 -->
    <div v-show="step === 2" class="page-card">
      <template v-if="needsVideoCover">
        <p class="muted">
          {{ platformLabel(form.platform) }}视频可设置 {{ videoCoverRatio }} 封面（可选）。未设置时由平台自动截取；也可跳过，稍后上传。
        </p>
        <el-button type="primary" :loading="generatingImage" @click="generateVideoCover">AI 生成视频封面</el-button>
        <el-button v-if="coverPreview" @click="generateVideoCover">重新生成</el-button>
        <el-upload :show-file-list="false" :http-request="uploadCoverImage" accept="image/*" style="display: inline-block; margin-left: 8px">
          <el-button>上传封面图</el-button>
        </el-upload>
        <el-button @click="skipVideoCover">跳过封面</el-button>
        <div v-if="coverPreview" class="cover-preview">
          <div class="cover-preview-frame" :style="coverPreviewFrameStyle">
            <img :src="coverPreview" class="cover-preview-img" alt="封面预览" />
          </div>
        </div>
        <div style="margin-top: 16px">
          <el-button @click="step = 1">上一步</el-button>
          <el-button :loading="saving" @click="saveDraft">保存草稿</el-button>
          <el-button type="primary" @click="step = 3">下一步：选择视频</el-button>
        </div>
      </template>
      <template v-else-if="isVideo">
        <p class="muted">当前平台视频发布无需单独封面，可直接选择视频素材。</p>
        <el-button @click="step = 1">上一步</el-button>
        <el-button type="primary" @click="step = 3">下一步：选择视频</el-button>
      </template>
      <template v-else>
        <p class="muted">将根据主题与封面文案生成 {{ coverRatio }} {{ platformLabel(form.platform) }}封面图。Key 未配置时可跳过，改用手动上传。</p>
        <el-form label-width="90px" style="max-width: 520px; margin-bottom: 12px">
          <el-form-item label="风格">
            <el-select v-model="form.image_style" style="width: 100%">
              <el-option v-for="s in IMAGE_STYLES" :key="s.value" :label="s.label" :value="s.value" />
            </el-select>
          </el-form-item>
          <el-form-item label="品牌色">
            <el-input v-model="form.brand_color" placeholder="可选，如 #2E8B57" />
          </el-form-item>
          <el-form-item label="品牌说明">
            <el-input v-model="form.brand_hint" placeholder="可选" />
          </el-form-item>
        </el-form>
        <el-button size="small" :loading="previewingPrompt" @click="previewCoverPrompt">预览 Prompt</el-button>
        <el-button type="primary" :loading="generatingImage" @click="generateCover">生成封面图</el-button>
        <el-button v-if="coverPreview" @click="generateCover">重新生成</el-button>
        <el-button @click="skipCover">跳过，稍后选手动素材</el-button>
        <div v-if="promptPreview.prompt_zh" class="prompt-preview">
          <p><strong>中文：</strong></p>
          <pre>{{ promptPreview.prompt_zh }}</pre>
          <p v-if="promptPreview.prompt_en"><strong>英文：</strong></p>
          <pre v-if="promptPreview.prompt_en">{{ promptPreview.prompt_en }}</pre>
          <p v-if="promptPreview.negative_prompt"><strong>负面：</strong></p>
          <pre v-if="promptPreview.negative_prompt">{{ promptPreview.negative_prompt }}</pre>
        </div>
        <div v-if="coverPreview" class="cover-preview">
          <div class="cover-preview-frame" :style="coverPreviewFrameStyle">
            <img :src="coverPreview" class="cover-preview-img" alt="封面预览" />
          </div>
        </div>
        <div style="margin-top: 16px">
          <el-button @click="step = 1">上一步</el-button>
          <el-button :loading="saving" @click="saveDraft">保存草稿</el-button>
          <el-button type="primary" @click="step = 3">下一步：确认素材</el-button>
        </div>
      </template>
    </div>

    <!-- Step 3 -->
    <div v-show="step === 3" class="page-card">
      <el-form label-width="100px">
        <el-form-item :label="isVideo ? '视频素材' : '图片素材'">
          <el-select
            v-model="form.material_ids"
            :multiple="!isVideo"
            :placeholder="isVideo ? '选择视频' : '选择图片'"
            style="width: 100%"
          >
            <el-option
              v-for="m in selectableMaterials"
              :key="m.id"
              :label="`#${m.id} ${m.name || '未命名'} [${m.category || '默认'}]`"
              :value="m.id"
            />
          </el-select>
          <el-upload
            v-if="!isVideo"
            :show-file-list="false"
            :http-request="uploadImage"
            accept="image/*"
            style="margin-top: 8px"
          >
            <el-button>上传新图片</el-button>
          </el-upload>
          <el-upload
            v-else
            :show-file-list="false"
            :http-request="uploadVideo"
            accept="video/mp4,video/quicktime,video/*"
            style="margin-top: 8px"
          >
            <el-button>上传新视频</el-button>
          </el-upload>
          <div v-if="videoPreviewUrl" class="cover-preview">
            <video :src="videoPreviewUrl" controls style="max-width: 100%; max-height: 280px" />
          </div>
        </el-form-item>
        <el-form-item v-if="needsVideoCover && form.cover_material_id" label="视频封面">
          <div class="cover-preview-frame cover-preview-frame--small" :style="coverPreviewFrameStyle">
            <img :src="coverPreview" class="cover-preview-img" alt="视频封面预览" />
          </div>
          <p class="muted">封面素材 #{{ form.cover_material_id }}</p>
        </el-form-item>
      </el-form>
      <el-button @click="step = isVideo ? (needsVideoCover ? 2 : 1) : 2">上一步</el-button>
      <el-button :loading="saving" @click="saveDraft">保存草稿</el-button>
      <el-button type="primary" :disabled="!form.material_ids.length" @click="step = 4">下一步：排期提交</el-button>
    </div>

    <!-- Step 4 -->
    <div v-show="step === 4" class="page-card">
      <el-form label-width="120px">
        <el-form-item label="计划发布时间">
          <el-date-picker
            v-model="form.publish_time"
            type="datetime"
            placeholder="可选，留空表示尽快发布"
            style="width: 100%"
          />
          <p class="muted">设置计划时间后，系统将在到点自动发布；也可在任务列表提前手动点「执行」。</p>
        </el-form-item>
        <el-form-item label="摘要">
          <div class="summary">
            <p><strong>平台：</strong>{{ platformLabel(form.platform) }} / {{ contentTypeLabel }}</p>
            <p><strong>标题：</strong>{{ form.title }}</p>
            <p><strong>账号：</strong>{{ accountLabel }}</p>
            <p><strong>素材：</strong>{{ materialSummary }}</p>
            <p v-if="needsVideoCover && form.cover_material_id"><strong>视频封面：</strong>#{{ form.cover_material_id }}</p>
          </div>
        </el-form-item>
      </el-form>
      <el-button @click="step = 3">上一步</el-button>
      <el-button :loading="saving" @click="saveDraft">保存草稿</el-button>
      <el-alert
        v-if="requireReview"
        type="info"
        :closable="false"
        show-icon
        title="内容审核已开启：提交后将进入「待审核」，审核通过后方可发布。"
        style="margin-bottom: 12px"
      />
      <el-button type="primary" :loading="saving" @click="submitPending">
        {{ requireReview ? '提交审核' : '提交待发布' }}
      </el-button>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { api } from '@/api'
import {
  PLATFORMS,
  platformCoverRatio,
  platformLabel,
  platformLoginHint,
  platformVideoCoverRatio,
  platformVideoHint,
} from '@/constants/platforms'
import { IMAGE_STYLES } from '@/constants/imageStyles'
import { BILIBILI_TIDS } from '@/constants/bilibili'
import { usePermission } from '@/composables/usePermission'

const route = useRoute()
const router = useRouter()
const { can } = usePermission()

const accounts = ref([])
const materials = ref([])
const contentTemplates = ref([])
const selectedTemplateId = ref(null)
const step = ref(0)
const draftId = ref(null)
const generating = ref(false)
const generatingImage = ref(false)
const savingTextMaterial = ref(false)
const lastTextRecordId = ref(null)
const previewingPrompt = ref(false)
const saving = ref(false)
const promptPreview = reactive({ prompt_zh: '', prompt_en: '', negative_prompt: '' })
const requireReview = ref(false)
const coverPreview = ref('')
const videoPreviewUrl = ref('')

const form = reactive({
  platform: 'xhs',
  content_type: 'note',
  account_id: null,
  topic: '春茶上新',
  title: '',
  content: '',
  tagsText: '',
  cover_text: '',
  image_style: 'default',
  brand_color: '',
  brand_hint: '',
  comment_guide: '',
  material_ids: [],
  cover_material_id: null,
  publish_time: null,
  bilibili_tid: 21,
})

const isBilibili = computed(() => form.platform === 'bilibili')
const isChannelsVideo = computed(() => form.platform === 'channels' && isVideo.value)
const isVideo = computed(() => form.content_type === 'video')
const isXhsVideo = computed(() => form.platform === 'xhs' && isVideo.value)
const needsVideoCover = computed(() => isXhsVideo.value || isChannelsVideo.value)
const videoCoverRatio = computed(() => platformVideoCoverRatio(form.platform))
const videoCoverStepTitle = computed(() => {
  if (!isVideo.value) return 'AI 封面'
  return needsVideoCover.value ? '视频封面（可选）' : '封面（可跳过）'
})
const currentPlatform = computed(() => PLATFORMS.find((p) => p.value === form.platform))
const currentContentTypes = computed(() => currentPlatform.value?.contentTypes || [])
const coverRatio = computed(() => platformCoverRatio(form.platform))
const activeCoverRatio = computed(() => (needsVideoCover.value ? videoCoverRatio.value : coverRatio.value))
const coverPreviewFrameStyle = computed(() => {
  const parts = activeCoverRatio.value.split(':').map((n) => Number(n))
  if (parts.length === 2 && parts[0] > 0 && parts[1] > 0) {
    return { aspectRatio: `${parts[0]} / ${parts[1]}` }
  }
  return { aspectRatio: '3 / 4' }
})
const contentTypeLabel = computed(() => (isVideo.value ? '视频' : '图文'))

const pageTitle = computed(() => {
  if (draftId.value) return `编辑草稿 #${draftId.value}`
  return `发布向导（${platformLabel(form.platform)}${contentTypeLabel.value}）`
})

function isMaterialSelectable(m) {
  if (m.type === 'image' && ['rejected', 'pending'].includes(m.moderation_status)) {
    return false
  }
  return true
}

const selectableMaterials = computed(() =>
  materials.value.filter((m) => {
    if (!isMaterialSelectable(m)) return false
    return isVideo.value ? m.type === 'video' : m.type === 'image'
  })
)

const accountLabel = computed(() => {
  const acc = accounts.value.find((a) => a.id === form.account_id)
  return acc ? acc.account_name : '-'
})

const materialSummary = computed(() => {
  const ids = Array.isArray(form.material_ids) ? form.material_ids : form.material_ids ? [form.material_ids] : []
  return ids.join(', ') || '-'
})

const canGoStep1 = computed(() => Boolean(form.account_id && form.topic.trim()))

function normalizeMaterialIds() {
  if (isVideo.value) {
    const videoId = Array.isArray(form.material_ids) ? form.material_ids[0] : form.material_ids
    form.material_ids = videoId ? [videoId] : []
  } else if (!Array.isArray(form.material_ids)) {
    form.material_ids = form.material_ids ? [form.material_ids] : []
  }
}

function resolveMaterialIds() {
  normalizeMaterialIds()
  const ids = [...form.material_ids]
  if (needsVideoCover.value && form.cover_material_id && !ids.includes(form.cover_material_id)) {
    ids.push(form.cover_material_id)
  }
  return ids
}

function splitDraftMaterials(task, mats) {
  const ids = task.material_ids || []
  const byId = Object.fromEntries(mats.map((m) => [m.id, m]))
  const videos = ids.filter((id) => byId[id]?.type === 'video')
  const images = ids.filter((id) => byId[id]?.type === 'image')
  form.material_ids = videos.length ? [videos[0]] : ids.slice(0, 1)
  form.cover_material_id = images[0] || null
  if (form.cover_material_id) {
    const cover = byId[form.cover_material_id]
    if (cover?.url) coverPreview.value = cover.url
  }
  const video = byId[form.material_ids[0]]
  if (video?.url) videoPreviewUrl.value = video.url
}

function buildTaskPayload(submit) {
  return {
    title: form.title || form.topic.trim(),
    content: form.content,
    comment_guide: form.comment_guide || null,
    topic: form.topic.trim() || null,
    cover_text: form.cover_text || null,
    wizard_step: step.value,
    tags: form.tagsText.split(',').map((s) => s.trim()).filter(Boolean),
    platform: form.platform,
    account_id: form.account_id,
    content_type: form.content_type,
    material_ids: resolveMaterialIds(),
    publish_time: form.publish_time ? new Date(form.publish_time).toISOString() : null,
    bilibili_tid: isBilibili.value ? form.bilibili_tid : null,
    submit,
  }
}

function inferWizardStep(task) {
  if (task.wizard_step != null && task.wizard_step >= 0 && task.wizard_step <= 4) {
    return task.wizard_step
  }
  if (task.material_ids?.length) return 4
  if (['xhs', 'channels'].includes(task.platform) && task.content_type === 'video' && task.title && task.content) {
    return 2
  }
  if (task.content_type === 'video' && task.title && task.content) return 3
  if (task.title && task.content) return 2
  if (task.title || task.topic) return 1
  return 0
}

async function loadAccounts() {
  const acc = await api.listAccounts(form.platform)
  accounts.value = acc
  if (!acc.find((a) => a.id === form.account_id)) {
    form.account_id = acc.length ? acc[0].id : null
  }
}

async function loadTemplates() {
  try {
    contentTemplates.value = await api.listContentTemplates({
      platform: form.platform || undefined,
    })
  } catch {
    contentTemplates.value = []
  }
}

function applyTemplate(templateId) {
  if (!templateId) return
  const template = contentTemplates.value.find((item) => item.id === templateId)
  if (!template) return
  if (template.platform && PLATFORMS.some((p) => p.value === template.platform)) {
    form.platform = template.platform
  }
  if (template.content_type) {
    form.content_type = template.content_type
  }
  form.topic = template.topic
  if (template.title_hint) {
    form.title = template.title_hint
    if (!form.cover_text) form.cover_text = template.title_hint
  }
  if (template.content_body) form.content = template.content_body
  if (template.tags?.length) form.tagsText = template.tags.join('，')
  if (template.image_style) form.image_style = template.image_style
  if (template.brand_color) form.brand_color = template.brand_color
  if (template.brand_hint) form.brand_hint = template.brand_hint
  loadAccounts()
}

async function loadBase() {
  const mats = await api.listMaterials()
  materials.value = mats
  await Promise.all([loadAccounts(), loadTemplates()])
}

async function onPlatformChange() {
  form.account_id = null
  const types = currentContentTypes.value
  if (types.length && !types.find((t) => t.value === form.content_type)) {
    form.content_type = types[0].value
  }
  if (form.platform === 'bilibili' && !form.bilibili_tid) {
    form.bilibili_tid = 21
  }
  await Promise.all([loadAccounts(), loadTemplates()])
}

function goAfterText() {
  if (needsVideoCover.value) step.value = 2
  else if (isVideo.value) step.value = 3
  else step.value = 2
}

async function loadDraft(id) {
  const task = await api.getTask(id)
  if (task.status !== 'draft') {
    ElMessage.warning('仅 draft 任务可在此编辑')
    router.replace('/tasks')
    return
  }
  draftId.value = task.id
  form.platform = task.platform || 'xhs'
  form.content_type = task.content_type || 'note'
  await loadAccounts()
  form.account_id = task.account_id
  form.topic = task.topic || task.title || form.topic
  form.title = task.title
  form.content = task.content || ''
  form.comment_guide = task.comment_guide || ''
  form.cover_text = task.cover_text || ''
  form.bilibili_tid = task.bilibili_tid || 21
  form.tagsText = (task.tags || []).join(',')
  form.cover_material_id = null
  if (task.content_type === 'video') {
    splitDraftMaterials(task, materials.value)
  } else {
    form.material_ids = task.material_ids || []
    if (form.material_ids.length) {
      const first = materials.value.find((m) => m.id === form.material_ids[0])
      if (first?.url) coverPreview.value = first.url
    }
  }
  form.publish_time = task.publish_time ? new Date(task.publish_time) : null
  step.value = inferWizardStep(task)
}

async function saveTextToMaterial() {
  if (!form.title && !form.content) return ElMessage.warning('请先生成或填写文案')
  savingTextMaterial.value = true
  try {
    await api.saveTextMaterial({
      title: form.title || form.topic,
      content: form.content || '',
      tags: form.tagsText ? form.tagsText.split(/[,，]/).map((t) => t.trim()).filter(Boolean) : [],
      platform: form.platform,
      comment_guide: form.comment_guide || null,
      topic: form.topic,
      ai_record_id: lastTextRecordId.value,
    })
    ElMessage.success('文案已保存到素材库')
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    savingTextMaterial.value = false
  }
}

async function generateText() {
  generating.value = true
  try {
    const res = await api.generateText(form.topic, form.platform, form.content_type)
    form.title = res.title
    form.content = res.content
    form.tagsText = (res.tags || []).join(',')
    form.cover_text = res.cover_text || ''
    form.comment_guide = res.comment_guide || ''
    lastTextRecordId.value = res.record_id || null
    ElMessage.success(`文案已生成 (${res.provider}/${res.model || '-'})`)
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    generating.value = false
  }
}

function imageGeneratePayload(ratio, count = 1) {
  return {
    topic: form.topic,
    platform: form.platform,
    ratio,
    count,
    style: form.image_style,
    cover_text: form.cover_text || null,
    brand_color: form.brand_color || null,
    brand_hint: form.brand_hint || null,
  }
}

async function previewCoverPrompt() {
  if (!form.topic.trim()) return ElMessage.warning('请先填写主题')
  previewingPrompt.value = true
  try {
    const res = await api.buildPrompt({
      kind: 'image',
      platform: form.platform,
      topic: form.topic,
      ratio: needsVideoCover.value ? videoCoverRatio.value : coverRatio.value,
      style: form.image_style,
      cover_text: form.cover_text || null,
      brand_color: form.brand_color || null,
      brand_hint: form.brand_hint || null,
    })
    promptPreview.prompt_zh = res.prompt_zh || res.prompt
    promptPreview.prompt_en = res.prompt_en || ''
    promptPreview.negative_prompt = res.negative_prompt || ''
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    previewingPrompt.value = false
  }
}

async function generateVideoCover() {
  generatingImage.value = true
  try {
    const res = await api.generateImage(imageGeneratePayload(videoCoverRatio.value))
    const mat = res.materials?.[0]
    if (!mat) throw new Error('未返回封面素材')
    await loadBase()
    form.cover_material_id = mat.id
    coverPreview.value = mat.url
    ElMessage.success('视频封面已生成')
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    generatingImage.value = false
  }
}

function skipVideoCover() {
  form.cover_material_id = null
  coverPreview.value = ''
  step.value = 3
}

async function uploadCoverImage({ file }) {
  const res = await api.uploadMaterial(file, {
    name: file.name.replace(/\.[^.]+$/, ''),
    category: '视频封面',
  })
  materials.value.unshift(res)
  form.cover_material_id = res.id
  coverPreview.value = res.url
  ElMessage.success('封面已上传')
}

async function generateCover() {
  generatingImage.value = true
  try {
    const res = await api.generateImage(imageGeneratePayload(coverRatio.value))
    const mat = res.materials?.[0]
    if (!mat) throw new Error('未返回图片素材')
    if (mat.url?.includes('stub') || mat.file_path?.includes('stub')) {
      ElMessage.warning('当前为占位图，请配置文生图 Key 或改用手动上传')
    } else {
      ElMessage.success('封面已生成')
    }
    await loadBase()
    form.material_ids = [mat.id]
    coverPreview.value = mat.url
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    generatingImage.value = false
  }
}

function skipCover() {
  step.value = 3
}

async function uploadImage({ file }) {
  const res = await api.uploadMaterial(file, {
    name: file.name.replace(/\.[^.]+$/, ''),
    category: '发布素材',
  })
  materials.value.unshift(res)
  form.material_ids = [res.id]
  coverPreview.value = res.url
  ElMessage.success('图片已上传')
}

async function uploadVideo({ file }) {
  const res = await api.uploadMaterial(file, {
    name: file.name.replace(/\.[^.]+$/, ''),
    category: '发布素材',
  })
  materials.value.unshift(res)
  form.material_ids = [res.id]
  videoPreviewUrl.value = res.url || ''
  ElMessage.success('视频已上传')
}

async function persistTask(submit) {
  if (!form.account_id) return ElMessage.warning('请选择账号')
  const title = form.title || form.topic.trim()
  if (!title) return ElMessage.warning('请填写标题或主题')
  const materialIds = resolveMaterialIds()
  if (submit && !materialIds.length) {
    return ElMessage.warning(isVideo.value ? '请选择视频素材' : '请选择图片素材')
  }
  if (submit && isVideo.value && !materialIds.some((id) => materials.value.find((m) => m.id === id)?.type === 'video')) {
    return ElMessage.warning('请选择视频素材')
  }

  saving.value = true
  try {
    let task
    const payload = buildTaskPayload(submit)
    payload.title = title
    if (draftId.value) {
      const { submit: _s, ...updatePayload } = payload
      await api.updateTask(draftId.value, updatePayload)
      task = submit ? await api.submitTask(draftId.value) : await api.getTask(draftId.value)
    } else {
      task = await api.createTask(payload)
      if (submit && task.status === 'draft') {
        task = await api.submitTask(task.id)
      }
    }
    if (submit) {
      if (task.status === 'pending_review') {
        ElMessage.success(`任务 #${task.id} 已提交，等待审核`)
        router.push('/reviews')
      } else {
        ElMessage.success(`任务 #${task.id} 已提交待发布`)
        router.push('/tasks')
      }
    } else {
      ElMessage.success(`草稿 #${task.id} 已保存`)
      draftId.value = task.id
      router.replace({ path: '/publish', query: { id: task.id } })
    }
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    saving.value = false
  }
}

function saveDraft() {
  persistTask(false)
}

function submitPending() {
  persistTask(true)
}

async function removeDraft() {
  if (!draftId.value) return
  try {
    await ElMessageBox.confirm(`确定删除草稿 #${draftId.value}？删除后不可恢复。`, '删除草稿', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })
    await api.deleteTask(draftId.value)
    ElMessage.success('草稿已删除')
    router.push('/tasks')
  } catch (e) {
    if (e !== 'cancel') ElMessage.error(e.message || '删除失败')
  }
}

watch(
  () => form.content_type,
  () => {
    form.material_ids = []
    form.cover_material_id = null
    coverPreview.value = ''
    videoPreviewUrl.value = ''
  }
)

watch(
  () => form.material_ids,
  (ids) => {
    if (!isVideo.value) return
    const videoId = Array.isArray(ids) ? ids[0] : ids
    const mat = materials.value.find((m) => m.id === videoId)
    videoPreviewUrl.value = mat?.url || ''
  },
  { deep: true }
)

function applyRouteDefaults() {
  const platform = route.query.platform
  const contentType = route.query.content_type
  if (platform && PLATFORMS.some((p) => p.value === platform)) {
    form.platform = platform
  }
  if (contentType === 'video' || contentType === 'note') {
    form.content_type = contentType
  }
}

async function loadFeatures() {
  try {
    const features = await api.getSystemFeatures()
    requireReview.value = !!features.require_content_review
  } catch {
    requireReview.value = false
  }
}

async function applyTemplateFromRoute() {
  const templateId = Number(route.query.template_id)
  if (!templateId) return
  try {
    const template = await api.getContentTemplate(templateId)
    const exists = contentTemplates.value.some((item) => item.id === template.id)
    if (!exists) contentTemplates.value = [template, ...contentTemplates.value]
    selectedTemplateId.value = template.id
    applyTemplate(template.id)
  } catch {
    // ignore invalid template id
  }
}

onMounted(async () => {
  await loadFeatures()
  applyRouteDefaults()
  await loadBase()
  await applyTemplateFromRoute()
  const id = route.query.id
  if (id) await loadDraft(Number(id))
})
</script>

<style scoped>
.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}
.page-header .page-title {
  margin: 0;
}
.muted {
  color: #888;
  font-size: 13px;
  margin: 8px 0;
}
.cover-preview {
  margin-top: 16px;
  display: flex;
  justify-content: center;
}
.cover-preview-frame {
  width: min(280px, 100%);
  max-height: 420px;
  background: #f5f7fa;
  border-radius: 8px;
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
}
.cover-preview-frame--small {
  width: min(160px, 100%);
  max-height: 240px;
}
.cover-preview-img {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: contain;
}
.prompt-preview {
  margin-top: 12px;
  background: #f5f7fa;
  padding: 10px 12px;
  border-radius: 6px;
  font-size: 13px;
}
.prompt-preview pre {
  white-space: pre-wrap;
  margin: 4px 0 10px;
}
.summary p {
  margin: 4px 0;
}
</style>
