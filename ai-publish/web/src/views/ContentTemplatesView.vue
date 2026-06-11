<template>
  <div>
    <div class="toolbar">
      <h2 class="page-title">内容模板</h2>
      <el-button v-if="can('templates:write')" type="primary" @click="openCreate">新建模板</el-button>
    </div>

    <div class="page-card filter-bar">
      <el-form inline>
        <el-form-item label="行业">
          <el-select v-model="filters.industry" clearable placeholder="全部行业" style="width: 140px">
            <el-option v-for="c in industries" :key="c" :label="c" :value="c" />
          </el-select>
        </el-form-item>
        <el-form-item label="平台">
          <el-select v-model="filters.platform" clearable placeholder="全部平台" style="width: 140px">
            <el-option v-for="p in PLATFORMS" :key="p.value" :label="p.label" :value="p.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="filters.status" clearable placeholder="全部状态" style="width: 120px">
            <el-option label="启用" value="active" />
            <el-option label="停用" value="disabled" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="load">查询</el-button>
          <el-button @click="resetFilters">重置</el-button>
        </el-form-item>
      </el-form>
    </div>

    <div class="page-card">
      <el-table :data="templates" v-loading="loading">
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column prop="name" label="名称" min-width="140" show-overflow-tooltip />
        <el-table-column prop="industry" label="行业" width="100" />
        <el-table-column label="平台" width="100">
          <template #default="{ row }">{{ row.platform ? platformLabel(row.platform) : '通用' }}</template>
        </el-table-column>
        <el-table-column label="类型" width="90">
          <template #default="{ row }">{{ row.content_type === 'video' ? '视频' : '图文' }}</template>
        </el-table-column>
        <el-table-column prop="topic" label="主题" min-width="160" show-overflow-tooltip />
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="row.status === 'active' ? 'success' : 'info'">
              {{ row.status === 'active' ? '启用' : '停用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="180" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="preview(row)">预览</el-button>
            <el-button v-if="can('templates:write')" size="small" @click="openEdit(row)">编辑</el-button>
            <el-button
              v-if="can('templates:write')"
              size="small"
              :type="row.status === 'active' ? 'warning' : 'success'"
              @click="toggleStatus(row)"
            >
              {{ row.status === 'active' ? '停用' : '启用' }}
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <el-dialog v-model="showForm" :title="formMode === 'create' ? '新建模板' : '编辑模板'" width="640px">
      <el-form label-width="100px">
        <el-form-item label="名称" required>
          <el-input v-model="form.name" />
        </el-form-item>
        <el-form-item label="行业" required>
          <el-input v-model="form.industry" placeholder="如：茶叶、电商" />
        </el-form-item>
        <el-form-item label="平台">
          <el-select v-model="form.platform" clearable placeholder="留空表示通用" style="width: 100%">
            <el-option v-for="p in PLATFORMS" :key="p.value" :label="p.label" :value="p.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="内容类型">
          <el-radio-group v-model="form.content_type">
            <el-radio value="note">图文</el-radio>
            <el-radio value="video">视频</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="主题" required>
          <el-input v-model="form.topic" />
        </el-form-item>
        <el-form-item label="标题提示">
          <el-input v-model="form.title_hint" />
        </el-form-item>
        <el-form-item label="文案骨架">
          <el-input v-model="form.content_body" type="textarea" :rows="4" />
        </el-form-item>
        <el-form-item label="标签">
          <el-input v-model="form.tagsText" placeholder="逗号分隔" />
        </el-form-item>
        <el-form-item label="图片风格">
          <el-select v-model="form.image_style" clearable style="width: 100%">
            <el-option v-for="s in IMAGE_STYLES" :key="s.value" :label="s.label" :value="s.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="图片比例">
          <el-input v-model="form.image_ratio" placeholder="如 3:4、9:16" />
        </el-form-item>
        <el-form-item label="品牌色">
          <el-input v-model="form.brand_color" placeholder="#2E8B57" />
        </el-form-item>
        <el-form-item label="品牌说明">
          <el-input v-model="form.brand_hint" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showForm = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submitForm">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="showPreview" title="模板预览" width="560px">
      <el-descriptions v-if="previewRow" :column="1" border>
        <el-descriptions-item label="名称">{{ previewRow.name }}</el-descriptions-item>
        <el-descriptions-item label="行业">{{ previewRow.industry }}</el-descriptions-item>
        <el-descriptions-item label="平台">
          {{ previewRow.platform ? platformLabel(previewRow.platform) : '通用' }}
        </el-descriptions-item>
        <el-descriptions-item label="主题">{{ previewRow.topic }}</el-descriptions-item>
        <el-descriptions-item label="标题提示">{{ previewRow.title_hint || '-' }}</el-descriptions-item>
        <el-descriptions-item label="文案骨架">
          <pre class="preview-body">{{ previewRow.content_body || '-' }}</pre>
        </el-descriptions-item>
        <el-descriptions-item label="标签">
          {{ (previewRow.tags || []).join('、') || '-' }}
        </el-descriptions-item>
        <el-descriptions-item label="文生图">
          {{ previewRow.image_style || '-' }} / {{ previewRow.image_ratio || '-' }}
        </el-descriptions-item>
        <el-descriptions-item label="品牌">
          {{ previewRow.brand_color || '-' }} — {{ previewRow.brand_hint || '-' }}
        </el-descriptions-item>
      </el-descriptions>
      <template #footer>
        <el-button v-if="can('publish:write')" type="primary" @click="useInPublish">用于发布</el-button>
        <el-button @click="showPreview = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { api } from '@/api'
import { PLATFORMS, platformLabel } from '@/constants/platforms'
import { IMAGE_STYLES } from '@/constants/imageStyles'
import { usePermission } from '@/composables/usePermission'

const router = useRouter()
const { can } = usePermission()

const loading = ref(false)
const saving = ref(false)
const templates = ref([])
const industries = ref([])
const showForm = ref(false)
const showPreview = ref(false)
const formMode = ref('create')
const editingId = ref(null)
const previewRow = ref(null)

const filters = reactive({
  industry: '',
  platform: '',
  status: '',
})

const emptyForm = () => ({
  name: '',
  industry: '',
  platform: '',
  content_type: 'note',
  template_kind: 'bundle',
  topic: '',
  title_hint: '',
  content_body: '',
  tagsText: '',
  image_style: '',
  image_ratio: '',
  brand_color: '',
  brand_hint: '',
})

const form = reactive(emptyForm())

function resetFilters() {
  filters.industry = ''
  filters.platform = ''
  filters.status = ''
  load()
}

async function load() {
  loading.value = true
  try {
    const params = {}
    if (filters.industry) params.industry = filters.industry
    if (filters.platform) params.platform = filters.platform
    if (filters.status) {
      params.status = filters.status
      params.include_disabled = true
    } else {
      params.include_disabled = true
    }
    const [rows, industryData] = await Promise.all([
      api.listContentTemplates(params),
      api.listTemplateIndustries(),
    ])
    templates.value = rows
    industries.value = industryData.items || []
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    loading.value = false
  }
}

function openCreate() {
  formMode.value = 'create'
  editingId.value = null
  Object.assign(form, emptyForm())
  showForm.value = true
}

function openEdit(row) {
  formMode.value = 'edit'
  editingId.value = row.id
  Object.assign(form, {
    name: row.name,
    industry: row.industry,
    platform: row.platform || '',
    content_type: row.content_type,
    template_kind: row.template_kind,
    topic: row.topic,
    title_hint: row.title_hint || '',
    content_body: row.content_body || '',
    tagsText: (row.tags || []).join('，'),
    image_style: row.image_style || '',
    image_ratio: row.image_ratio || '',
    brand_color: row.brand_color || '',
    brand_hint: row.brand_hint || '',
  })
  showForm.value = true
}

function buildPayload() {
  const tags = form.tagsText
    .split(/[,，]/)
    .map((t) => t.trim())
    .filter(Boolean)
  return {
    name: form.name.trim(),
    industry: form.industry.trim(),
    platform: form.platform || null,
    content_type: form.content_type,
    template_kind: form.template_kind,
    topic: form.topic.trim(),
    title_hint: form.title_hint || null,
    content_body: form.content_body || null,
    tags,
    image_style: form.image_style || null,
    image_ratio: form.image_ratio || null,
    brand_color: form.brand_color || null,
    brand_hint: form.brand_hint || null,
    status: 'active',
  }
}

async function submitForm() {
  if (!form.name.trim() || !form.industry.trim() || !form.topic.trim()) {
    ElMessage.warning('请填写名称、行业与主题')
    return
  }
  saving.value = true
  try {
    const payload = buildPayload()
    if (formMode.value === 'create') {
      await api.createContentTemplate(payload)
      ElMessage.success('模板已创建')
    } else {
      await api.updateContentTemplate(editingId.value, payload)
      ElMessage.success('模板已更新')
    }
    showForm.value = false
    await load()
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    saving.value = false
  }
}

async function toggleStatus(row) {
  const next = row.status === 'active' ? 'disabled' : 'active'
  try {
    await api.updateContentTemplate(row.id, { status: next })
    ElMessage.success(next === 'active' ? '已启用' : '已停用')
    await load()
  } catch (e) {
    ElMessage.error(e.message)
  }
}

function preview(row) {
  previewRow.value = row
  showPreview.value = true
}

function useInPublish() {
  if (!previewRow.value) return
  const row = previewRow.value
  router.push({
    path: '/publish',
    query: {
      template_id: row.id,
      platform: row.platform || undefined,
      content_type: row.content_type || undefined,
    },
  })
}

onMounted(load)
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
.filter-bar {
  margin-bottom: 16px;
}
.preview-body {
  white-space: pre-wrap;
  margin: 0;
  font-family: inherit;
}
</style>
