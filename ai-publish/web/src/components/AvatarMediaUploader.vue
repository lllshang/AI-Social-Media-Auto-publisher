<template>
  <div class="avatar-media-uploader">
    <el-upload
      :auto-upload="false"
      :show-file-list="false"
      :accept="accept"
      :disabled="uploading"
      @change="onFileChange"
    >
      <el-button :loading="uploading">
        {{ modelValue ? '重新选择' : `选择${label}` }}
      </el-button>
    </el-upload>

    <!-- 图片预览 -->
    <div v-if="modelValue && isImage" class="preview-box">
      <img :src="modelValue" class="preview-media" />
      <el-button size="small" type="danger" plain class="clear-btn" @click="clear">清除</el-button>
    </div>

    <!-- 视频预览 -->
    <div v-else-if="modelValue && isVideo" class="preview-box">
      <video :src="modelValue" controls class="preview-media" />
      <el-button size="small" type="danger" plain class="clear-btn" @click="clear">清除</el-button>
    </div>

    <p v-if="hint" class="muted">{{ hint }}</p>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { api } from '@/api'

const props = defineProps({
  modelValue: { type: String, default: '' },
  mediaType: { type: String, default: 'image' }, // image | video
  label: { type: String, default: '素材' },
  hint: { type: String, default: '' },
  category: { type: String, default: '数字人参考' },
})
const emit = defineEmits(['update:modelValue'])

const uploading = ref(false)
const isImage = computed(() => props.mediaType === 'image')
const isVideo = computed(() => props.mediaType === 'video')
const accept = computed(() => (props.mediaType === 'video' ? 'video/*' : 'image/*'))

function onFileChange(uploadFile) {
  const file = uploadFile.raw || uploadFile
  if (!file) return
  doUpload(file)
}

async function doUpload(file) {
  uploading.value = true
  try {
    const res = await api.uploadMaterial(file, {
      name: `${props.label}_${file.name}`,
      category: props.category,
    })
    emit('update:modelValue', res.url || res.thumbnail_url || res.file_url)
    ElMessage.success('上传成功')
  } catch (e) {
    ElMessage.error(`上传失败: ${e.message}`)
  } finally {
    uploading.value = false
  }
}

function clear() {
  emit('update:modelValue', '')
}
</script>

<style scoped>
.avatar-media-uploader {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.preview-box {
  position: relative;
  display: inline-block;
  max-width: 200px;
}
.preview-media {
  max-width: 200px;
  max-height: 200px;
  border-radius: 8px;
  display: block;
}
.clear-btn {
  margin-top: 6px;
}
.muted {
  color: #888;
  font-size: 13px;
  margin: 0;
}
</style>
