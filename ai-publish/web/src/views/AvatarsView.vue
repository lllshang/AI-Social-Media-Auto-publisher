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
          <el-image v-if="row.thumbnail_url" :src="row.thumbnail_url" fit="cover" style="width: 48px; height: 48px; border-radius: 4px" />
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
      <el-table-column label="操作" width="220">
        <template #default="{ row }">
          <el-button size="small" @click="openEdit(row)">编辑</el-button>
          <el-button size="small" @click="openThumbnail(row)">上传预览图</el-button>
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
})

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
    } else if (avatarForm.type === 'simulation_human') {
      payload.reference_video_url = avatarForm.reference_video_url || undefined
    }

    if (editingId.value) {
      await api.updateAvatar(editingId.value, payload)
      ElMessage.success('已更新')
    } else {
      await api.createAvatar(payload)
      ElMessage.success('已创建')
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
