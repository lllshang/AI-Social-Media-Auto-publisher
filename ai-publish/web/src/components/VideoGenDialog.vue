<template>
  <el-dialog v-model="visible" title="AI 视频生成" width="600px" @open="onOpen">
    <el-form label-width="100px">
      <el-form-item label="视频描述" required>
        <el-input v-model="description" type="textarea" :rows="4" placeholder="描述你想要生成的视频内容" />
      </el-form-item>
      <el-form-item label="生成方式">
        <el-radio-group v-model="genMode">
          <el-radio value="t2v">文生视频</el-radio>
          <el-radio value="i2v">照片生成视频</el-radio>
          <el-radio value="digital_human">数字人</el-radio>
          <el-radio value="simulation_human">仿真人</el-radio>
        </el-radio-group>
      </el-form-item>
      <el-form-item v-if="genMode === 'i2v'" label="驱动照片" required>
        <el-upload
          :auto-upload="false"
          :show-file-list="false"
          accept="image/*"
          @change="onDriverPhotoChange"
        >
          <el-button>选择照片</el-button>
        </el-upload>
        <div v-if="driverPhotoPreview" style="margin-top: 8px">
          <img :src="driverPhotoPreview" style="max-width: 200px; max-height: 200px; border-radius: 8px" />
          <el-button size="small" type="danger" plain style="margin-left: 8px" @click="clearDriverPhoto">清除</el-button>
        </div>
        <p class="muted" style="margin-top: 4px">上传人物照片，AI 将生成仿真人说话/动作视频</p>
      </el-form-item>
      <el-form-item v-if="genMode === 'digital_human'" label="选择数字人" required>
        <el-select v-model="selectedAvatarId" placeholder="选择数字人" style="width: 100%">
          <el-option v-for="a in digitalHumanAvatars" :key="a.id" :label="a.name" :value="a.id" />
        </el-select>
        <p v-if="!digitalHumanAvatars.length" class="muted">暂无数字人，请先在「数字人 / 仿真人」页创建。</p>
      </el-form-item>
      <el-form-item v-if="genMode === 'simulation_human'" label="选择仿真人" required>
        <el-select v-model="selectedAvatarId" placeholder="选择仿真人" style="width: 100%">
          <el-option v-for="a in simulationHumanAvatars" :key="a.id" :label="a.name" :value="a.id" />
        </el-select>
        <p v-if="!simulationHumanAvatars.length" class="muted">暂无仿真人，请先在「数字人 / 仿真人」页创建。</p>
      </el-form-item>
      <el-form-item v-if="videoError" label=" ">
        <el-alert type="error" :closable="true" :title="videoError" @close="videoError = ''" show-icon />
      </el-form-item>
    </el-form>
    <template #footer>
      <span class="cost-tag" style="margin-right: auto">预估 ¥2.50 (5秒)</span>
      <el-button @click="visible = false">取消</el-button>
      <el-button type="primary" :loading="generating" :disabled="!canGenerate" @click="confirmGenerate">确认生成</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { api } from '@/api'

const props = defineProps({
  modelValue: Boolean,
  topic: { type: String, default: '' },
  platform: { type: String, default: 'xhs' },
})
const emit = defineEmits(['update:modelValue', 'generated'])

const visible = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val),
})

const description = ref('')
const genMode = ref('t2v')
const driverPhotoFile = ref(null)
const driverPhotoPreview = ref('')
const generating = ref(false)
const avatars = ref([])
const selectedAvatarId = ref(null)
const videoError = ref('')

const digitalHumanAvatars = computed(() => avatars.value.filter((a) => a.type === 'digital_human'))
const simulationHumanAvatars = computed(() => avatars.value.filter((a) => a.type === 'simulation_human'))

const canGenerate = computed(() => {
  if (!description.value.trim()) return false
  if (genMode.value === 'i2v' && !driverPhotoFile.value) return false
  if (genMode.value === 'digital_human' && !selectedAvatarId.value) return false
  if (genMode.value === 'simulation_human' && !selectedAvatarId.value) return false
  return true
})

async function onOpen() {
  description.value = props.topic || ''
  genMode.value = 't2v'
  selectedAvatarId.value = null
  clearDriverPhoto()
  videoError.value = ''
  try {
    avatars.value = await api.listAvatars()
  } catch {
    avatars.value = []
  }
}

function onDriverPhotoChange(uploadFile) {
  const file = uploadFile.raw || uploadFile
  driverPhotoFile.value = file
  driverPhotoPreview.value = URL.createObjectURL(file)
}

function clearDriverPhoto() {
  driverPhotoFile.value = null
  driverPhotoPreview.value = ''
}

function platformVideoResolution(platform) {
  if (['douyin', 'kuaishou'].includes(platform)) return 'portrait'
  return '720p'
}

async function confirmGenerate() {
  if (!description.value.trim()) {
    ElMessage.warning('请输入视频描述')
    return
  }
  if (genMode.value === 'i2v' && !driverPhotoFile.value) {
    ElMessage.warning('请上传驱动照片')
    return
  }
  if ((genMode.value === 'digital_human' || genMode.value === 'simulation_human') && !selectedAvatarId.value) {
    ElMessage.warning(genMode.value === 'digital_human' ? '请选择数字人' : '请选择仿真人')
    return
  }

  generating.value = true
  videoError.value = ''
  try {
    let imageUrl = null
    let avatarId = null
    let avatarType = null

    if (genMode.value === 'i2v' && driverPhotoFile.value) {
      const uploadRes = await api.uploadMaterial(driverPhotoFile.value, {
        name: '驱动照片',
        category: '视频驱动',
      })
      imageUrl = uploadRes.url
    }

    if (genMode.value === 'digital_human' || genMode.value === 'simulation_human') {
      avatarId = selectedAvatarId.value
      avatarType = genMode.value
    }

    const res = await api.generateVideo({
      topic: description.value.trim(),
      platform: props.platform,
      duration: 5,
      resolution: platformVideoResolution(props.platform),
      fps: 24,
      image_url: imageUrl,
      avatar_id: avatarId,
      avatar_type: avatarType,
    })

    const mat = res.materials?.[0]
    if (!mat) throw new Error('未返回视频素材')

    if (mat.url?.includes('stub')) {
      ElMessage.warning('当前为占位视频，请配置 MiniMax 或通义 API Key')
    } else {
      ElMessage.success(`视频已生成 (${res.provider}, ${mat.duration || 5}s)`)
    }

    emit('generated', res)
    visible.value = false
  } catch (e) {
    videoError.value = e.message || '视频生成失败'
  } finally {
    generating.value = false
  }
}

watch(visible, (val) => {
  if (!val) clearDriverPhoto()
})
</script>

<style scoped>
.muted {
  color: #888;
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
