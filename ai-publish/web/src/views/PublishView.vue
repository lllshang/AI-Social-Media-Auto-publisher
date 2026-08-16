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
              v-for="p in availablePlatforms"
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
      <div style="display:flex;gap:12px;align-items:center">
        <el-button type="primary" :disabled="!canGoStep1" @click="step = 1">下一步：生成文案</el-button>
      </div>
      <p class="muted" style="margin-top: 8px">
        如需先由 AI 做更专业的图片 / 视频 / 数字人创作，可在「AI 封面」环节点击「AI 创作新视频」或「AI 创作视频」跳转到内容创作。
      </p>
    </div>

    <!-- Step 1 -->
    <div v-show="step === 1" class="page-card">
      <el-form label-width="100px">
        <el-form-item label="主题">
          <el-input v-model="form.topic" disabled />
          <div style="margin-top: 8px; display: flex; gap: 8px; flex-wrap: wrap; align-items: center">
            <el-button :loading="generating" @click="generateText">AI 生成文案</el-button>
            <el-button
              v-if="can('materials:write')"
              :loading="savingTextMaterial"
              :disabled="!form.title && !form.content"
              @click="saveTextToMaterial"
            >
              保存到素材库
            </el-button>
            <el-button
              type="primary"
              plain
              :disabled="!form.title && !form.content"
              @click="showPolishPanel = !showPolishPanel"
            >
              AI 按指令优化
            </el-button>
          </div>
          <!-- 按指令优化：快捷风格 + 自由指令，无需跳转内容创作 -->
          <div v-if="showPolishPanel" style="margin-top: 10px; padding: 12px; border: 1px dashed var(--el-border-color); border-radius: 8px">
            <div style="display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 10px">
              <el-button
                v-for="qa in QUICK_ACTIONS_LIST"
                :key="qa.key"
                size="small"
                :loading="polishing && polishAction === qa.key"
                @click="quickPolish(qa.key)"
              >{{ qa.label }}</el-button>
            </div>
            <div style="display: flex; gap: 8px">
              <el-input
                v-model="polishInstruction"
                placeholder="输入优化指令，如：缩短到100字 / 第一句改抓人 / 换成活泼语气"
                :disabled="polishing"
                @keyup.enter="doPolish"
              />
              <el-button type="primary" :loading="polishing" :disabled="!polishInstruction.trim()" @click="doPolish">优化</el-button>
            </div>
            <p class="upload-hint" style="margin-top: 8px">
              基于当前标题/正文按你的指令改写，不触发随机生成，也不会跳转到内容创作。
            </p>
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
      <div style="display:flex;gap:12px;align-items:center;flex-wrap:wrap">
        <el-button @click="step = 0">上一步</el-button>
        <el-button :loading="saving" @click="saveDraft">保存草稿</el-button>
        <el-button type="primary" :disabled="!form.title" @click="goAfterText">下一步</el-button>
      </div>
      <el-alert v-if="publishError" type="error" :closable="true" :title="publishError" @close="publishError = ''" show-icon style="margin-top: 12px" />
      <el-alert v-if="draftError" type="error" :closable="true" :title="draftError" @close="draftError = ''" show-icon style="margin-top: 8px" />
    </div>

    <!-- Step 2 -->
    <div v-show="step === 2" class="page-card">
      <template v-if="needsVideoCover">
        <!-- 视频号/小红书视频流程：这一步生成或选择视频封面图（图片素材） -->
        <p class="muted">
          视频封面是从视频内容里抽出的画面，可使用 AI 生成封面图，也可从素材库选择/上传现有图片。
        </p>
        <el-form label-width="90px" style="max-width: 520px; margin-bottom: 12px">
          <el-form-item label="风格">
            <el-select v-model="form.image_style" style="width: 100%">
              <el-option v-for="s in IMAGE_STYLES" :key="s.value" :label="s.label" :value="s.value" />
            </el-select>
          </el-form-item>
          <el-form-item label="品牌色">
            <BrandColorSelect v-model="form.brand_color" />
          </el-form-item>
          <el-form-item label="品牌说明">
            <el-input v-model="form.brand_hint" placeholder="可选" />
          </el-form-item>
        </el-form>
        <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap">
          <el-button size="small" :loading="previewingPrompt" @click="previewCoverPrompt">预览 Prompt</el-button>
          <el-button type="primary" :loading="generatingImage" @click="generateCover">生成封面图</el-button>
          <el-button v-if="coverPreview" @click="generateCover">重新生成</el-button>
          <el-upload
            :show-file-list="false"
            :http-request="uploadCoverImage"
            accept="image/*"
          >
            <el-button>上传封面图</el-button>
          </el-upload>
          <el-button @click="skipCover">跳过，稍后选手动素材</el-button>
        </div>
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
        <div style="margin-top: 16px; display:flex;gap:12px;align-items:center">
          <el-button @click="step = 1">上一步</el-button>
          <el-button :loading="saving" @click="saveDraft">保存草稿</el-button>
          <el-button type="primary" @click="step = 3">下一步：选择视频</el-button>
        </div>
      </template>
      <template v-else-if="isVideo">
        <!-- 其它视频平台（无视频封面需求）：跳过封面步骤，step=2 实际为视频素材预览 -->
        <p class="muted">
          视频素材可以从素材库选择已有视频、上传本地视频，或前往「内容创作」AI生成。
        </p>
        <div style="display:flex;gap:12px;align-items:center">
          <el-button @click="step = 1">上一步</el-button>
          <el-button :loading="saving" @click="saveDraft">保存草稿</el-button>
          <el-button type="primary" @click="step = 3">下一步：选择视频</el-button>
          <el-button type="primary" plain @click="goToCreate">AI 创作新视频 →</el-button>
        </div>
        <div v-if="videoPreview" class="video-preview" style="margin-top: 16px">
          <video :src="videoPreview" controls style="max-width: 600px; max-height: 400px"></video>
        </div>
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
            <BrandColorSelect v-model="form.brand_color" />
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
      <el-alert v-if="publishError" type="error" :closable="true" :title="publishError" @close="publishError = ''" show-icon style="margin-top: 12px" />
    </div>

    <!-- Step 3 -->
    <div v-show="step === 3" class="page-card">
      <el-form label-width="100px">
        <el-form-item :label="isVideo ? '视频素材' : '图片素材'">
          <el-select
            v-model="materialPickerValue"
            :multiple="!isVideo"
            :placeholder="isVideo ? '选择视频' : '选择图片'"
            style="width: 100%"
            clearable
            @change="onMaterialPickerChange"
            @clear="onMaterialClear"
          >
            <el-option
              v-for="m in selectableMaterials"
              :key="m.id"
              :label="`#${m.id} ${m.name || '未命名'} [${m.category || '默认'}]`"
              :value="m.id"
            />
          </el-select>
          <el-button
            v-if="hasMaterialSelected"
            style="margin-top: 8px"
            type="danger"
            plain
            @click="clearMaterialSelection"
          >删除当前素材（可重新选择/上传）</el-button>
          <el-upload
            v-if="!isVideo"
            :show-file-list="false"
            :http-request="uploadImage"
            accept="image/*"
            style="margin-top: 8px"
          >
            <el-button>上传新图片</el-button>
          </el-upload>
          <el-button v-if="!isVideo" style="margin-top: 8px" :loading="generatingImageInStep3" @click="showStep3ImageGen = true">AI 生成图片</el-button>
          <el-upload
            v-else
            :show-file-list="false"
            :http-request="uploadVideo"
            accept="video/mp4,video/quicktime,video/*"
            style="margin-top: 8px"
          >
            <el-button>上传新视频</el-button>
          </el-upload>
          <el-button v-if="isVideo" type="primary" plain style="margin-top: 8px" @click="goToCreate">AI 创作视频 →</el-button>
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
      <el-button type="primary" :disabled="!hasMaterialSelected" @click="step = 4">下一步：排期提交</el-button>
      <el-alert v-if="publishError" type="error" :closable="true" :title="publishError" @close="publishError = ''" show-icon style="margin-top: 12px" />
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
      <el-alert v-if="publishError" type="error" :closable="true" :title="publishError" @close="publishError = ''" show-icon style="margin-top: 12px" />
      <el-alert v-if="draftError" type="error" :closable="true" :title="draftError" @close="draftError = ''" show-icon style="margin-top: 8px" />
    </div>

    <!-- Step 3: AI 生成图片 Dialog -->
    <el-dialog v-model="showStep3ImageGen" title="AI 生成图片" width="480px">
      <el-form label-width="90px">
        <el-form-item label="风格">
          <el-select v-model="step3ImageStyle" style="width: 100%">
            <el-option v-for="s in IMAGE_STYLES" :key="s.value" :label="s.label" :value="s.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="品牌色">
          <BrandColorSelect v-model="step3ImageBrandColor" />
        </el-form-item>
        <el-form-item label="品牌说明">
          <el-input v-model="step3ImageBrandHint" placeholder="可选" />
        </el-form-item>
        <el-form-item label="数量">
          <el-input-number v-model="step3ImageCount" :min="1" :max="4" />
        </el-form-item>
      </el-form>
      <template #footer>
        <span class="cost-tag" style="margin-right: auto">预估 ¥{{ step3ImageCostEstimate }}</span>
        <el-button @click="showStep3ImageGen = false">取消</el-button>
        <el-button type="primary" :loading="generatingImageInStep3" @click="generateImageInStep3">生成</el-button>
      </template>
    </el-dialog>

  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { api } from '@/api'
import {
  platformsForRuntime,
  platformCoverRatio,
  platformLabel,
  platformLoginHint,
  platformVideoCoverRatio,
  platformVideoHint,
} from '@/constants/platforms'
import BrandColorSelect from '@/components/BrandColorSelect.vue'
import { IMAGE_STYLES, normalizeImageStyle } from '@/constants/imageStyles'
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
const publishError = ref('')
const draftError = ref('')

// 切换步骤时清除错误
watch(step, () => {
  publishError.value = ''
  draftError.value = ''
})
const savingTextMaterial = ref(false)
const lastTextRecordId = ref(null)
const previewingPrompt = ref(false)
const saving = ref(false)
const promptPreview = reactive({ prompt_zh: '', prompt_en: '', negative_prompt: '' })
const requireReview = ref(false)
const runtime = ref({ bilibili_enabled: false })
const availablePlatforms = computed(() => platformsForRuntime(runtime.value))
const coverPreview = ref('')
const videoPreview = ref('')
const videoPreviewUrl = ref('')

// Step 3 inline AI 生成
const showStep3ImageGen = ref(false)
const generatingImageInStep3 = ref(false)
const step3ImageStyle = ref('default')
const step3ImageBrandColor = ref('')
const step3ImageBrandHint = ref('')
const step3ImageCount = ref(1)
const step3ImageCostEstimate = computed(() => (step3ImageCount.value * 0.02).toFixed(2))

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
const currentPlatform = computed(() => availablePlatforms.value.find((p) => p.value === form.platform))
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

// 单选视频 / 多选图片 共用一个 v-model：
// - isVideo=true 时，下拉期望单值；数据内部仍用数组 form.material_ids
// - isVideo=false 时，直接是数组
// 是否已选素材：视频看 form.material_ids 数组首元素；图文看长度
const hasMaterialSelected = computed(() => {
  if (isVideo.value) {
    const arr = Array.isArray(form.material_ids) ? form.material_ids : []
    return Boolean(arr[0])
  }
  return Array.isArray(form.material_ids) && form.material_ids.length > 0
})

const materialPickerValue = computed({
  get() {
    if (isVideo.value) {
      const arr = Array.isArray(form.material_ids) ? form.material_ids : []
      return arr[0] ?? null
    }
    return Array.isArray(form.material_ids) ? form.material_ids : []
  },
  set(val) {
    if (isVideo.value) {
      form.material_ids = val ? [val] : []
    } else if (Array.isArray(val)) {
      form.material_ids = val
    } else if (val == null) {
      form.material_ids = []
    } else {
      form.material_ids = [val]
    }
  },
})

function onMaterialPickerChange(val) {
  // 兜底：某些 element-plus 版本写回 v-model 时只更新 set，跳过 get，
  // 这里再强制把 form.material_ids 与 picker 一致，确保"下一步"按钮可用。
  if (isVideo.value) {
    form.material_ids = val ? [val] : []
  }
}

// 用户点下拉框自带的清空（X）按钮时触发
function onMaterialClear() {
  form.material_ids = []
  videoPreviewUrl.value = ''
  coverPreview.value = ''
  form.cover_material_id = null
}

// 显式"删除"按钮：清空已选素材，便于重新选择 / 上传 / 创作
function clearMaterialSelection() {
  form.material_ids = []
  videoPreviewUrl.value = ''
  coverPreview.value = ''
  form.cover_material_id = null
  ElMessage.info('已清空当前素材，可重新选择 / 上传 / AI 创作')
}

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
  if (template.image_style) form.image_style = normalizeImageStyle(template.image_style)
  if (template.brand_color) form.brand_color = template.brand_color
  if (template.brand_hint) form.brand_hint = template.brand_hint
  loadAccounts()
}

async function loadBase() {
  runtime.value = await api.getRuntimeInfo()
  const mats = await api.listMaterials()
  materials.value = mats
  await Promise.all([loadAccounts(), loadTemplates()])
}

async function onPlatformChange() {
  form.account_id = null
  if (form.platform === 'bilibili') {
    form.content_type = 'video'
    if (!form.bilibili_tid) {
      form.bilibili_tid = 21
    }
  }
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
    draftError.value = e.message || '保存失败'
  } finally {
    savingTextMaterial.value = false
  }
}

async function generateText() {
  generating.value = true
  publishError.value = ''
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
    publishError.value = e.message || '文案生成失败'
  } finally {
    generating.value = false
  }
}

// ── AI 按指令优化（不跳转内容创作）─────────────────────────────
const QUICK_ACTIONS_LIST = [
  { key: 'shorten', label: '缩短' },
  { key: 'expand', label: '扩写' },
  { key: 'humorous', label: '变幽默' },
  { key: 'add_emoji', label: '加 Emoji' },
  { key: 'formal', label: '变正式' },
  { key: 'bilibili_style', label: 'B站风格' },
  { key: 'xiaohongshu_style', label: '小红书风格' },
  { key: 'douyin_style', label: '抖音风格' },
  {
    key: 'detox',
    label: '去 AI 味',
    // 反 AI 腔：固化成 instruction 走后端自由指令通道（后端 QUICK_ACTIONS 无 detox 键）
    instruction:
      '请去掉这篇文案的"AI 腔"，改写成真人博主自然口播/分享的感觉。具体要求：' +
      '1）删掉并禁止出现套话和空话，如"首先/其次/总而言之/在这个XX的时代/值得一提的是/不容忽视/解锁/赋能/震撼/深度/搭建/利器/一站式/全方位/综上所述"等；' +
      '2）禁止"三段式排比+总结句"的模板结构，不要每段的最后一句都来一句升华；' +
      '3）多用口语短句、第一人称（我/咱们）、真实细节和具体场景，允许适度口语化甚至小瑕疵；' +
      '4）保留原意、核心信息和平台风格，不要加 emoji 除非原本就有；' +
      '5）读起来要像一个有经验的人在跟朋友聊，而不是机器生成的营销稿。',
  },
]
const showPolishPanel = ref(false)
const polishInstruction = ref('')
const polishing = ref(false)
const polishAction = ref('')

async function _runPolish(payload, actionKey = '') {
  if (!form.title && !form.content) return ElMessage.warning('请先生成或填写文案')
  polishing.value = true
  polishAction.value = actionKey
  publishError.value = ''
  try {
    const res = await api.polishText({
      title: form.title,
      body: form.content,
      tags: form.tagsText ? form.tagsText.split(/[,，]/).map((t) => t.trim()).filter(Boolean) : [],
      platform: form.platform,
      content_type: form.content_type,
      ...payload,
    })
    form.title = res.title || form.title
    form.content = res.body || form.content
    form.tagsText = (res.tags || []).join(',')
    ElMessage.success('已按指令优化文案')
  } catch (e) {
    publishError.value = e.message || '文案优化失败'
  } finally {
    polishing.value = false
    polishAction.value = ''
  }
}

function quickPolish(key) {
  const item = QUICK_ACTIONS_LIST.find((q) => q.key === key)
  polishInstruction.value = ''
  // 带 instruction 的项（如"去 AI 味"）走自由指令通道，否则走 quick_action 快捷键
  if (item && item.instruction) {
    _runPolish({ instruction: item.instruction }, key)
  } else {
    _runPolish({ quick_action: key }, key)
  }
}

function doPolish() {
  const instruction = polishInstruction.value.trim()
  if (!instruction) return
  _runPolish({ instruction })
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
    publishError.value = e.message || '预览失败'
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
    publishError.value = e.message || '封面生成失败'
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
    publishError.value = e.message || '封面生成失败'
  } finally {
    generatingImage.value = false
  }
}

function skipCover() {
  step.value = 3
}

function goToCreate() {
  // 把当前已选的平台/账号带给创作视图，创作完成后可原样带回来，避免账号被重置
  const q = { ref: 'publish', platform: form.platform }
  if (form.account_id) q.account = form.account_id
  router.push({ path: '/create', query: q })
}

async function onVideoGenResult(res) {
  const mat = res.materials?.[0]
  if (!mat) return
  await loadBase()
  form.material_ids = [mat.id]
  videoPreview.value = mat.url || ''
  videoPreviewUrl.value = mat.url || ''
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

async function generateImageInStep3() {
  generatingImageInStep3.value = true
  showStep3ImageGen.value = false
  try {
    const res = await api.generateImage({
      topic: form.topic,
      platform: form.platform,
      ratio: coverRatio.value,
      count: step3ImageCount.value,
      style: step3ImageStyle.value,
      brand_color: step3ImageBrandColor.value || null,
      brand_hint: step3ImageBrandHint.value || null,
    })
    const mats = res.materials || []
    if (!mats.length) throw new Error('未返回图片素材')
    await loadBase()
    form.material_ids = mats.map((m) => m.id)
    ElMessage.success(`已生成 ${mats.length} 张图片`)
  } catch (e) {
    publishError.value = e.message || '图片生成失败'
  } finally {
    generatingImageInStep3.value = false
  }
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
    draftError.value = e.message || '保存失败'
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
    if (e !== 'cancel') draftError.value = e.message || '删除失败'
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

async function applyRouteDefaults() {
  const platform = route.query.platform
  const contentType = route.query.content_type
  const topic = route.query.topic
  // route 上原始期望的 account id(用于最后兜底, 不被 onPlatformChange 清空)
  const wantedAccountId = route.query.account ? Number(route.query.account) : null
  // 注意: PLATFORMS 是 computed(availablePlatforms), 在 onMounted 早期 runtime 还没加载时
  // 仍然是空数组, 不能用它做白名单校验。直接信任 route.query 值, 留给 onPlatformChange
  // 与后续 listAccounts 自动校验即可。
  if (platform) {
    if (form.platform !== platform) {
      form.platform = platform
      // 平台切换会清空 form.account_id 并重载 accounts 列表
      await onPlatformChange()
    }
  }
  if (contentType === 'video' || contentType === 'note') {
    form.content_type = contentType
  }
  if (typeof topic === 'string' && topic.trim()) {
    form.topic = topic.trim()
  }
  // 兜底: route 上带的 account 必须被读取, 否则从创作视图回来会被重置。
  // 必须放在 onPlatformChange() 之后(它会清空 form.account_id)。
  if (wantedAccountId) {
    form.account_id = wantedAccountId
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

async function loadFromSession() {
  const sessionId = route.query.withSession
  if (!sessionId) return
  try {
    const session = await api.getSession(Number(sessionId))
    if (session.final_copy) {
      form.title = session.final_copy.title || ''
      form.content = session.final_copy.body || ''
      form.tagsText = (session.final_copy.tags || []).join(' ')
    }
    // session.output_material_ids 是混合 ID 列表：可能包括文案、封面、数字人口播图、视频等，
    // 不能整组赋给 form.material_ids（视频是单选，会把文案/封面也当成视频保存）。
    // 按当前已加载的 materials 拆分类别，分别填到视频或封面字段。
    const rawIds = session.output_material_ids || []
    const byId = Object.fromEntries(materials.value.map((m) => [m.id, m]))
    const videos = rawIds.filter((id) => byId[id]?.type === 'video')
    const images = rawIds.filter((id) => byId[id]?.type === 'image')
    if (videos.length) {
      // 视频流程是单选，先取第一个作为预选；其余的素材依然在素材库里可手动切换。
      form.material_ids = [videos[0]]
      const firstVideo = byId[videos[0]]
      if (firstVideo?.url) videoPreviewUrl.value = firstVideo.url
    }
    if (images.length && !form.cover_material_id) {
      form.cover_material_id = images[0]
      const cover = byId[images[0]]
      if (cover?.url && !coverPreview.value) coverPreview.value = cover.url
    }
    // 平台/账号已由 applyRouteDefaults 处理（避免重复调用 onPlatformChange 二次清空 account）
    // 创作视图回来后直接跳到「素材确认」步骤（视频流程是 step=3，图文是 step=2），
    // 让用户看到刚生成的视频，而不是又落到 step=0「主题账号」。
    if (videos.length || images.length) {
      step.value = isVideo.value ? 3 : 2
    }
    const totalMats = videos.length + images.length
    const videoLabel = videos.length ? `${videos.length} 个视频` : ''
    const imageLabel = images.length ? `${images.length} 张图` : ''
    const detail = [videoLabel, imageLabel].filter(Boolean).join(' + ')
    ElMessage.success(
      detail
        ? `已从创作结果加载文案和 ${detail}`
        : `已从创作结果加载文案`,
    )
  } catch { /* ignore */ }
}

onMounted(async () => {
  await loadFeatures()
  await applyRouteDefaults()
  await loadBase()
  await applyTemplateFromRoute()
  await loadFromSession()
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
