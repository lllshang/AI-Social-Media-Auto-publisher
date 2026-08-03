<template>
  <div>
    <div class="toolbar">
      <h2 class="page-title">AI 模型</h2>
      <div v-if="canWrite">
        <el-button @click="detect">自动匹配</el-button>
        <el-button type="primary" @click="apply">应用模型选择</el-button>
      </div>
    </div>

    <el-alert
      v-if="!canWrite"
      type="info"
      :closable="false"
      show-icon
      title="只读模式"
      description="当前账号仅可查看模型配置，无法修改或切换模型。"
      style="margin-bottom: 16px"
    />
    <el-alert
      v-if="pageError"
      type="error"
      :closable="true"
      show-icon
      :title="pageError"
      style="margin-bottom: 16px"
      @close="pageError = ''"
    />

    <el-row :gutter="16">
      <el-col :span="canWrite ? 12 : 24">
        <div class="page-card">
          <h3>当前配置</h3>
          <p>文案：{{ current.text }}</p>
          <p>文生图：{{ current.image }}</p>
          <p>文生视频：{{ current.video }}</p>
        </div>
      </el-col>
      <el-col v-if="canWrite" :span="12">
        <div class="page-card">
          <h3>测试文案生成</h3>
          <el-input v-model="topic" placeholder="输入主题" />
          <el-button type="primary" style="margin-top: 12px" :loading="generating" @click="testText">生成</el-button>
          <pre v-if="textResult" class="result">{{ textResult }}</pre>
          <el-alert v-if="textError" type="error" :closable="true" :title="textError" @close="textError = ''" show-icon style="margin-top: 12px" />
        </div>
      </el-col>
    </el-row>

    <el-row v-if="canWrite" :gutter="16" style="margin-top: 16px">
      <el-col :span="12">
        <div class="page-card">
          <h3>测试图片生成</h3>
          <el-input v-model="imageTopic" placeholder="输入主题" />
          <el-select v-model="imageRatio" style="width: 100%; margin-top: 8px">
            <el-option label="3:4（竖版）" value="3:4" />
            <el-option label="1:1（方版）" value="1:1" />
            <el-option label="16:9（横版）" value="16:9" />
          </el-select>
          <div style="margin-top: 12px; display: flex; align-items: center; gap: 8px">
            <el-button type="primary" :loading="generatingImage" @click="testImage">生成图片</el-button>
            <span class="cost-tag">预估 ¥{{ imageCostEstimate }}</span>
          </div>
          <div v-if="imageResult" class="test-result">
            <el-image
              v-if="imageResult.materials?.length"
              :src="imageResult.materials[0].url"
              :preview-src-list="[imageResult.materials[0].url]"
              fit="contain"
              style="max-width: 100%; max-height: 160px; border-radius: 6px"
            />
            <p class="test-meta">{{ imageResult.provider }} / {{ imageResult.model }} · 预估 ¥{{ imageResult.cost }} · 耗时 {{ formatElapsed(imageResult.elapsed) }}</p>
            <pre v-if="imageResult.prompt" class="result" style="max-height: 100px">{{ imageResult.prompt }}</pre>
          </div>
          <el-alert v-if="imageError" type="error" :closable="true" :title="imageError" @close="imageError = ''" show-icon style="margin-top: 12px" />
        </div>
      </el-col>
      <el-col :span="12">
        <div class="page-card">
          <h3>测试视频生成</h3>
          <el-input v-model="videoTopic" placeholder="输入主题" />
          <el-input-number v-model="videoDuration" :min="1" :max="60" :step="1" style="width: 100%; margin-top: 8px" />
          <div style="margin-top: 12px; display: flex; align-items: center; gap: 8px">
            <el-button type="primary" :loading="generatingVideo" @click="testVideo">生成视频</el-button>
            <span class="cost-tag">预估 ¥{{ videoCostEstimate }}</span>
          </div>
          <div v-if="videoResult" class="test-result">
            <video
              v-if="videoResult.materials?.length && videoResult.materials[0].url"
              :src="videoResult.materials[0].url"
              :poster="videoResult.materials[0].thumbnail_url"
              controls
              preload="metadata"
              style="max-width: 100%; max-height: 240px; border-radius: 6px; display: block"
            />
            <p class="test-meta">{{ videoResult.provider }} / {{ videoResult.model }} · {{ videoResult.materials?.[0]?.duration || videoResult.duration }}s · 预估 ¥{{ videoResult.cost }} · 耗时 {{ formatElapsed(videoResult.elapsed) }}</p>
            <pre v-if="videoResult.prompt" class="result" style="max-height: 100px">{{ videoResult.prompt }}</pre>
          </div>
          <el-alert v-if="videoError" type="error" :closable="true" :title="videoError" @close="videoError = ''" show-icon style="margin-top: 12px" />
        </div>
      </el-col>
    </el-row>

    <div v-if="canWrite" class="page-card" style="margin-top: 16px">
      <h3>切换文案模型</h3>
      <el-select v-model="selectedText" placeholder="选择文案模型" style="width: 100%">
        <el-option
          v-for="item in textOptions"
          :key="item.provider + item.model"
          :label="item.label"
          :value="`${item.provider}::${item.model}`"
          :disabled="!item.ready"
        />
      </el-select>
    </div>

    <div v-if="canWrite" class="page-card" style="margin-top: 16px">
      <h3>切换文生图模型</h3>
      <el-select v-model="selectedImage" placeholder="选择文生图模型" style="width: 100%">
        <el-option
          v-for="item in imageOptions"
          :key="item.provider + item.model"
          :label="item.label"
          :value="`${item.provider}::${item.model}`"
          :disabled="!item.ready"
        />
      </el-select>
    </div>

    <div v-if="canWrite" class="page-card" style="margin-top: 16px">
      <h3>切换文生视频模型</h3>
      <p class="muted" style="margin: 0 0 10px">视频生成需配置相应厂商的 API Key</p>
      <el-select v-model="selectedVideo" placeholder="选择文生视频模型" style="width: 100%">
        <el-option
          v-for="item in videoOptions"
          :key="item.provider + item.model"
          :label="item.label"
          :value="`${item.provider}::${item.model}`"
          :disabled="!item.ready"
        />
      </el-select>
    </div>

    <div class="page-card" style="margin-top: 16px">
      <div class="section-header">
        <div>
          <h3>厂商 API Key 配置</h3>
          <p class="muted">内置主流厂商可直接配置 Key；也可新增 OpenAI 兼容的自定义厂商。</p>
        </div>
        <el-button v-if="canWrite" type="primary" plain @click="openAddProvider">新增厂商</el-button>
      </div>
      <el-table v-loading="loading" :data="providers" size="small">
        <el-table-column prop="label" label="厂商" min-width="180" />
        <el-table-column prop="kind" label="类型" width="80" />
        <el-table-column label="Key 状态" width="120">
          <template #default="{ row }">
            <el-tag :type="row.configured ? 'success' : 'info'">{{ row.configured ? '已配置' : '未配置' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="api_key_masked" label="Key 预览" width="140" />
        <el-table-column prop="base_url" label="Base URL" show-overflow-tooltip />
        <el-table-column v-if="canWrite" label="操作" width="180">
          <template #default="{ row }">
            <el-button size="small" @click="openProvider(row)">配置</el-button>
            <el-button v-if="row.custom" size="small" type="danger" plain @click="removeProvider(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <el-dialog v-model="providerVisible" :title="`配置 ${providerForm.label}`" width="520px">
      <el-form label-width="90px">
        <el-form-item v-if="providerForm.key_field" label="SecretId">
          <el-input v-model="providerForm.api_key" type="password" show-password placeholder="留空则不修改" />
        </el-form-item>
        <el-form-item v-if="providerForm.secret_key_field" label="SecretKey">
          <el-input v-model="providerForm.secret_key" type="password" show-password placeholder="留空则不修改" />
        </el-form-item>
        <el-form-item v-if="providerForm.sub_app_id_field" label="SubAppId">
          <el-input v-model="providerForm.sub_app_id" placeholder="留空则不修改" />
        </el-form-item>
        <el-form-item v-if="providerForm.base_url_field || providerForm.custom" label="Base URL">
          <el-input v-model="providerForm.base_url" :placeholder="providerForm.default_base_url" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button v-if="providerForm.key_field" type="danger" plain @click="clearProvider">清除 Key</el-button>
        <el-button @click="providerVisible = false">取消</el-button>
        <el-button type="primary" @click="saveProvider">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="addVisible" title="新增厂商" width="560px">
      <el-form label-width="100px">
        <el-form-item label="厂商名称" required>
          <el-input v-model="addForm.label" placeholder="例如：OneAPI 代理" />
        </el-form-item>
        <el-form-item label="类型" required>
          <el-select v-model="addForm.kind" style="width: 100%">
            <el-option label="文案" value="text" />
            <el-option label="文生图" value="image" />
            <el-option label="文案 + 文生图" value="both" />
          </el-select>
        </el-form-item>
        <el-form-item label="Base URL" required>
          <el-input v-model="addForm.base_url" placeholder="https://api.example.com/v1" />
        </el-form-item>
        <el-form-item label="API Key">
          <el-input v-model="addForm.api_key" type="password" show-password placeholder="可选，稍后也可配置" />
        </el-form-item>
        <el-form-item v-if="addForm.kind !== 'image'" label="文案模型">
          <el-input
            v-model="addForm.text_models"
            type="textarea"
            :rows="2"
            placeholder="每行一个模型名，例如 gpt-4o-mini"
          />
        </el-form-item>
        <el-form-item v-if="addForm.kind !== 'text'" label="文生图模型">
          <el-input
            v-model="addForm.image_models"
            type="textarea"
            :rows="2"
            placeholder="每行一个模型名，例如 dall-e-3"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="addVisible = false">取消</el-button>
        <el-button type="primary" @click="submitAddProvider">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { api } from '@/api'
import { usePermission } from '@/composables/usePermission'

const { can } = usePermission()
const canWrite = computed(() => can('models:write'))
const modelData = ref(null)
const providers = ref([])
const selectedText = ref('')
const selectedImage = ref('')
const selectedVideo = ref('')
const topic = ref('春茶上新')
const textResult = ref('')
const generating = ref(false)
const textError = ref('')
const imageError = ref('')
const videoError = ref('')
const pageError = ref('')
const imageTopic = ref('春茶上新')
const imageRatio = ref('3:4')
const imageResult = ref(null)
const generatingImage = ref(false)
const videoTopic = ref('春茶上新')
const videoDuration = ref(5)
const videoResult = ref(null)
const generatingVideo = ref(false)
const loading = ref(false)
const providerVisible = ref(false)
const addVisible = ref(false)
const providerForm = reactive({
  provider: '',
  label: '',
  key_field: '',
  secret_key_field: '',
  sub_app_id_field: '',
  base_url_field: '',
  default_base_url: '',
  custom: false,
  api_key: '',
  secret_key: '',
  sub_app_id: '',
  base_url: '',
})
const addForm = reactive({
  label: '',
  kind: 'text',
  base_url: '',
  api_key: '',
  text_models: '',
  image_models: '',
})

const current = computed(() => ({
  text: modelData.value?.text?.current
    ? `${modelData.value.text.current.provider} / ${modelData.value.text.current.model}`
    : '-',
  image: modelData.value?.image?.current
    ? `${modelData.value.image.current.provider} / ${modelData.value.image.current.model}`
    : '-',
  video: modelData.value?.video?.current
    ? `${modelData.value.video.current.provider} / ${modelData.value.video.current.model}`
    : '-',
}))
const textOptions = computed(() => modelData.value?.text?.available || [])
const imageOptions = computed(() => modelData.value?.image?.available || [])
const videoOptions = computed(() => modelData.value?.video?.available || [])

// --- 费用预估 ---
function getVideoPricePerSec(modelName) {
  if (!modelName) return 0.5
  if (modelName.includes('mini')) return 0.5
  if (modelName.includes('pro')) return 1.5
  if (modelName.includes('seedance-2-0')) return 1.0
  return 0.5
}

function getImagePricePerImage(modelName) {
  if (!modelName) return 0.02
  if (modelName.includes('seedream')) return 0.02
  return 0.08
}

function formatElapsed(seconds) {
  const s = Number(seconds) || 0
  if (s < 60) return `${s.toFixed(1)} 秒`
  const m = Math.floor(s / 60)
  const rest = Math.round(s % 60)
  return `${m} 分 ${rest} 秒`
}

const currentVideoModel = computed(() => modelData.value?.video?.current?.model || '')
const currentImageModel = computed(() => modelData.value?.image?.current?.model || '')
const videoCostEstimate = computed(() => (videoDuration.value * getVideoPricePerSec(currentVideoModel.value)).toFixed(2))
const imageCostEstimate = computed(() => getImagePricePerImage(currentImageModel.value).toFixed(2))

function splitModels(raw) {
  return raw
    .split(/[\n,]/)
    .map((item) => item.trim())
    .filter(Boolean)
}

async function loadProviders() {
  const providerData = await api.listProviders()
  providers.value = providerData.items || []
}

async function loadModels() {
  const models = await api.getModels()
  modelData.value = models
  const textCur = models.text?.current
  const imageCur = models.image?.current
  const videoCur = models.video?.current
  if (textCur?.provider && textCur?.model) {
    selectedText.value = `${textCur.provider}::${textCur.model}`
  }
  if (imageCur?.provider && imageCur?.model) {
    selectedImage.value = `${imageCur.provider}::${imageCur.model}`
  }
  if (videoCur?.provider && videoCur?.model) {
    selectedVideo.value = `${videoCur.provider}::${videoCur.model}`
  }
}

async function load() {
  loading.value = true
  try {
    await Promise.all([loadProviders(), loadModels()])
  } catch (e) {
    try {
      await loadProviders()
    } catch (providerError) {
      pageError.value = providerError.message || '加载厂商列表失败'
    }
    if (!modelData.value) {
      pageError.value = e.message || '加载模型信息失败'
    }
  } finally {
    loading.value = false
  }
}

async function detect() {
  try {
    modelData.value = await api.detectModels()
    ElMessage.success('已重新自动匹配')
    await load()
  } catch (e) {
    pageError.value = e.message || '自动匹配失败'
  }
}

async function apply() {
  try {
    const [textProvider, textModel] = selectedText.value.split('::')
    const [imageProvider, imageModel] = selectedImage.value.split('::')
    const [videoProvider, videoModel] = selectedVideo.value ? selectedVideo.value.split('::') : ['', '']
    await api.selectModel({
      mode: 'manual',
      text_provider: textProvider,
      text_model: textModel,
      image_provider: imageProvider,
      image_model: imageModel,
      video_provider: videoProvider || undefined,
      video_model: videoModel || undefined,
    })
    ElMessage.success('已切换模型')
    await load()
  } catch (e) {
    pageError.value = e.message || '切换模型失败'
  }
}

async function testText() {
  generating.value = true
  textError.value = ''
  try {
    const res = await api.generateText(topic.value)
    textResult.value = JSON.stringify(res, null, 2)
  } catch (e) {
    textError.value = e.message || '文案生成失败'
  } finally {
    generating.value = false
  }
}

async function testImage() {
  generatingImage.value = true
  imageResult.value = null
  imageError.value = ''
  try {
    const res = await api.generateImage({ topic: imageTopic.value, platform: 'xhs', ratio: imageRatio.value, count: 1 })
    imageResult.value = res
  } catch (e) {
    imageError.value = e.message || '图片生成失败'
  } finally {
    generatingImage.value = false
  }
}

async function testVideo() {
  generatingVideo.value = true
  videoResult.value = null
  videoError.value = ''
  try {
    const res = await api.generateVideo({ topic: videoTopic.value, platform: 'douyin', duration: videoDuration.value })
    videoResult.value = res
  } catch (e) {
    videoError.value = e.message || '视频生成失败'
  } finally {
    generatingVideo.value = false
  }
}

function openProvider(row) {
  providerForm.provider = row.provider
  providerForm.label = row.label
  providerForm.key_field = row.key_field
  providerForm.secret_key_field = row.secret_key_field
  providerForm.sub_app_id_field = row.sub_app_id_field
  providerForm.base_url_field = row.base_url_field
  providerForm.default_base_url = row.default_base_url
  providerForm.custom = !!row.custom
  providerForm.api_key = ''
  providerForm.secret_key = ''
  providerForm.sub_app_id = ''
  providerForm.base_url = row.base_url || row.default_base_url || ''
  providerVisible.value = true
}

function openAddProvider() {
  addForm.label = ''
  addForm.kind = 'text'
  addForm.base_url = ''
  addForm.api_key = ''
  addForm.text_models = ''
  addForm.image_models = ''
  addVisible.value = true
}

async function submitAddProvider() {
  try {
    await api.addCustomProvider({
      label: addForm.label,
      kind: addForm.kind,
      base_url: addForm.base_url,
      api_key: addForm.api_key || undefined,
      text_models: addForm.kind === 'image' ? [] : splitModels(addForm.text_models),
      image_models: addForm.kind === 'text' ? [] : splitModels(addForm.image_models),
    })
    ElMessage.success('厂商已新增')
    addVisible.value = false
    await load()
  } catch (e) {
    pageError.value = e.message || '添加失败'
  }
}

async function saveProvider() {
  try {
    await api.saveProviderConfig({
      provider: providerForm.provider,
      api_key: providerForm.api_key || undefined,
      secret_key: providerForm.secret_key || undefined,
      sub_app_id: providerForm.sub_app_id || undefined,
      base_url: providerForm.base_url || undefined,
    })
    ElMessage.success('配置已保存')
    providerVisible.value = false
    await load()
  } catch (e) {
    pageError.value = e.message || '保存配置失败'
    ElMessage.error(pageError.value)
  }
}

async function clearProvider() {
  try {
    await api.saveProviderConfig({ provider: providerForm.provider, clear_key: true })
    ElMessage.success('Key 已清除')
    providerVisible.value = false
    await load()
  } catch (e) {
    pageError.value = e.message || '清除配置失败'
  }
}

async function removeProvider(row) {
  try {
    await ElMessageBox.confirm(`确定删除自定义厂商「${row.label}」吗？`, '删除确认', { type: 'warning' })
    await api.deleteCustomProvider(row.provider)
    ElMessage.success('已删除')
    await load()
  } catch (e) {
    if (e !== 'cancel' && e?.message) {
      ElMessage.error(e.message)
    }
  }
}

onMounted(load)
</script>

<style scoped>
.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.section-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 12px;
}
.section-header h3 {
  margin: 0;
}
.result {
  margin-top: 12px;
  background: #0f1419;
  color: #e7ecf3;
  padding: 12px;
  border-radius: 8px;
  overflow: auto;
  max-height: 240px;
  font-size: 12px;
}
.test-result {
  margin-top: 12px;
}
.test-meta {
  margin: 8px 0 0;
  color: #666;
  font-size: 13px;
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
