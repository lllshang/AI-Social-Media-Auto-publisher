<template>
  <div>
    <div class="toolbar">
      <h2 class="page-title">素材库</h2>
      <div v-if="can('materials:write')">
        <el-button @click="showAiGenerate = true">AI 生成图片</el-button>
        <el-button @click="showAiVideoGenerate = true">AI 生成视频</el-button>
        <el-button type="primary" @click="showUpload = true">上传素材</el-button>
      </div>
    </div>

    <div class="page-card filter-bar">
      <el-form inline>
        <el-form-item label="分类">
          <el-select v-model="filters.category" clearable placeholder="全部分类" style="width: 140px">
            <el-option v-for="c in categories" :key="c" :label="c" :value="c" />
          </el-select>
        </el-form-item>
        <el-form-item label="类型">
          <el-select v-model="filters.material_type" clearable placeholder="全部类型" style="width: 120px">
            <el-option label="图片" value="image" />
            <el-option label="视频" value="video" />
            <el-option label="文案" value="text" />
          </el-select>
        </el-form-item>
        <el-form-item label="名称">
          <el-input v-model="filters.keyword" clearable placeholder="名称关键字" style="width: 180px" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="load">查询</el-button>
          <el-button @click="reset">重置</el-button>
        </el-form-item>
      </el-form>
    </div>

    <div class="page-card">
      <el-table :data="materials" v-loading="loading">
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column prop="name" label="名称" min-width="120" show-overflow-tooltip />
        <el-table-column prop="category" label="分类" width="100" />
        <el-table-column label="类型" width="90">
          <template #default="{ row }">{{ typeLabel(row.type) }}</template>
        </el-table-column>
        <el-table-column prop="source" label="来源" width="100" />
        <el-table-column label="图片审核" width="100">
          <template #default="{ row }">
            <el-tag v-if="row.type === 'image'" size="small" :type="moderationTagType(row.moderation_status)">
              {{ moderationLabel(row.moderation_status) }}
            </el-tag>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column label="预览" width="120">
          <template #default="{ row }">
            <el-image
              v-if="row.type === 'image' && (row.thumbnail_url || row.url)"
              :src="row.thumbnail_url || row.url"
              :preview-src-list="[row.url || row.thumbnail_url]"
              fit="cover"
              class="thumb clickable"
              preview-teleported
            />
            <el-button v-else-if="row.type === 'text'" link type="primary" @click="previewText(row)">
              查看文案
            </el-button>
            <el-image
              v-else-if="row.type === 'video' && row.thumbnail_url"
              :src="row.thumbnail_url"
              fit="cover"
              class="thumb clickable"
              @click="openVideoPreview(row)"
            />
            <el-button v-else-if="row.type === 'audio' && row.url" link type="primary" @click="openAudioPreview(row)">
              <el-icon style="vertical-align: middle; margin-right: 2px"><Headset /></el-icon>试听
            </el-button>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column label="创建时间" width="180">
          <template #default="{ row }">{{ formatDateTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column v-if="can('materials:write')" label="操作" width="100" fixed="right">
          <template #default="{ row }">
            <el-button size="small" type="danger" @click="remove(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <el-dialog v-model="showUpload" title="上传素材" width="480px">
      <el-form label-width="80px">
        <el-form-item label="名称">
          <el-input v-model="uploadForm.name" placeholder="如：春茶封面01" />
        </el-form-item>
        <el-form-item label="分类">
          <el-select v-model="uploadForm.category" allow-create filterable default-first-option placeholder="选择或输入分类" style="width: 100%">
            <el-option v-for="c in categories" :key="c" :label="c" :value="c" />
          </el-select>
        </el-form-item>
        <el-form-item label="文件">
          <el-upload drag :auto-upload="false" :limit="1" :on-change="onFileChange">
            <div class="el-upload__text">拖拽或点击选择文件</div>
          </el-upload>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showUpload = false">取消</el-button>
        <el-button type="primary" :loading="uploading" @click="submitUpload">上传</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="showAiGenerate" title="AI 生成图片" width="640px">
      <el-form label-width="90px">
        <el-form-item label="平台">
          <el-select v-model="aiForm.platform" style="width: 100%" @change="onPlatformChange">
            <el-option v-for="p in PLATFORMS" :key="p.value" :label="p.label" :value="p.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="主题">
          <el-input v-model="aiForm.topic" placeholder="如：春茶上新封面" />
        </el-form-item>
        <el-form-item label="风格">
          <el-select v-model="aiForm.style" style="width: 100%">
            <el-option v-for="s in IMAGE_STYLES" :key="s.value" :label="s.label" :value="s.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="品牌色">
          <BrandColorSelect v-model="aiForm.brand_color" />
        </el-form-item>
        <el-form-item label="品牌说明">
          <el-input v-model="aiForm.brand_hint" placeholder="可选，如：高山有机春茶" />
        </el-form-item>
        <el-form-item label="封面文案">
          <el-input v-model="aiForm.cover_text" placeholder="可选，显示在封面上的文字" />
        </el-form-item>
        <el-form-item label="比例">
          <el-select v-model="aiForm.ratio" style="width: 100%">
            <el-option v-for="r in IMAGE_RATIOS" :key="r" :label="r" :value="r" />
          </el-select>
        </el-form-item>
        <el-form-item label="数量">
          <el-input-number v-model="aiForm.count" :min="1" :max="4" />
        </el-form-item>
        <el-form-item label="中文 Prompt">
          <el-input v-model="promptPreview.prompt_zh" type="textarea" :rows="3" readonly placeholder="点击预览 Prompt" />
        </el-form-item>
        <el-form-item label="英文 Prompt">
          <el-input v-model="promptPreview.prompt_en" type="textarea" :rows="3" readonly placeholder="-" />
        </el-form-item>
        <el-form-item label="负面 Prompt">
          <el-input v-model="promptPreview.negative_prompt" type="textarea" :rows="2" readonly placeholder="-" />
        </el-form-item>
      </el-form>
      <template #footer>
        <span class="cost-tag" style="margin-right: auto">预估 ¥{{ aiImageCostEstimate }}</span>
        <el-button @click="previewPrompt" :loading="previewing">预览 Prompt</el-button>
        <el-button @click="showAiGenerate = false">取消</el-button>
        <el-button type="primary" :loading="aiGenerating" @click="submitAiGenerate">生成</el-button>
      </template>
      <el-alert v-if="pageError" type="error" :closable="true" :title="pageError" @close="pageError = ''" show-icon style="margin-top: 12px" />
    </el-dialog>

    <el-dialog v-model="showAiVideoGenerate" title="AI 生成视频" width="560px">
      <el-form label-width="90px">
        <el-form-item label="平台">
          <el-select v-model="aiVideoForm.platform" style="width: 100%">
            <el-option v-for="p in PLATFORMS" :key="p.value" :label="p.label" :value="p.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="主题">
          <el-input v-model="aiVideoForm.topic" placeholder="如：春茶上新短视频" />
        </el-form-item>
        <el-form-item label="生成方式">
          <el-radio-group v-model="aiVideoForm.mode" @change="onVideoModeChange">
            <el-radio value="t2v">文生视频</el-radio>
            <el-radio value="i2v">图生视频</el-radio>
            <el-radio value="digital_human">数字人</el-radio>
            <el-radio value="simulation_human">仿真人</el-radio>
          </el-radio-group>
          <p class="upload-hint" style="margin-top: 6px">
            当前视频生成走<strong>腾讯云点播（VOD）</strong>通道，与「AI 模型」页配置一致；
            选「数字人 / 仿真人」会自动切换为图生视频并加载数字人列表（对口型，走 Kling，支持）。
          </p>
        </el-form-item>
        <!-- 数字人 / 仿真人：自动联动图生视频 -->
        <template v-if="aiVideoForm.mode === 'digital_human' || aiVideoForm.mode === 'simulation_human'">
          <el-form-item label="选择数字人">
            <el-select v-model="aiVideoForm.avatarId" placeholder="选择已创建的数字人" @focus="loadVideoAvatars" style="width: 100%">
              <el-option v-for="av in videoAvatars.filter(a => a.type === aiVideoForm.mode)" :key="av.id" :label="av.name" :value="av.id" />
            </el-select>
            <p class="upload-hint">选择数字人后，将以其形象做图生视频（对口型）。未选数字人无法提交，避免误扣费。</p>
          </el-form-item>
        </template>
        <!-- 纯图生视频（不上传照片 + 不选数字人时拦截，避免 H3 不支持误扣费） -->
        <el-form-item v-else-if="aiVideoForm.mode === 'i2v'" label="驱动照片">
          <el-upload :auto-upload="false" :show-file-list="false" accept="image/*" @change="onVideoDriverPhotoChange">
            <el-button>选择照片</el-button>
          </el-upload>
          <div v-if="videoDriverPhotoPreview" style="margin-top: 8px">
            <img :src="videoDriverPhotoPreview" style="max-width: 160px; max-height: 160px; border-radius: 8px" />
            <el-button size="small" type="danger" plain style="margin-left: 8px" @click="clearVideoDriverPhoto">清除</el-button>
          </div>
          <p class="upload-hint">
            上传人物照片生成图生视频。注意：当前默认子模型（Hailuo H3）对纯图生视频支持有限，提交若失败会被后台拒绝且不扣费；
            如需稳定出图生视频，建议选上方「数字人 / 仿真人」走对口型，或在「AI 模型」页切换支持 i2v 的子模型（如可灵 Kling）。
          </p>
        </el-form-item>
        <el-form-item label="时长">
          <el-input-number v-model="aiVideoForm.duration" :min="1" :max="60" :step="1" style="width: 100%" />
        </el-form-item>
      </el-form>
      <template #footer>
        <span class="cost-tag" style="margin-right: auto">预估 ¥{{ aiVideoCostEstimate }}</span>
        <el-button @click="showAiVideoGenerate = false">取消</el-button>
        <el-button type="primary" :loading="aiVideoGenerating" @click="submitAiVideoGenerate">生成</el-button>
      </template>
      <el-alert v-if="pageError" type="error" :closable="true" :title="pageError" @close="pageError = ''" show-icon style="margin-top: 12px" />
    </el-dialog>

    <el-drawer v-model="textPreviewVisible" :title="textPreviewTitle" size="480px">
      <p v-if="textPreviewLoading" class="muted">加载中…</p>
      <el-input
        v-else
        v-model="textPreviewContent"
        type="textarea"
        :rows="18"
        readonly
      />
    </el-drawer>

    <el-dialog v-model="videoPreviewVisible" title="视频预览" width="640px" align-center destroy-on-close>
      <video
        :src="videoPreviewUrl"
        :poster="videoPreviewPoster"
        controls
        autoplay
        preload="auto"
        style="width: 100%; max-height: 70vh; border-radius: 8px; display: block"
      />
    </el-dialog>

    <el-dialog v-model="audioPreviewVisible" :title="audioPreviewTitle" width="480px" align-center destroy-on-close>
      <audio
        :src="audioPreviewUrl"
        controls
        autoplay
        preload="auto"
        style="width: 100%; display: block"
      />
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Headset, WarningFilled } from '@element-plus/icons-vue'
import { api } from '@/api'
import { PLATFORMS, platformCoverRatio } from '@/constants/platforms'
import BrandColorSelect from '@/components/BrandColorSelect.vue'
import { IMAGE_RATIOS, IMAGE_STYLES } from '@/constants/imageStyles'
import { formatDateTime } from '@/utils/datetime'
import { usePermission } from '@/composables/usePermission'

const { can } = usePermission()

const loading = ref(false)
const pageError = ref('')
const uploading = ref(false)
const materials = ref([])
const categories = ref([])
const showUpload = ref(false)
const showAiGenerate = ref(false)
const aiGenerating = ref(false)
const previewing = ref(false)
const promptPreview = reactive({ prompt_zh: '', prompt_en: '', negative_prompt: '' })
const uploadFile = ref(null)
const filters = reactive({ category: '', material_type: '', keyword: '' })
const uploadForm = reactive({ name: '', category: '默认' })
const textPreviewVisible = ref(false)
const textPreviewTitle = ref('文案预览')
const textPreviewContent = ref('')
const textPreviewLoading = ref(false)
const videoPreviewVisible = ref(false)
const videoPreviewUrl = ref('')
const videoPreviewPoster = ref('')
const audioPreviewVisible = ref(false)
const audioPreviewUrl = ref('')
const audioPreviewTitle = ref('')

// AI 生成视频
const showAiVideoGenerate = ref(false)
const aiVideoGenerating = ref(false)
const aiVideoForm = reactive({ platform: 'douyin', topic: '', mode: 't2v', duration: 5, avatarId: null })
const videoDriverPhotoFile = ref(null)
const videoDriverPhotoPreview = ref('')
// 数字人 / 仿真人列表（AI 生成视频对话框内联动使用）
const videoAvatars = ref([])
async function loadVideoAvatars() {
  try {
    videoAvatars.value = await api.listAvatars()
  } catch {
    /* ignore */
  }
}
// 选「数字人 / 仿真人」自动联动为图生视频（i2v）；切回文生视频收起数字人
function onVideoModeChange(val) {
  if (val === 'digital_human' || val === 'simulation_human') {
    // 保持 mode 语义为 i2v（图生视频），用 avatarType 区分数字人
    aiVideoForm.mode = val
  } else if (val === 't2v') {
    aiVideoForm.avatarId = null
  }
}

function typeLabel(type) {
  return { image: '图片', video: '视频', text: '文案' }[type] || type
}

function moderationLabel(status) {
  return (
    {
      passed: '通过',
      rejected: '未通过',
      pending: '审核中',
      skipped: '未启用',
    }[status] || '—'
  )
}

function moderationTagType(status) {
  if (status === 'passed') return 'success'
  if (status === 'rejected') return 'danger'
  if (status === 'pending') return 'warning'
  return 'info'
}

async function previewText(row) {
  textPreviewTitle.value = row.name || `文案 #${row.id}`
  textPreviewVisible.value = true
  textPreviewLoading.value = true
  textPreviewContent.value = row.text_preview || ''
  try {
    const detail = await api.getMaterial(row.id)
    textPreviewContent.value = detail.text_content || detail.text_preview || '（无正文）'
  } catch (e) {
    pageError.value = e.message || '加载失败'
  } finally {
    textPreviewLoading.value = false
  }
}

function openVideoPreview(row) {
  if (!row.url) return ElMessage.warning('视频链接不存在')
  videoPreviewUrl.value = row.url
  videoPreviewPoster.value = row.thumbnail_url || ''
  videoPreviewVisible.value = true
}

function openAudioPreview(row) {
  audioPreviewTitle.value = row.name || `音频 #${row.id}`
  audioPreviewUrl.value = resolvePlayUrl(row)
  if (!audioPreviewUrl.value) return ElMessage.warning('音频链接不存在')
  audioPreviewVisible.value = true
}

// 兜底从 file_path 计算可播放的 /static/materials/xxx 路径。
// 兼容历史脏数据：旧 storage.get_url 只取 basename，丢失 voices/ 子目录导致 404。
function resolvePlayUrl(row) {
  // 优先用 file_path 直接拼出带子目录的正确 URL（如 voices/avatar_xxx.mp3）
  if (row.file_path) {
    const fp = String(row.file_path)
    const m = fp.match(/\/data\/materials\/(.+)$/)
    if (m) return `/static/materials/${m[1]}`
    const name = fp.split('/').pop()
    if (name) return `/static/materials/${name}`
  }
  // 退化到后端返回的 url（新写入的 audio 应该是 /static/materials/voices/xxx.mp3）
  return row.url || ''
}

const aiForm = reactive({
  platform: 'xhs',
  topic: '春茶上新',
  style: 'default',
  brand_color: '',
  brand_hint: '',
  cover_text: '',
  ratio: '3:4',
  count: 1,
})

// 费用预估
const aiImageCostEstimate = computed(() => (aiForm.count * 0.02).toFixed(2))
const aiVideoCostEstimate = computed(() => (aiVideoForm.duration * 0.5).toFixed(2))

function onPlatformChange() {
  aiForm.ratio = platformCoverRatio(aiForm.platform)
}

async function previewPrompt() {
  if (!aiForm.topic.trim()) return ElMessage.warning('请填写主题')
  previewing.value = true
  try {
    const res = await api.buildPrompt({
      kind: 'image',
      platform: aiForm.platform,
      topic: aiForm.topic,
      ratio: aiForm.ratio,
      style: aiForm.style,
      cover_text: aiForm.cover_text || null,
      brand_color: aiForm.brand_color || null,
      brand_hint: aiForm.brand_hint || null,
    })
    promptPreview.prompt_zh = res.prompt_zh || res.prompt
    promptPreview.prompt_en = res.prompt_en || ''
    promptPreview.negative_prompt = res.negative_prompt || ''
  } catch (e) {
    pageError.value = e.message || '预览失败'
  } finally {
    previewing.value = false
  }
}

function onFileChange(file) {
  uploadFile.value = file.raw
  if (!uploadForm.name && file.name) {
    uploadForm.name = file.name.replace(/\.[^.]+$/, '')
  }
}

async function loadCategories() {
  const res = await api.listMaterialCategories()
  categories.value = res.items || []
}

async function load() {
  loading.value = true
  try {
    const params = {}
    if (filters.category) params.category = filters.category
    if (filters.material_type) params.material_type = filters.material_type
    if (filters.keyword) params.keyword = filters.keyword
    materials.value = await api.listMaterials(params)
  } finally {
    loading.value = false
  }
}

function reset() {
  filters.category = ''
  filters.material_type = ''
  filters.keyword = ''
  load()
}

async function remove(row) {
  try {
    await ElMessageBox.confirm(`确定删除素材「${row.name || row.id}」？`, '删除确认', { type: 'warning' })
    await api.deleteMaterial(row.id)
    ElMessage.success('已删除')
    load()
  } catch (e) {
    if (e !== 'cancel') pageError.value = e.message || '删除失败'
  }
}

async function submitUpload() {
  if (!uploadFile.value) return ElMessage.warning('请选择文件')
  pageError.value = ''
  uploading.value = true
  try {
    await api.uploadMaterial(uploadFile.value, {
      name: uploadForm.name,
      category: uploadForm.category || '默认',
    })
    ElMessage.success('上传成功')
    showUpload.value = false
    uploadFile.value = null
    uploadForm.name = ''
    uploadForm.category = '默认'
    await loadCategories()
    load()
  } catch (e) {
    pageError.value = e.message || '上传失败'
  } finally {
    uploading.value = false
  }
}

async function submitAiGenerate() {
  pageError.value = ''
  if (!aiForm.topic.trim()) return ElMessage.warning('请填写主题')
  aiGenerating.value = true
  try {
    const res = await api.generateImage({
      topic: aiForm.topic,
      platform: aiForm.platform,
      ratio: aiForm.ratio,
      count: aiForm.count,
      style: aiForm.style,
      cover_text: aiForm.cover_text || null,
      brand_color: aiForm.brand_color || null,
      brand_hint: aiForm.brand_hint || null,
    })
    ElMessage.success(`已生成 ${res.materials?.length || aiForm.count} 张图片（风格：${aiForm.style}）`)
    showAiGenerate.value = false
    promptPreview.prompt_zh = ''
    promptPreview.prompt_en = ''
    promptPreview.negative_prompt = ''
    load()
  } catch (e) {
    pageError.value = e.message || '图片生成失败'
  } finally {
    aiGenerating.value = false
  }
}

function onVideoDriverPhotoChange(file) {
  videoDriverPhotoFile.value = file.raw
  videoDriverPhotoPreview.value = URL.createObjectURL(file.raw)
}

function clearVideoDriverPhoto() {
  videoDriverPhotoFile.value = null
  videoDriverPhotoPreview.value = ''
}

function platformVideoResolution(platform) {
  if (['douyin', 'kuaishou'].includes(platform)) return 'portrait'
  return '720p'
}

async function submitAiVideoGenerate() {
  if (!aiVideoForm.topic.trim()) return ElMessage.warning('请填写主题')
  const isAvatar = aiVideoForm.mode === 'digital_human' || aiVideoForm.mode === 'simulation_human'
  if (isAvatar) {
    if (!aiVideoForm.avatarId) return ElMessage.warning('请先选择数字人（数字人 / 仿真人为必选项）')
  } else if (aiVideoForm.mode === 'i2v' && !videoDriverPhotoFile.value) {
    // 纯图生视频（不上传照片）：H3 不支持，提交会被后台拒绝且不扣费，这里先提示
    return ElMessage.warning('请先上传驱动照片，或选择上方「数字人 / 仿真人」走对口型（更稳定）')
  }
  pageError.value = ''
  aiVideoGenerating.value = true
  try {
    let imageUrl = null
    // 数字人 / 仿真人：不传 image_url，走 avatar 对口型（Kling），避免 H3 i2v 误扣费
    if (!isAvatar && aiVideoForm.mode === 'i2v' && videoDriverPhotoFile.value) {
      const uploadRes = await api.uploadMaterial(videoDriverPhotoFile.value, { name: '驱动照片', category: '视频驱动' })
      imageUrl = uploadRes.url
    }
    const payload = {
      topic: aiVideoForm.topic,
      platform: aiVideoForm.platform,
      duration: aiVideoForm.duration,
      resolution: platformVideoResolution(aiVideoForm.platform),
      fps: 24,
      image_url: imageUrl,
    }
    if (isAvatar) {
      payload.avatar_id = aiVideoForm.avatarId
      payload.avatar_type = aiVideoForm.mode
    }
    const res = await api.generateVideo(payload)
    const count = res.materials?.length || 1
    ElMessage.success(`已生成 ${count} 个视频（${res.provider}）`)
    showAiVideoGenerate.value = false
    aiVideoForm.topic = ''
    aiVideoForm.mode = 't2v'
    aiVideoForm.avatarId = null
    videoDriverPhotoFile.value = null
    videoDriverPhotoPreview.value = ''
    load()
  } catch (e) {
    pageError.value = e.message || '视频生成失败'
  } finally {
    aiVideoGenerating.value = false
  }
}

onMounted(async () => {
  await loadCategories()
  load()
})
</script>

<style scoped>
.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.filter-bar {
  margin-bottom: 16px;
}
.thumb {
  width: 64px;
  height: 64px;
  border-radius: 8px;
}
.clickable {
  cursor: zoom-in;
}
.upload-hint {
  margin: 4px 0 0;
  color: #999;
  font-size: 12px;
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
