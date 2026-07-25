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

        <!-- Digital human appearance config -->
        <template v-if="avatarForm.type === 'digital_human'">
          <el-form-item label="发型">
            <el-select v-model="avatarForm.config.hairstyle" style="width: 100%">
              <el-option label="短发" value="short" />
              <el-option label="长发" value="long" />
              <el-option label="卷发" value="curly" />
              <el-option label="马尾" value="ponytail" />
            </el-select>
          </el-form-item>
          <el-form-item label="服装">
            <el-select v-model="avatarForm.config.clothing" style="width: 100%">
              <el-option label="商务正装" value="business" />
              <el-option label="休闲装" value="casual" />
              <el-option label="传统服饰" value="traditional" />
              <el-option label="运动装" value="sportswear" />
            </el-select>
          </el-form-item>
          <el-form-item label="声音">
            <el-select v-model="avatarForm.config.voice" style="width: 100%">
              <el-option label="标准女声" value="female_standard" />
              <el-option label="标准男声" value="male_standard" />
              <el-option label="温柔女声" value="female_soft" />
              <el-option label="沉稳男声" value="male_deep" />
            </el-select>
          </el-form-item>
        </template>

        <!-- Simulation human reference -->
        <template v-if="avatarForm.type === 'simulation_human'">
          <el-form-item label="描述">
            <el-input v-model="avatarForm.config.description" type="textarea" :rows="2" placeholder="仿真人外貌、风格等描述" />
          </el-form-item>
          <el-form-item label="声音">
            <el-select v-model="avatarForm.config.voice" style="width: 100%">
              <el-option label="克隆原声" value="clone" />
              <el-option label="标准女声" value="female_standard" />
              <el-option label="标准男声" value="male_standard" />
            </el-select>
          </el-form-item>
          <el-form-item label="参考照片">
            <p class="muted">上传真人照片，S2V-01 会据此生成仿真人视频。照片将自动保存到素材库。</p>
            <el-upload
              :auto-upload="false"
              :show-file-list="false"
              accept="image/*"
              @change="onRefPhotoChange"
            >
              <el-button>选择照片</el-button>
            </el-upload>
            <div v-if="refPhotoPreview" style="margin-top: 8px">
              <img :src="refPhotoPreview" style="max-width: 160px; max-height: 160px; border-radius: 8px" />
              <el-button size="small" type="danger" plain style="margin-left: 8px" @click="clearRefPhoto">清除</el-button>
            </div>
            <div v-if="existingRefImages.length" style="margin-top: 8px">
              <p class="muted">已保存的参考照片：</p>
              <div style="display: flex; gap: 8px; flex-wrap: wrap">
                <div v-for="img in existingRefImages" :key="img.id" style="position: relative">
                  <el-image :src="img.url" fit="cover" style="width: 80px; height: 80px; border-radius: 4px" />
                </div>
              </div>
            </div>
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

// Reference photo for simulation_human
const refPhotoFile = ref(null)
const refPhotoPreview = ref('')
const existingRefImages = ref([])
const uploadingRefPhoto = ref(false)

const defaultConfig = () => ({
  hairstyle: '',
  clothing: '',
  voice: '',
  description: '',
})

const avatarForm = reactive({
  type: 'digital_human',
  name: '',
  gender: 'female',
  config: defaultConfig(),
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
  existingRefImages.value = []
  clearRefPhoto()
  dialogVisible.value = true
}

function openEdit(row) {
  editingId.value = row.id
  avatarForm.type = row.type
  avatarForm.name = row.name
  avatarForm.gender = row.gender || ''
  avatarForm.config = { ...defaultConfig(), ...(row.config || {}) }
  // Load existing reference images
  existingRefImages.value = []
  clearRefPhoto()
  if (row.reference_images && row.reference_images.length) {
    loadRefImageDetails(row.reference_images)
  }
  dialogVisible.value = true
}

async function submitAvatar() {
  if (!avatarForm.name.trim()) {
    ElMessage.warning('请输入名称')
    return
  }
  // Simulation human with ref photo: upload first
  if (avatarForm.type === 'simulation_human' && refPhotoFile.value) {
    uploadingRefPhoto.value = true
    try {
      const uploadRes = await api.uploadMaterial(refPhotoFile.value, {
        name: `仿真人参考照片_${avatarForm.name.trim()}`,
        category: '仿真人参考',
      })
      // Collect reference image IDs: existing + newly uploaded
      const existingIds = (existingRefImages.value || []).map((img) => img.id)
      avatarForm.reference_images = [...existingIds, uploadRes.id]
    } catch (e) {
      ElMessage.error(`参考照片上传失败: ${e.message}`)
      uploadingRefPhoto.value = false
      return
    } finally {
      uploadingRefPhoto.value = false
    }
  }

  submitting.value = true
  try {
    const payload = {
      name: avatarForm.name.trim(),
      type: avatarForm.type,
      gender: avatarForm.gender || null,
      config: { ...avatarForm.config },
      reference_images: avatarForm.reference_images || undefined,
    }
    // Clean empty config values
    for (const key of Object.keys(payload.config)) {
      if (!payload.config[key]) delete payload.config[key]
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

// Reference photo handling
function onRefPhotoChange(uploadFile) {
  const file = uploadFile.raw || uploadFile
  refPhotoFile.value = file
  refPhotoPreview.value = URL.createObjectURL(file)
}

function clearRefPhoto() {
  refPhotoFile.value = null
  refPhotoPreview.value = ''
}

async function loadRefImageDetails(ids) {
  // Fetch material details for each reference image ID
  try {
    const mats = await api.listMaterials()
    existingRefImages.value = ids
      .map((id) => mats.find((m) => m.id === id))
      .filter(Boolean)
      .map((m) => ({ id: m.id, url: m.url || m.thumbnail_url }))
  } catch {
    existingRefImages.value = []
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
