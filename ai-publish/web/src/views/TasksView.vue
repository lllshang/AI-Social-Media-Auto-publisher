<template>
  <div>
    <div class="toolbar">
      <h2 class="page-title">发布任务</h2>
      <el-button v-if="can('publish:write')" type="primary" @click="$router.push('/publish')">新建发布</el-button>
    </div>

    <div class="page-card filter-bar">
      <el-form inline>
        <el-form-item label="标题">
          <el-input v-model="filters.keyword" clearable placeholder="标题关键字" style="width: 160px" />
        </el-form-item>
        <el-form-item label="平台">
          <el-select v-model="filters.platform" clearable placeholder="全部" style="width: 110px">
            <el-option v-for="p in PLATFORMS" :key="p.value" :label="p.label" :value="p.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="filters.status" clearable placeholder="全部" style="width: 140px">
            <el-option v-for="s in statusOptions" :key="s.value" :label="s.label" :value="s.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="创建时间">
          <el-date-picker
            v-model="filters.dateRange"
            type="datetimerange"
            range-separator="至"
            start-placeholder="开始"
            end-placeholder="结束"
          />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="load">查询</el-button>
          <el-button @click="reset">重置</el-button>
        </el-form-item>
      </el-form>
    </div>

    <div class="page-card">
      <el-table :data="tasks" v-loading="loading">
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column prop="title" label="标题" show-overflow-tooltip />
        <el-table-column label="平台" width="90">
          <template #default="{ row }">{{ platformLabel(row.platform) }}</template>
        </el-table-column>
        <el-table-column label="类型" width="70">
          <template #default="{ row }">{{ contentTypeLabel(row.content_type) }}</template>
        </el-table-column>
        <el-table-column label="状态" width="110">
          <template #default="{ row }">
            <el-tag :type="statusType(row.status)">{{ statusLabel(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="计划时间" width="170">
          <template #default="{ row }">{{ row.publish_time ? formatDateTime(row.publish_time) : '-' }}</template>
        </el-table-column>
        <el-table-column label="创建时间" width="170">
          <template #default="{ row }">{{ formatDateTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" min-width="200" fixed="right">
          <template #default="{ row }">
            <div class="action-buttons">
              <el-button size="small" @click="showDetail(row)">详情</el-button>
              <el-button size="small" @click="showLogs(row)">日志</el-button>
              <el-button v-if="canEditDraft(row)" size="small" @click="editDraft(row)">继续编辑</el-button>
              <el-button v-if="canDelete(row)" size="small" type="danger" plain @click="removeDraft(row)">删除</el-button>
              <el-button v-if="canApprove(row)" size="small" type="success" @click="approve(row)">通过</el-button>
              <el-button v-if="canReject(row)" size="small" type="danger" @click="reject(row)">驳回</el-button>
              <el-button v-if="canReopen(row)" size="small" @click="reopen(row)">退回草稿</el-button>
              <el-button v-if="canExecute(row)" size="small" type="primary" @click="execute(row)">执行</el-button>
              <el-button v-if="canRetry(row)" size="small" type="warning" @click="retry(row)">重试</el-button>
            </div>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <el-drawer v-model="detailVisible" title="任务详情" size="520px">
      <template v-if="detail">
        <p><strong>标题：</strong>{{ detail.title }}</p>
        <p><strong>状态：</strong>{{ statusLabel(detail.status) }}</p>
        <p><strong>类型：</strong>{{ contentTypeLabel(detail.content_type) }}</p>
        <p v-if="detail.error_message"><strong>备注/错误：</strong>{{ detail.error_message }}</p>
        <p><strong>计划时间：</strong>{{ detail.publish_time ? formatDateTime(detail.publish_time) : '未设置' }}</p>
        <p><strong>正文：</strong></p>
        <pre class="block">{{ detail.content || '-' }}</pre>
        <p><strong>评论引导：</strong></p>
        <el-input v-model="detail.comment_guide" type="textarea" :rows="2" readonly />
        <el-button size="small" style="margin-top: 8px" @click="copyComment">复制评论引导</el-button>
        <p style="margin-top: 12px"><strong>素材：</strong></p>
        <ul v-if="detail.materials?.length">
          <li v-for="m in detail.materials" :key="m.id">#{{ m.id }} {{ m.name || m.type }} — {{ m.url || '-' }}</li>
        </ul>
        <el-empty v-else description="无关联素材" />
      </template>
    </el-drawer>

    <el-drawer v-model="logVisible" title="任务日志" size="480px">
      <el-timeline v-if="logs.length">
        <el-timeline-item v-for="log in logs" :key="log.id" :timestamp="formatDateTime(log.created_at)">
          [{{ log.step }}] {{ log.status }} — {{ log.message || '' }}
        </el-timeline-item>
      </el-timeline>
      <el-empty v-else description="暂无日志" />
    </el-drawer>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { api } from '@/api'
import { PLATFORMS, contentTypeLabel, platformLabel } from '@/constants/platforms'
import { formatDateTime } from '@/utils/datetime'
import { usePermission } from '@/composables/usePermission'

const { can } = usePermission()

const route = useRoute()
const router = useRouter()
const loading = ref(false)
const tasks = ref([])
const logVisible = ref(false)
const detailVisible = ref(false)
const logs = ref([])
const detail = ref(null)

const statusOptions = [
  { value: 'draft', label: '草稿' },
  { value: 'pending_review', label: '待审核' },
  { value: 'pending', label: '待发布' },
  { value: 'running', label: '执行中' },
  { value: 'success', label: '成功' },
  { value: 'failed', label: '失败' },
  { value: 'rejected', label: '已驳回' },
]

const filters = reactive({
  keyword: '',
  platform: '',
  status: '',
  dateRange: [],
})

const statusMap = Object.fromEntries(statusOptions.map((s) => [s.value, s.label]))

function statusLabel(status) {
  return statusMap[status] || status
}

function statusType(status) {
  const map = {
    success: 'success',
    failed: 'danger',
    running: 'warning',
    pending: 'info',
    pending_review: 'warning',
    rejected: 'danger',
    draft: 'info',
  }
  return map[status] || 'info'
}

function canEditDraft(row) {
  return can('publish:write') && row.status === 'draft'
}

function canDelete(row) {
  return can('tasks:write') && row.status === 'draft'
}

function canExecute(row) {
  return can('tasks:execute') && row.status === 'pending'
}

function canRetry(row) {
  return can('tasks:execute') && row.status === 'failed'
}

function canApprove(row) {
  return can('tasks:write') && row.status === 'pending_review'
}

function canReject(row) {
  return can('tasks:write') && row.status === 'pending_review'
}

function canReopen(row) {
  return can('tasks:write') && row.status === 'rejected'
}

function buildParams() {
  const params = {}
  if (filters.keyword) params.keyword = filters.keyword
  if (filters.platform) params.platform = filters.platform
  if (filters.status) params.status = filters.status
  if (filters.dateRange?.length === 2) {
    params.created_from = new Date(filters.dateRange[0]).toISOString()
    params.created_to = new Date(filters.dateRange[1]).toISOString()
  }
  return params
}

async function load() {
  loading.value = true
  try {
    tasks.value = await api.listTasks(buildParams())
  } finally {
    loading.value = false
  }
}

function reset() {
  filters.keyword = ''
  filters.platform = ''
  filters.status = ''
  filters.dateRange = []
  load()
}

async function showDetail(row) {
  detail.value = await api.getTask(row.id)
  detailVisible.value = true
}

async function showLogs(row) {
  logs.value = await api.getTaskLogs(row.id)
  logVisible.value = true
}

function editDraft(row) {
  router.push({ path: '/publish', query: { id: row.id } })
}

async function removeDraft(row) {
  try {
    await ElMessageBox.confirm(`确定删除草稿「${row.title}」？删除后不可恢复。`, '删除草稿', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })
    await api.deleteTask(row.id)
    ElMessage.success('草稿已删除')
    load()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error(e.message || '删除失败')
  }
}

async function copyComment() {
  if (!detail.value?.comment_guide) return ElMessage.warning('无评论引导内容')
  try {
    await navigator.clipboard.writeText(detail.value.comment_guide)
    ElMessage.success('已复制')
  } catch {
    ElMessage.error('复制失败')
  }
}

async function execute(row) {
  try {
    await api.executeTask(row.id)
    ElMessage.success('已开始执行，请等待浏览器完成发布')
    setTimeout(load, 2000)
  } catch (e) {
    ElMessage.error(e.message)
  }
}

async function retry(row) {
  try {
    await api.retryTask(row.id)
    ElMessage.success('已重置为待发布')
    load()
  } catch (e) {
    ElMessage.error(e.message)
  }
}

async function approve(row) {
  try {
    await api.approveTask(row.id)
    ElMessage.success('已通过审核，任务进入待发布')
    load()
  } catch (e) {
    ElMessage.error(e.message)
  }
}

async function reopen(row) {
  try {
    await api.reopenTask(row.id)
    ElMessage.success('已退回草稿，可继续编辑')
    load()
  } catch (e) {
    ElMessage.error(e.message)
  }
}

async function reject(row) {
  try {
    const { value } = await ElMessageBox.prompt('请输入驳回原因（可选）', '驳回任务', {
      confirmButtonText: '驳回',
      cancelButtonText: '取消',
      inputPlaceholder: '如：标题不合规',
    })
    await api.rejectTask(row.id, value || undefined)
    ElMessage.success('已驳回')
    load()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error(e.message || '驳回失败')
  }
}

onMounted(() => {
  if (route.query.status) {
    filters.status = String(route.query.status)
  }
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
.action-buttons {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.block {
  white-space: pre-wrap;
  background: #f5f5f5;
  padding: 8px;
  border-radius: 4px;
  font-size: 13px;
}
</style>
