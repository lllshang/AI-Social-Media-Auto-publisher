<template>
  <div>
    <h2 class="page-title">内容审核</h2>

    <el-tabs v-model="activeTab" @tab-change="onTabChange">
      <el-tab-pane label="待审核" name="pending" />
      <el-tab-pane label="审核历史" name="history" />
    </el-tabs>

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
        <el-form-item v-if="activeTab === 'history'" label="结果">
          <el-select v-model="filters.action" clearable placeholder="全部" style="width: 110px">
            <el-option label="通过" value="approved" />
            <el-option label="驳回" value="rejected" />
          </el-select>
        </el-form-item>
        <el-form-item label="时间">
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

    <div v-if="activeTab === 'pending'" class="page-card">
      <el-table :data="pendingItems" v-loading="loading">
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column prop="title" label="标题" show-overflow-tooltip />
        <el-table-column label="平台" width="90">
          <template #default="{ row }">{{ platformLabel(row.platform) }}</template>
        </el-table-column>
        <el-table-column label="发布账号" min-width="120" show-overflow-tooltip>
          <template #default="{ row }">{{ row.account_name || `#${row.account_id}` }}</template>
        </el-table-column>
        <el-table-column label="类型" width="70">
          <template #default="{ row }">{{ contentTypeLabel(row.content_type) }}</template>
        </el-table-column>
        <el-table-column label="提交时间" width="170">
          <template #default="{ row }">{{ formatDateTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" min-width="200" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="showDetail(row)">预览</el-button>
            <el-button v-if="canReview" size="small" type="success" @click="approve(row)">通过</el-button>
            <el-button v-if="canReview" size="small" type="danger" @click="reject(row)">驳回</el-button>
          </template>
        </el-table-column>
      </el-table>
      <div class="pager">
        <el-pagination
          v-model:current-page="page"
          v-model:page-size="pageSize"
          :total="total"
          layout="total, prev, pager, next"
          @current-change="load"
        />
      </div>
    </div>

    <div v-else class="page-card">
      <el-table :data="historyItems" v-loading="loading">
        <el-table-column prop="id" label="记录ID" width="80" />
        <el-table-column prop="task_title" label="任务标题" show-overflow-tooltip />
        <el-table-column label="平台" width="90">
          <template #default="{ row }">{{ platformLabel(row.platform) }}</template>
        </el-table-column>
        <el-table-column label="结果" width="90">
          <template #default="{ row }">
            <el-tag :type="row.action === 'approved' ? 'success' : 'danger'">
              {{ row.action === 'approved' ? '通过' : '驳回' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="reviewer_name" label="审核人" width="120" />
        <el-table-column prop="comment" label="备注/原因" min-width="160" show-overflow-tooltip />
        <el-table-column label="审核时间" width="170">
          <template #default="{ row }">{{ formatDateTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="90" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="showHistoryDetail(row)">详情</el-button>
          </template>
        </el-table-column>
      </el-table>
      <div class="pager">
        <el-pagination
          v-model:current-page="page"
          v-model:page-size="pageSize"
          :total="total"
          layout="total, prev, pager, next"
          @current-change="load"
        />
      </div>
    </div>

    <el-drawer v-model="detailVisible" title="内容预览" size="560px">
      <template v-if="detail">
        <p><strong>标题：</strong>{{ detail.title }}</p>
        <p><strong>平台：</strong>{{ platformLabel(detail.platform) }}</p>
        <p><strong>发布账号：</strong>{{ detail.account_name || `#${detail.account_id}` }}</p>
        <p v-if="detail.worker_name"><strong>执行机器：</strong>{{ detail.worker_name }}</p>
        <p><strong>类型：</strong>{{ contentTypeLabel(detail.content_type) }}</p>
        <p v-if="detail.topic"><strong>主题：</strong>{{ detail.topic }}</p>
        <p v-if="detail.cover_text"><strong>封面文案：</strong>{{ detail.cover_text }}</p>
        <p><strong>正文：</strong></p>
        <pre class="block">{{ detail.content || '-' }}</pre>
        <p v-if="detail.comment_guide"><strong>评论引导：</strong></p>
        <pre v-if="detail.comment_guide" class="block">{{ detail.comment_guide }}</pre>
        <p v-if="detail.tags?.length"><strong>标签：</strong>{{ detail.tags.join('、') }}</p>
        <p style="margin-top: 12px"><strong>素材：</strong></p>
        <div v-if="detail.materials?.length" class="material-grid">
          <div v-for="m in detail.materials" :key="m.id" class="material-item">
            <el-image
              v-if="m.type === 'image' && m.url"
              :src="m.url"
              fit="cover"
              :preview-src-list="[m.url]"
              preview-teleported
              style="width: 120px; height: 120px"
            />
            <video v-else-if="m.type === 'video' && m.url" :src="m.url" controls style="max-width: 100%; max-height: 200px" />
            <span v-else>#{{ m.id }} {{ m.name || m.type }}</span>
          </div>
        </div>
        <el-empty v-else description="无关联素材" />
        <div v-if="canReview && detail.status === 'pending_review'" class="drawer-actions">
          <el-button type="success" @click="approve(detail)">通过</el-button>
          <el-button type="danger" @click="reject(detail)">驳回</el-button>
        </div>
      </template>
    </el-drawer>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { api } from '@/api'
import { PLATFORMS, contentTypeLabel, platformLabel } from '@/constants/platforms'
import { formatDateTime } from '@/utils/datetime'
import { usePermission } from '@/composables/usePermission'

const { can } = usePermission()
const canReview = computed(() => can('tasks:write') || can('review:write'))

const activeTab = ref('pending')
const loading = ref(false)
const pendingItems = ref([])
const historyItems = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const detailVisible = ref(false)
const detail = ref(null)

const filters = reactive({
  keyword: '',
  platform: '',
  action: '',
  dateRange: [],
})

function buildParams() {
  const params = { page: page.value, page_size: pageSize.value }
  if (filters.keyword) params.keyword = filters.keyword
  if (filters.platform) params.platform = filters.platform
  if (filters.action) params.action = filters.action
  if (filters.dateRange?.length === 2) {
    params.created_from = new Date(filters.dateRange[0]).toISOString()
    params.created_to = new Date(filters.dateRange[1]).toISOString()
  }
  return params
}

async function load() {
  loading.value = true
  try {
    if (activeTab.value === 'pending') {
      const res = await api.listPendingReviews(buildParams())
      pendingItems.value = res.items
      total.value = res.total
    } else {
      const res = await api.listReviewHistory(buildParams())
      historyItems.value = res.items
      total.value = res.total
    }
  } finally {
    loading.value = false
  }
}

function onTabChange() {
  page.value = 1
  load()
}

function reset() {
  filters.keyword = ''
  filters.platform = ''
  filters.action = ''
  filters.dateRange = []
  page.value = 1
  load()
}

async function showDetail(row) {
  detail.value = await api.getTask(row.id)
  detailVisible.value = true
}

async function showHistoryDetail(row) {
  detail.value = await api.getTask(row.task_id)
  detailVisible.value = true
}

async function approve(row) {
  try {
    await api.approveTask(row.id)
    ElMessage.success('已通过审核')
    detailVisible.value = false
    load()
  } catch (e) {
    ElMessage.error(e.message)
  }
}

async function reject(row) {
  try {
    const { value } = await ElMessageBox.prompt('请输入驳回原因', '驳回任务', {
      confirmButtonText: '驳回',
      cancelButtonText: '取消',
      inputPlaceholder: '如：标题不合规',
      inputValidator: (v) => !!(v && v.trim()) || '请填写驳回原因',
    })
    await api.rejectTask(row.id, value.trim())
    ElMessage.success('已驳回')
    detailVisible.value = false
    load()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error(e.message || '驳回失败')
  }
}

onMounted(load)
</script>

<style scoped>
.filter-bar {
  margin-bottom: 16px;
}
.pager {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
}
.block {
  white-space: pre-wrap;
  background: #f5f7fa;
  padding: 8px 12px;
  border-radius: 6px;
  font-size: 13px;
}
.material-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}
.material-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.drawer-actions {
  margin-top: 20px;
  display: flex;
  gap: 12px;
}
</style>
