<template>
  <div>
    <div class="toolbar">
      <h2 class="page-title">素材库</h2>
      <div>
        <el-button @click="showAiGenerate = true">AI 生成图片</el-button>
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
        <el-table-column prop="type" label="类型" width="90" />
        <el-table-column prop="source" label="来源" width="100" />
        <el-table-column label="预览" width="100">
          <template #default="{ row }">
            <el-image
              v-if="row.type === 'image' && row.url"
              :src="row.url"
              :preview-src-list="[row.url]"
              fit="cover"
              class="thumb clickable"
              preview-teleported
            />
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column label="创建时间" width="180">
          <template #default="{ row }">{{ formatDateTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="100" fixed="right">
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

    <el-dialog v-model="showAiGenerate" title="AI 生成图片" width="480px">
      <el-form label-width="80px">
        <el-form-item label="主题">
          <el-input v-model="aiForm.topic" placeholder="如：春茶上新封面" />
        </el-form-item>
        <el-form-item label="封面文案">
          <el-input v-model="aiForm.cover_text" placeholder="可选，显示在封面上的文字" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showAiGenerate = false">取消</el-button>
        <el-button type="primary" :loading="aiGenerating" @click="submitAiGenerate">生成</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { api } from '@/api'
import { formatDateTime } from '@/utils/datetime'

const loading = ref(false)
const uploading = ref(false)
const materials = ref([])
const categories = ref([])
const showUpload = ref(false)
const showAiGenerate = ref(false)
const aiGenerating = ref(false)
const uploadFile = ref(null)
const filters = reactive({ category: '', material_type: '', keyword: '' })
const uploadForm = reactive({ name: '', category: '默认' })
const aiForm = reactive({ topic: '春茶上新', cover_text: '' })

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
    if (e !== 'cancel') ElMessage.error(e.message || '删除失败')
  }
}

async function submitUpload() {
  if (!uploadFile.value) return ElMessage.warning('请选择文件')
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
    ElMessage.error(e.message)
  } finally {
    uploading.value = false
  }
}

async function submitAiGenerate() {
  if (!aiForm.topic.trim()) return ElMessage.warning('请填写主题')
  aiGenerating.value = true
  try {
    await api.generateImage(aiForm.topic, 'xhs', '3:4', 1, aiForm.cover_text || undefined)
    ElMessage.success('图片已生成并入库')
    showAiGenerate.value = false
    load()
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    aiGenerating.value = false
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
</style>
