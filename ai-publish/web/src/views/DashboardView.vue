<template>
  <div v-loading="loading">
    <h2 class="page-title">工作台</h2>

    <el-alert
      v-for="alert in summary?.alerts || []"
      :key="alert.id"
      :title="alert.message"
      :type="alert.level === 'error' ? 'error' : 'warning'"
      show-icon
      :closable="false"
      style="margin-bottom: 16px"
    >
      <template #default>
        <el-button link type="primary" @click="$router.push(alert.link)">去处理</el-button>
      </template>
    </el-alert>

    <el-row :gutter="16">
      <el-col :span="4" v-for="item in overviewCards" :key="item.label">
        <div class="page-card stat">
          <div class="muted">{{ item.label }}</div>
          <div class="value" :class="item.danger ? 'danger' : ''">{{ item.value }}</div>
        </div>
      </el-col>
    </el-row>

    <div class="page-card" style="margin-top: 16px">
      <div class="section-head">
        <h3>风控观测（近 {{ riskStats.period_days || 7 }} 天）</h3>
        <span class="muted">用于评估是否需启用本机 Worker（D.4）</span>
      </div>
      <el-row :gutter="12">
        <el-col :span="4" v-for="item in riskCards" :key="item.label">
          <div class="risk-stat">
            <div class="muted">{{ item.label }}</div>
            <div class="value" :class="item.danger ? 'danger' : item.warn ? 'warn' : ''">{{ item.value }}</div>
          </div>
        </el-col>
      </el-row>
      <div class="risk-tags">
        <el-tag type="danger">疑似风控失败 {{ riskStats.failed_risk || 0 }}</el-tag>
        <el-tag type="warning">技术问题失败 {{ riskStats.failed_technical || 0 }}</el-tag>
        <el-tag type="info">其他失败 {{ riskStats.failed_other || 0 }}</el-tag>
      </div>
    </div>

    <el-row :gutter="16" class="dashboard-row" style="margin-top: 16px">
      <el-col :span="12" class="dashboard-col">
        <div class="page-card dashboard-panel">
          <div class="section-head">
            <h3>失败任务</h3>
            <el-button link type="primary" @click="$router.push({ path: '/tasks', query: { status: 'failed' } })">
              查看全部
            </el-button>
          </div>
          <div class="panel-body">
            <el-table :data="summary?.failed_tasks || []" empty-text="暂无失败任务">
              <el-table-column prop="id" label="ID" width="60" />
              <el-table-column prop="title" label="标题" show-overflow-tooltip />
              <el-table-column label="平台" width="90">
                <template #default="{ row }">{{ platformLabel(row.platform) }}</template>
              </el-table-column>
              <el-table-column label="归类" width="100">
                <template #default="{ row }">
                  <el-tag size="small" :type="failureTagType(row.failure_category)">
                    {{ failureCategoryLabel(row.failure_category) }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="error_message" label="错误" show-overflow-tooltip />
              <el-table-column label="操作" width="90">
              <template #default="{ row }">
                <el-button v-if="can('tasks:execute')" size="small" type="warning" @click="retryTask(row)">重试</el-button>
              </template>
              </el-table-column>
            </el-table>
          </div>
        </div>
      </el-col>

      <el-col :span="12" class="dashboard-col">
        <div class="page-card dashboard-panel">
          <div class="section-head">
            <h3>账号健康</h3>
            <el-button link type="primary" @click="$router.push('/accounts')">管理账号</el-button>
          </div>
          <div class="health-tags">
            <el-tag type="success">正常 {{ summary?.account_health?.active || 0 }}</el-tag>
            <el-tag type="info">未激活 {{ summary?.account_health?.inactive || 0 }}</el-tag>
            <el-tag type="danger">已过期 {{ summary?.account_health?.expired || 0 }}</el-tag>
          </div>
          <div class="panel-body">
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
        </div>
      </el-col>
    </el-row>

    <el-row :gutter="16" class="dashboard-row" style="margin-top: 16px">
      <el-col :span="12" class="dashboard-col">
        <div class="page-card dashboard-panel">
          <h3 class="panel-title">任务趋势（近 7 天）</h3>
          <div class="panel-body">
            <div class="trend-chart">
              <div v-for="day in dailyTrend" :key="day.date" class="trend-day">
                <div class="trend-bars">
                  <div
                    class="trend-bar success"
                    :style="{ height: barHeight(day.success) }"
                    :title="`成功 ${day.success}`"
                  />
                  <div
                    class="trend-bar failed"
                    :style="{ height: barHeight(day.failed) }"
                    :title="`失败 ${day.failed}`"
                  />
                  <div
                    class="trend-bar pending"
                    :style="{ height: barHeight(day.pending) }"
                    :title="`待处理 ${day.pending}`"
                  />
                </div>
                <span class="trend-label">{{ day.label }}</span>
              </div>
            </div>
            <div class="trend-legend">
              <span><i class="dot success" />成功</span>
              <span><i class="dot failed" />失败</span>
              <span><i class="dot pending" />待处理</span>
            </div>
          </div>
        </div>
      </el-col>

      <el-col :span="12" class="dashboard-col">
        <div class="page-card dashboard-panel">
          <h3 class="panel-title">任务按平台分布</h3>
          <div class="panel-body platform-bars">
            <div v-for="item in platformTrend" :key="item.platform" class="platform-row">
              <span class="platform-name">{{ platformLabel(item.platform) }}</span>
              <div class="platform-track">
                <div class="platform-fill" :style="{ width: platformWidth(item.count) }" />
              </div>
              <span class="platform-count">{{ item.count }}</span>
            </div>
            <p v-if="!platformTrend.length" class="muted">暂无任务数据</p>
          </div>
        </div>
      </el-col>
    </el-row>

    <el-row :gutter="16" class="dashboard-row" style="margin-top: 16px">
      <el-col :span="12" class="dashboard-col">
        <div class="page-card dashboard-panel">
          <h3 class="panel-title">AI 调用统计（近 7 天）</h3>
          <div class="panel-body">
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
        </div>
      </el-col>

      <el-col :span="12" class="dashboard-col">
        <div class="page-card dashboard-panel">
          <h3 class="panel-title">当前 AI 模型</h3>
          <div class="panel-body">
            <p>文案：{{ models.text || '-' }}</p>
            <p>文生图：{{ models.image || '-' }}</p>
            <p class="muted">文生图 Key 未配置时将使用占位图，发布请上传真实图片。</p>
          </div>
          <div v-if="can('publish:write')" class="panel-actions">
            <el-button type="primary" @click="$router.push('/publish')">发布图文</el-button>
            <el-button @click="$router.push({ path: '/publish', query: { platform: 'xhs', content_type: 'video' } })">
              发布小红书视频
            </el-button>
          </div>
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
import { usePermission } from '@/composables/usePermission'

const { can } = usePermission()

const loading = ref(false)
const summary = ref(null)
const models = reactive({ text: '', image: '' })

const riskStats = computed(() => summary.value?.risk_stats || {})

const riskCards = computed(() => {
  const r = riskStats.value
  return [
    { label: '敏感词拦截', value: r.sensitive_word_blocks ?? 0 },
    { label: '限频拦截', value: r.rate_limit_blocks ?? 0, warn: (r.rate_limit_blocks || 0) >= 5 },
    { label: '发布成功', value: r.success_count ?? 0 },
    { label: '发布失败', value: r.failed_count ?? 0, danger: (r.failed_count || 0) > 0 },
    {
      label: '失败率',
      value: `${r.failure_rate_percent ?? 0}%`,
      danger: (r.failure_rate_percent || 0) >= 15,
    },
    { label: '疑似风控', value: r.failed_risk ?? 0, danger: (r.failed_risk || 0) >= 3 },
  ]
})

function failureCategoryLabel(category) {
  return (
    {
      risk: '疑似风控',
      technical: '技术',
      other: '其他',
    }[category] || category || '其他'
  )
}

function failureTagType(category) {
  if (category === 'risk') return 'danger'
  if (category === 'technical') return 'warning'
  return 'info'
}

const dailyTrend = computed(() => {
  const rows = summary.value?.task_trends?.daily_7d || []
  return rows.map((row) => ({
    ...row,
    label: row.date.slice(5),
  }))
})

const platformTrend = computed(() => summary.value?.task_trends?.by_platform || [])

const trendMax = computed(() => {
  let max = 1
  for (const day of dailyTrend.value) {
    max = Math.max(max, day.success, day.failed, day.pending, day.other || 0)
  }
  return max
})

const platformMax = computed(() => {
  const counts = platformTrend.value.map((item) => item.count)
  return Math.max(1, ...counts, 0)
})

function barHeight(value) {
  const pct = Math.round((Number(value || 0) / trendMax.value) * 100)
  return `${Math.max(pct, value ? 8 : 0)}%`
}

function platformWidth(count) {
  const pct = Math.round((Number(count || 0) / platformMax.value) * 100)
  return `${Math.max(pct, count ? 6 : 0)}%`
}

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
.risk-stat {
  padding: 8px 4px;
}
.risk-stat .value {
  font-size: 22px;
  font-weight: 700;
  margin-top: 6px;
}
.risk-stat .value.danger {
  color: #f56c6c;
}
.risk-stat .value.warn {
  color: #e6a23c;
}
.risk-tags {
  margin-top: 12px;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
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
.dashboard-row {
  align-items: stretch;
}
.dashboard-col {
  display: flex;
}
.dashboard-panel {
  flex: 1;
  width: 100%;
  display: flex;
  flex-direction: column;
  min-height: 280px;
}
.panel-title {
  margin: 0 0 12px;
}
.panel-body {
  flex: 1;
  display: flex;
  flex-direction: column;
}
.panel-body :deep(.el-table) {
  flex: 1;
}
.panel-body :deep(.el-table__empty-block) {
  min-height: 120px;
}
.panel-actions {
  margin-top: auto;
  padding-top: 16px;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.trend-chart {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 8px;
  min-height: 140px;
  padding-top: 8px;
}
.trend-day {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
}
.trend-bars {
  display: flex;
  align-items: flex-end;
  gap: 3px;
  height: 110px;
  width: 100%;
  justify-content: center;
}
.trend-bar {
  width: 10px;
  border-radius: 4px 4px 0 0;
  min-height: 0;
}
.trend-bar.success {
  background: #67c23a;
}
.trend-bar.failed {
  background: #f56c6c;
}
.trend-bar.pending {
  background: #e6a23c;
}
.trend-label {
  font-size: 12px;
  color: #888;
}
.trend-legend {
  margin-top: 12px;
  display: flex;
  gap: 16px;
  font-size: 13px;
  color: #666;
}
.trend-legend .dot {
  display: inline-block;
  width: 10px;
  height: 10px;
  border-radius: 2px;
  margin-right: 4px;
}
.trend-legend .dot.success {
  background: #67c23a;
}
.trend-legend .dot.failed {
  background: #f56c6c;
}
.trend-legend .dot.pending {
  background: #e6a23c;
}
.platform-bars {
  gap: 10px;
}
.platform-row {
  display: grid;
  grid-template-columns: 72px 1fr 36px;
  align-items: center;
  gap: 8px;
}
.platform-name,
.platform-count {
  font-size: 13px;
}
.platform-track {
  height: 10px;
  background: #eef2f6;
  border-radius: 5px;
  overflow: hidden;
}
.platform-fill {
  height: 100%;
  background: linear-gradient(90deg, #409eff, #66b1ff);
  border-radius: 5px;
}
.muted {
  color: #888;
  font-size: 13px;
}
</style>
