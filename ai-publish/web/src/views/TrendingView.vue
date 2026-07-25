<template>
  <div v-loading="loading">
    <div class="toolbar">
      <h2 class="page-title">热点灵感</h2>
      <div v-if="canWrite">
        <el-button :loading="fetching" @click="runFetch">立即抓取</el-button>
        <el-button type="primary" :loading="aiLoading" @click="runAiRecommend">AI 推荐今日选题</el-button>
      </div>
    </div>

    <el-alert
      v-if="!features.trending_enabled"
      type="info"
      :closable="false"
      show-icon
      title="热点灵感未启用"
      description="请在系统设置中开启「trending_enabled」后使用本页功能。"
      style="margin-bottom: 16px"
    />

    <div class="page-card meta-row">
      <span class="muted">
        上次抓取：{{ status.last_fetch_at || '—' }}
        <template v-if="status.last_fetch_source">（{{ status.last_fetch_source }} / {{ status.last_fetch_status }}）</template>
      </span>
      <span v-if="status.stale" class="stale-tag">数据可能已过期</span>
    </div>

    <div class="page-card filters">
      <el-radio-group v-model="period" @change="loadItems">
        <el-radio-button value="daily">今日</el-radio-button>
        <el-radio-button value="rolling_7d">近 7 天</el-radio-button>
        <el-radio-button value="rolling_30d">近 30 天</el-radio-button>
      </el-radio-group>
      <el-select v-model="platform" clearable placeholder="全部平台" style="width: 140px; margin-left: 12px" @change="loadItems">
        <el-option label="抖音" value="douyin" />
        <el-option label="B站" value="bilibili" />
      </el-select>
      <el-checkbox v-model="miniGameOnly" style="margin-left: 12px" @change="loadItems">仅小游戏</el-checkbox>
      <span v-if="miniGameOnly" class="muted filter-hint">按标题/标签匹配游戏关键词，可在系统设置扩展</span>
    </div>

    <div v-if="recommendations.length" class="page-card">
      <h3>AI 推荐选题</h3>
      <div v-for="(rec, idx) in recommendations" :key="idx" class="rec-row">
        <div>
          <strong>{{ rec.topic }}</strong>
          <span class="muted"> — {{ platformLabel(rec.platform) }} · {{ rec.reason }}</span>
        </div>
        <el-button size="small" type="primary" @click="goCreate(rec)">用这个创作</el-button>
      </div>
    </div>

    <div class="page-card">
      <el-table :data="items" size="small" :empty-text="miniGameOnly ? '暂无匹配的小游戏热点，可取消勾选查看全部或扩展关键词后重新抓取' : '暂无热点，请先抓取'">
        <el-table-column prop="rank" label="#" width="50" />
        <el-table-column prop="title" label="话题/标题" min-width="220" show-overflow-tooltip />
        <el-table-column label="平台" width="90">
          <template #default="{ row }">{{ platformLabel(row.platform) }}</template>
        </el-table-column>
        <el-table-column prop="heat_score" label="热度" width="100" />
        <el-table-column prop="appear_days" label="持续天数" width="90" />
        <el-table-column label="标签" min-width="120">
          <template #default="{ row }">
            <el-tag v-for="tag in (row.tags || []).slice(0, 2)" :key="tag" size="small" style="margin-right: 4px">{{ tag }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column v-if="canWrite" label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button size="small" type="primary" @click="goCreate(row)">创作</el-button>
            <el-button size="small" @click="saveTemplate(row)">存模板</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { api } from '@/api'
import { usePermission } from '@/composables/usePermission'

const router = useRouter()
const { can } = usePermission()
const canWrite = computed(() => can('trending:write') || can('settings:write'))

const loading = ref(false)
const fetching = ref(false)
const aiLoading = ref(false)
const period = ref('daily')
const platform = ref('')
const miniGameOnly = ref(false)
const items = ref([])
const status = ref({})
const features = ref({ trending_enabled: false })
const recommendations = ref([])

function platformLabel(value) {
  return { douyin: '抖音', bilibili: 'B站' }[value] || value
}

async function loadFeatures() {
  try {
    features.value = await api.getSystemFeatures()
  } catch {
    features.value = { trending_enabled: false }
  }
}

async function loadStatus() {
  try {
    status.value = await api.getTrendingStatus()
  } catch {
    status.value = {}
  }
}

async function loadItems() {
  if (!features.value.trending_enabled) {
    items.value = []
    return
  }
  loading.value = true
  try {
    items.value = await api.listTrendingItems({
      period: period.value,
      platform: platform.value || undefined,
      category: miniGameOnly.value ? 'mini_game' : undefined,
    })
  } catch (e) {
    ElMessage.error(e.message || '加载失败')
  } finally {
    loading.value = false
  }
}

async function runFetch() {
  fetching.value = true
  try {
    const res = await api.fetchTrending()
    const detail = res.error_message ? `：${res.error_message}` : ''
    if (res.status === 'failed' || !res.item_count) {
      ElMessage.error(`抓取失败：${res.item_count || 0} 条${detail || '（请检查服务器外网或热榜源配置）'}`)
    } else if (res.status === 'partial') {
      ElMessage.warning(`抓取部分成功：${res.item_count} 条${detail}`)
    } else {
      ElMessage.success(`抓取完成：${res.item_count} 条（${res.source || res.status}）`)
    }
    await Promise.all([loadStatus(), loadItems()])
  } catch (e) {
    ElMessage.error(e.message || '抓取失败')
  } finally {
    fetching.value = false
  }
}

async function runAiRecommend() {
  aiLoading.value = true
  try {
    const res = await api.aiRecommendTrending({
      period: period.value,
      platform: platform.value || undefined,
      category: miniGameOnly.value ? 'mini_game' : undefined,
    })
    recommendations.value = res.recommendations || []
    if (!recommendations.value.length) {
      ElMessage.info(res.message || '暂无推荐')
    }
  } catch (e) {
    ElMessage.error(e.message || 'AI 推荐失败')
  } finally {
    aiLoading.value = false
  }
}

function goCreate(row) {
  const topic = row.topic || row.title
  const p = row.platform || 'douyin'
  router.push({
    path: '/publish',
    query: { topic, platform: p, content_type: 'video' },
  })
}

async function saveTemplate(row) {
  try {
    await api.saveTrendingTemplate(row.id)
    ElMessage.success('已存为内容模板')
  } catch (e) {
    ElMessage.error(e.message || '保存失败')
  }
}

onMounted(async () => {
  await loadFeatures()
  await loadStatus()
  await loadItems()
})
</script>

<style scoped>
.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}
.filters {
  margin-bottom: 16px;
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}
.meta-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}
.stale-tag {
  color: #e6a23c;
  font-size: 13px;
}
.rec-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 8px 0;
  border-bottom: 1px solid #f0f0f0;
}
.filter-hint {
  font-size: 12px;
}
.muted {
  color: #888;
  font-size: 13px;
}
</style>
