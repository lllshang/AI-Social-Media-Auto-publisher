<template>
  <div>
    <div class="toolbar">
      <h2 class="page-title">数字人 / 仿真人</h2>
      <el-button v-if="canWrite" type="primary" @click="openCreate">新建</el-button>
    </div>

    <el-tabs v-model="activeTab">
      <el-tab-pane label="全部" name="all" />
      <el-tab-pane label="数字人" name="digital_human" />
      <el-tab-pane label="仿真人" name="simulation_human" />
    </el-tabs>

    <el-table v-loading="loading" :data="filteredAvatars" size="small">
      <el-table-column label="预览" width="80">
        <template #default="{ row }">
          <el-tooltip v-if="row.background_image_url" :content="'已配置带背景图（视频生成将自动使用）'" placement="top">
            <el-image :src="row.background_image_url" fit="cover" style="width: 48px; height: 48px; border-radius: 4px; box-shadow: 0 0 0 2px #67c23a" />
          </el-tooltip>
          <el-image v-else-if="row.thumbnail_url" :src="row.thumbnail_url" fit="cover" style="width: 48px; height: 48px; border-radius: 4px" />
          <span v-else class="muted">无</span>
        </template>
      </el-table-column>
      <el-table-column prop="name" label="名称" />
      <el-table-column prop="type" label="类型" width="100">
        <template #default="{ row }">
          <el-tag :type="row.type === 'digital_human' ? 'primary' : 'warning'" size="small">
            {{ row.type === 'digital_human' ? '数字人' : '仿真人' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="gender" label="性别" width="80">
        <template #default="{ row }">
          {{ row.gender === 'male' ? '男' : row.gender === 'female' ? '女' : row.gender === 'neutral' ? '中性' : '-' }}
        </template>
      </el-table-column>
      <el-table-column prop="status" label="状态" width="80">
        <template #default="{ row }">
          <el-tag size="small" :type="row.status === 'active' ? 'success' : 'info'">{{ row.status }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="280">
        <template #default="{ row }">
          <el-button size="small" @click="openEdit(row)">编辑</el-button>
          <el-button
            size="small"
            type="primary"
            :disabled="row.type !== 'digital_human'"
            @click="openGenerateBg(row)"
          >生成背景图</el-button>
          <el-button size="small" type="danger" plain @click="removeAvatar(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- Create/Edit Dialog -->
    <el-dialog v-model="dialogVisible" :title="editingId ? '编辑' : '新建'" width="560px">
      <el-form label-width="100px">
        <el-form-item label="类型" required>
          <el-select v-model="avatarForm.type" :disabled="!!editingId" style="width: 100%">
            <el-option label="数字人" value="digital_human" />
            <el-option label="仿真人" value="simulation_human" />
          </el-select>
        </el-form-item>
        <el-form-item label="名称" required>
          <el-input v-model="avatarForm.name" />
        </el-form-item>
        <el-form-item label="性别">
          <el-select v-model="avatarForm.gender" style="width: 100%">
            <el-option label="男" value="male" />
            <el-option label="女" value="female" />
            <el-option label="中性" value="neutral" />
          </el-select>
        </el-form-item>

        <!-- 数字人：参考图（腾讯云 Kling avatar_i2v） -->
        <template v-if="avatarForm.type === 'digital_human'">
          <el-form-item label="参考图" required>
            <p class="muted">上传一张正面清晰人像，将作为数字人形象（腾讯云 Kling 数字人 avatar_i2v）。</p>
            <AvatarMediaUploader
              v-model="avatarForm.reference_image_url"
              media-type="image"
              label="参考图"
              category="数字人参考"
              hint="建议正面、光线充足、无遮挡的人像照片"
            />
          </el-form-item>
          <el-form-item label="背景图">
            <el-checkbox v-model="avatarForm.gen_background">生成带背景的数字人图</el-checkbox>
            <p class="muted">勾选后将依据下方描述生成带背景的候选图，挑选满意的一张作为数字人预览图（视频也将带背景）。不勾选则直接用上传的参考图。</p>
          </el-form-item>
          <template v-if="avatarForm.gen_background">
            <el-form-item label="背景描述">
              <div style="width: 100%">
                <div style="margin-bottom: 8px; display: flex; flex-wrap: wrap; gap: 8px">
                  <el-tag
                    v-for="ex in bgPromptExamples"
                    :key="ex"
                    class="bg-example"
                    @click="avatarForm.background_prompt = ex"
                  >{{ ex }}</el-tag>
                </div>
                <el-input
                  v-model="avatarForm.background_prompt"
                  type="textarea"
                  :rows="3"
                  maxlength="200"
                  show-word-limit
                  placeholder="描述人像所处的场景，例如：现代办公室落地窗前，背景虚化、暖色调；建议包含场景 + 光线/氛围，越具体生成效果越好"
                />
                <p class="muted">提示：包含「场景」（如办公室/咖啡厅/户外）+「风格氛围」（如简约/暖色调/科技感）可显著提升生成效果。</p>
              </div>
            </el-form-item>
          </template>
        </template>

        <!-- 仿真人：参考视频 + 口播词（腾讯云 Kling lip_sync） -->
        <template v-if="avatarForm.type === 'simulation_human'">
          <el-form-item label="参考视频" required>
            <p class="muted">上传一段真人视频，Kling 对口型(lip_sync)将据此生成仿真人讲解视频。</p>
            <AvatarMediaUploader
              v-model="avatarForm.reference_video_url"
              media-type="video"
              label="参考视频"
              category="仿真人参考"
              hint="建议 5-15 秒、面部清晰、单次说话的短视频"
            />
          </el-form-item>
          <el-form-item label="口播词">
            <el-input
              v-model="avatarForm.config.script"
              type="textarea"
              :rows="3"
              placeholder="仿真人将要讲述的文案（生成时作为驱动文本）"
            />
            <p class="muted">留空则直接使用生成视频时填写的视频描述。</p>
          </el-form-item>
        </template>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitAvatar">保存</el-button>
      </template>
    </el-dialog>

    <!-- Thumbnail upload Dialog -->
    <el-dialog v-model="thumbnailDialogVisible" title="上传预览图" width="400px">
      <el-upload
        :auto-upload="false"
        :show-file-list="false"
        accept="image/*"
        @change="onThumbnailFileChange"
      >
        <el-button>选择图片</el-button>
      </el-upload>
      <div v-if="thumbnailPreview" style="margin-top: 8px">
        <img :src="thumbnailPreview" style="max-width: 200px; max-height: 200px; border-radius: 8px" />
      </div>
      <template #footer>
        <el-button @click="thumbnailDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="uploadingThumbnail" :disabled="!thumbnailFile" @click="uploadThumbnail">上传</el-button>
      </template>
    </el-dialog>

    <!-- 生成背景图 Dialog -->
    <el-dialog v-model="bgDialogVisible" title="生成背景图（图生图）" width="640px" :close-on-click-modal="false">
      <p class="muted">
        基于数字人「<b>{{ bgAvatar?.name }}</b>」的参考图，按背景描述生成 1 张候选预览图。
      </p>
      <el-form label-width="80px">
        <el-form-item label="背景描述">
          <el-input
            v-model="bgPrompt"
            type="textarea"
            :rows="3"
            placeholder="例：阳光下的城市街景咖啡馆，背景虚化，自然光，电影感"
          />
        </el-form-item>
      </el-form>
      <el-button type="primary" :loading="bgGenerating" :disabled="!bgPrompt.trim()" @click="generateBg">
        生成候选图
      </el-button>
      <el-alert
        v-if="bgGenerated"
        type="success"
        :closable="false"
        style="margin-top: 12px"
        title="第一张候选图已自动保存为「带背景参考图」"
        description="数字人视频生成时将自动使用该图作为驱动图（视频带背景）。下方可继续挑选任一张「设为预览图」。"
      />
      <div v-if="bgCandidates.length" style="display: flex; gap: 12px; margin-top: 16px">
        <div v-for="(url, i) in bgCandidates" :key="i" style="flex: 1; text-align: center">
          <img :src="url" style="width: 100%; max-height: 320px; object-fit: cover; border-radius: 8px" />
          <el-button
            size="small"
            type="primary"
            :loading="bgSaving"
            style="margin-top: 8px"
            @click="applyBgCandidate(url)"
          >设为预览图</el-button>
        </div>
      </div>
      <template #footer>
        <el-button v-if="bgIsNewFlow" type="info" plain @click="skipBg">跳过，直接用参考图</el-button>
        <el-button @click="bgDialogVisible = false">{{ bgIsNewFlow ? '稍后再选' : '关闭' }}</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { api } from '@/api'
import { usePermission } from '@/composables/usePermission'
import AvatarMediaUploader from '@/components/AvatarMediaUploader.vue'

const { can } = usePermission()
const canWrite = computed(() => can('avatars:write'))

const loading = ref(false)
const avatars = ref([])
const activeTab = ref('all')
const dialogVisible = ref(false)
const editingId = ref(null)
const submitting = ref(false)

const thumbnailDialogVisible = ref(false)
const thumbnailAvatarId = ref(null)
const thumbnailFile = ref(null)
const thumbnailPreview = ref('')
const uploadingThumbnail = ref(false)

// 生成背景图弹窗
const bgDialogVisible = ref(false)
const bgAvatar = ref(null)
const bgCandidates = ref([]) // 候选图绝对 URL
const bgPrompt = ref('')
const bgGenerating = ref(false)
const bgSaving = ref(false)
const bgGenerated = ref(false)
const bgIsNewFlow = ref(false) // true=新建后跳来的生成等待页(可跳过)；false=列表点「生成背景图」编辑流程
// 把 /data/materials/xxx.jpg 转成可访问 URL（与后端约定：返回相对路径，需拼后端 base）
function absoluteMaterialUrl(relUrl) {
  if (!relUrl) return ''
  if (relUrl.startsWith('http')) return relUrl
  // 与后端 _absolutize_url 同一思路：拼后端 base
  // 前端直接用 window.location.origin + '/api/...' 转发不便；
  // 这里取当前后端 base（vite 代理过的话用同源）
  const base = import.meta.env.VITE_API_BASE || ''
  // 后端对静态文件是直挂 /static/..., storage 路径以 /data/materials 返回
  // 实际上 storage.save_bytes 把 /data/materials 转成 /static/materials 也可能，
  // 这里统一用 /static/materials/<filename> 兜底
  if (relUrl.startsWith('/static/')) return relUrl
  if (relUrl.startsWith('/data/materials/')) {
    const fname = relUrl.replace('/data/materials/', '')
    return `${base || ''}/static/materials/${fname}`
  }
  return relUrl
}

const defaultConfig = () => ({
  hairstyle: '',
  clothing: '',
  voice: '',
  description: '',
  script: '', // 仿真人口播词
})

const avatarForm = reactive({
  type: 'digital_human',
  name: '',
  gender: 'female',
  config: defaultConfig(),
  reference_image_url: '', // 数字人参考图 URL
  reference_video_url: '', // 仿真人参考视频 URL
  background_prompt: '', // 数字人背景描述（图生图 prompt）
  gen_background: false, // 是否生成带背景图
})

// 背景描述示例（点击直接填入）
const bgPromptExamples = [
  '现代办公室落地窗前，背景虚化',
  '海边日落，暖色调，电影感',
  '咖啡厅背景，柔和灯光',
  '科技感演播室，蓝色光带',
]

const filteredAvatars = computed(() => {
  if (activeTab.value === 'all') return avatars.value
  return avatars.value.filter((a) => a.type === activeTab.value)
})

async function loadAvatars() {
  loading.value = true
  try {
    avatars.value = await api.listAvatars()
  } catch {
    avatars.value = []
  } finally {
    loading.value = false
  }
}

function openCreate() {
  editingId.value = null
  avatarForm.type = 'digital_human'
  avatarForm.name = ''
  avatarForm.gender = 'female'
  avatarForm.config = defaultConfig()
  avatarForm.reference_image_url = ''
  avatarForm.reference_video_url = ''
  avatarForm.background_prompt = ''
  avatarForm.gen_background = false
  dialogVisible.value = true
}

function openEdit(row) {
  editingId.value = row.id
  avatarForm.type = row.type
  avatarForm.name = row.name
  avatarForm.gender = row.gender || ''
  avatarForm.config = { ...defaultConfig(), ...(row.config || {}) }
  avatarForm.reference_image_url = row.reference_image_url || (row.reference_images?.[0] || '')
  avatarForm.reference_video_url = row.reference_video_url || ''
  avatarForm.background_prompt = row.background_prompt || ''
  // 编辑时若已存在背景图，默认勾选（方便重新生成）；否则按有无描述推断
  avatarForm.gen_background = !!(row.background_image_url || avatarForm.background_prompt)
  dialogVisible.value = true
}

async function submitAvatar() {
  if (!avatarForm.name.trim()) {
    ElMessage.warning('请输入名称')
    return
  }
  if (avatarForm.type === 'digital_human' && !avatarForm.reference_image_url) {
    ElMessage.warning('请上传数字人参考图')
    return
  }
  if (avatarForm.type === 'simulation_human' && !avatarForm.reference_video_url) {
    ElMessage.warning('请上传仿真人参考视频')
    return
  }

  submitting.value = true
  try {
    const payload = {
      name: avatarForm.name.trim(),
      type: avatarForm.type,
      gender: avatarForm.gender || null,
      config: { ...avatarForm.config },
    }
    // Clean empty config values
    for (const key of Object.keys(payload.config)) {
      if (!payload.config[key]) delete payload.config[key]
    }

    if (avatarForm.type === 'digital_human') {
      payload.reference_image_url = avatarForm.reference_image_url || undefined
      payload.background_prompt = avatarForm.background_prompt || undefined
    } else if (avatarForm.type === 'simulation_human') {
      payload.reference_video_url = avatarForm.reference_video_url || undefined
    }

    if (editingId.value) {
      await api.updateAvatar(editingId.value, payload)
      ElMessage.success('已更新')
      dialogVisible.value = false
      await loadAvatars()
      return
    }

    // 新建：保存数字人
    const created = await api.createAvatar(payload)
    ElMessage.success('已创建')

    // 数字人 + 勾选「生成带背景图」→ 跳生成等待页，生成后挑选一张作预览图
    if (avatarForm.type === 'digital_human' && avatarForm.gen_background && avatarForm.background_prompt.trim()) {
      dialogVisible.value = false
      await startGenerateAndPick(created.id, avatarForm.background_prompt.trim())
      return
    }

    dialogVisible.value = false
    await loadAvatars()
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    submitting.value = false
  }
}

async function removeAvatar(row) {
  try {
    await ElMessageBox.confirm(`确定删除「${row.name}」？`, '删除', { type: 'warning' })
    await api.deleteAvatar(row.id)
    ElMessage.success('已删除')
    await loadAvatars()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error(e.message || '删除失败')
  }
}

function openThumbnail(row) {
  thumbnailAvatarId.value = row.id
  thumbnailFile.value = null
  thumbnailPreview.value = ''
  thumbnailDialogVisible.value = true
}

function onThumbnailFileChange(uploadFile) {
  const file = uploadFile.raw || uploadFile
  thumbnailFile.value = file
  thumbnailPreview.value = URL.createObjectURL(file)
}

async function uploadThumbnail() {
  if (!thumbnailFile.value || !thumbnailAvatarId.value) return
  uploadingThumbnail.value = true
  try {
    await api.uploadAvatarThumbnail(thumbnailAvatarId.value, thumbnailFile.value)
    ElMessage.success('预览图已上传')
    thumbnailDialogVisible.value = false
    await loadAvatars()
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    uploadingThumbnail.value = false
  }
}

// === 生成背景图 ===
async function openGenerateBg(row) {
  if (!row.reference_image_url) {
    ElMessage.warning('该数字人尚未上传参考图，无法生成背景')
    return
  }
  bgIsNewFlow.value = false
  bgAvatar.value = row
  bgCandidates.value = []
  bgGenerated.value = false
  bgPrompt.value = row.background_prompt || ''
  bgDialogVisible.value = true
}

async function generateBg() {
  if (!bgPrompt.value.trim()) {
    ElMessage.warning('请先填写背景描述')
    return
  }
  bgGenerating.value = true
  try {
    const resp = await api.generateAvatarBackground(bgAvatar.value.id, {
      background_prompt: bgPrompt.value,
      count: 1,
      ratio: '3:4',
    })
    bgCandidates.value = (resp.image_urls || []).map(absoluteMaterialUrl)
    bgGenerated.value = true
    await loadAvatars()
    ElMessage.success(`已生成 ${bgCandidates.value.length} 张候选图，第一张已自动存为视频背景图`)
  } catch (e) {
    ElMessage.error(e.message || '生成失败')
  } finally {
    bgGenerating.value = false
  }
}

async function applyBgCandidate(url) {
  bgSaving.value = true
  try {
    const relPath = String(url || '')
      .replace(import.meta.env.VITE_API_BASE || '', '')
      .replace('/static/materials/', '/data/materials/')
    await api.updateAvatar(bgAvatar.value.id, {
      thumbnail: relPath || url, // 后端存相对路径
      background_prompt: bgPrompt.value,
    })
    ElMessage.success('已保存为预览图')
    bgDialogVisible.value = false
    await loadAvatars()
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    bgSaving.value = false
  }
}

// 新建数字人后：跳生成等待页，自动生成候选图供挑选，可「跳过」直接用参考图
async function startGenerateAndPick(avatarId, prompt) {
  bgIsNewFlow.value = true
  bgAvatar.value = { id: avatarId }
  bgPrompt.value = prompt
  bgCandidates.value = []
  bgGenerated.value = false
  bgDialogVisible.value = true
  await generateBg()
}

// 新建流程：不挑选，直接用原始参考图作为预览图（背景图已生成第一张存在 background_image_url）
async function skipBg() {
  bgDialogVisible.value = false
  await loadAvatars()
  if (bgIsNewFlow.value) {
    ElMessage.info('已使用原始参考图作为预览图；带背景图仍可在列表中生成/更换')
  }
}

onMounted(loadAvatars)
</script>

<style scoped>
.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}
.toolbar .page-title {
  margin: 0;
}
.muted {
  color: #888;
  font-size: 13px;
}
</style>
