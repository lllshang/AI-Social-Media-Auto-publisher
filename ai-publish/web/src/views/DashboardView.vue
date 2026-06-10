<template>
  <div v-loading="loading">
    <h2 class="page-title">工作台</h2>

    <el-row :gutter="16">
      <el-col :span="4" v-for="item in overviewCards" :key="item.label">
        <div class="page-card stat">
          <div class="muted">{{ item.label }}</div>
          <div class="value" :class="item.danger ? 'danger' : ''">{{ item.value }}</div>
        </div>
      </el-col>
    </el-row>

    <el-row :gutter="16" style="margin-top: 16px">
      <el-col :span="12">
        <div class="page-card">
          <div class="section-head">
            <h3>失败任务</h3>
            <el-button link type="primary" @click="$router.push({ path: '/tasks', query: { status: 'failed' } })">
              查看全部
            </el-button>
          </div>
          <el-table :data="summary?.failed_tasks || []" empty-text="暂无失败任务">
            <el-table-column prop="id" label="ID" width="60" />
            <el-table-column prop="title" label="标题" show-overflow-tooltip />
            <el-table-column label="平台" width="90">
              <template #default="{ row }">{{ platformLabel(row.platform) }}</template>
            </el-table-column>
            <el-table-column prop="error_message" label="错误" show-overflow-tooltip />
            <el-table-column label="操作" width="90">
              <template #default="{ row }">
                <el-button size="small" type="warning" @click="retryTask(row)">重试</el-button>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </el-col>

      <el-col :span="12">
        <div class="page-card">
          <div class="section-head">
            <h3>账号健康</h3>
            <el-button link type="primary" @click="$router.push('/accounts')">管理账号</el-button>
          </div>
          <div class="health-tags">
            <el-tag type="success">正常 {{ summary?.account_health?.active || 0 }}</el-tag>
            <el-tag type="info">未激活 {{ summary?.account_health?.inactive || 0 }}</el-tag>
            <el-tag type="danger">已过期 {{ summary?.account_health?.expired || 0 }}</el-tag>
          </div>
          <el-table :data="summary?.account_health?.unhealthy_accounts || []" empty-text="账号状态良好">
            <el-table-column prop="account_name" label="账号" />
            <el-table-column label="平台" width="90">
              <template #default="{ row }">{{ platformLabel(row.platform) }}</template>
            </el-table-column>
            <el-table-column label="状态" width="100">
              <template #default="{ row }">
                <el-tag :type="row.status === 'expired' ? 'danger' : 'info'">{{ row.status }}</el-tag>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </el-col>
    </el-row>

    <el-row :gutter="16" style="margin-top: 16px">
      <el-col :span="12">
        <div class="page-card">
          <h3>AI 调用统计（近 7 天）</h3>
          <el-descriptions :column="2" border>
            <el-descriptions-item label="累计调用">{{ summary?.ai_stats?.total_calls || 0 }}</el-descriptions-item>
            <el-descriptions-item label="累计文案 Token">
              {{ formatAiUsage('text', summary?.ai_stats?.text_tokens_total) }}
            </el-descriptions-item>
            <el-descriptions-item label="累计文生图">
              {{ formatAiUsage('image', summary?.ai_stats?.image_units_total) }}
            </el-descriptions-item>
            <el-descriptions-item label="文案生成">
              {{ aiTypeStat('text') }}
            </el-descriptions-item>
            <el-descriptions-item label="文生图">
              {{ aiTypeStat('image') }}
            </el-descriptions-item>
          </el-descriptions>
          <div v-if="summary?.ai_stats?.by_provider?.length" class="provider-list">
            <span class="muted">按供应商：</span>
            <el-tag
              v-for="item in summary.ai_stats.by_provider"
              :key="item.provider"
              style="margin: 4px 6px 0 0"
            >
              {{ item.provider }} ({{ item.count }})
            </el-tag>
          </div>
        </div>
      </el-col>

      <el-col :span="12">
        <div class="page-card">
          <h3>当前 AI 模型</h3>
          <p>文案：{{ models.text || '-' }}</p>
          <p>文生图：{{ models.image || '-' }}</p>
          <p class="muted">文生图 Key 未配置时将使用占位图，发布请上传真实图片。</p>
          <el-button type="primary" @click="$router.push('/publish')">发布图文</el-button>
          <el-button @click="$router.push({ path: '/publish', query: { platform: 'xhs', content_type: 'video' } })">
            发布小红书视频
          </el-button>
        </div>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { api } from '@/api'
import { platformLabel } from '@/constants/platforms'
import { formatAiUsage } from '@/utils/aiUsage'

const loading = ref(false)
const summary = ref(null)
const models = reactive({ text: '', image: '' })

const overviewCards = computed(() => {
  const o = summary.value?.overview || {}
  return [
    { label: '平台账号', value: o.accounts ?? '-' },
    { label: '素材数量', value: o.materials ?? '-' },
    { label: '发布任务', value: o.tasks ?? '-' },
    { label: '成功任务', value: o.success_tasks ?? '-' },
    { label: '待发布', value: o.pending_tasks ?? '-' },
    { label: '失败任务', value: o.failed_tasks ?? '-', danger: true },
  ]
})

function aiTypeStat(type) {
  const stat = summary.value?.ai_stats?.last_7_days?.[type]
  if (!stat) return '0 次'
  return `${stat.count} 次 / ${formatAiUsage(type, stat.cost)}`
}

async function retryTask(row) {
  try {
    await api.retryTask(row.id)
    ElMessage.success('已重置为待发布')
    await load()
  } catch (e) {
    ElMessage.error(e.message)
  }
}

async function load() {
  loading.value = true
  try {
    const [dashboard, modelData] = await Promise.all([api.getDashboardSummary(), api.getModels()])
    summary.value = dashboard
    models.text = `${modelData.text.current.provider} / ${modelData.text.current.model}`
    models.image = `${modelData.image.current.provider} / ${modelData.image.current.model}`
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.stat .value {
  font-size: 28px;
  font-weight: 700;
  margin-top: 8px;
}
.stat .value.danger {
  color: #f56c6c;
}
.section-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}
.section-head h3 {
  margin: 0;
}
.health-tags {
  margin-bottom: 12px;
  display: flex;
  gap: 8px;
}
.provider-list {
  margin-top: 12px;
}
</style>
