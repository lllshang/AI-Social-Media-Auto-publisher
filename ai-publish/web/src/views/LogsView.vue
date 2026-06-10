<template>
  <div>
    <h2 class="page-title">日志中心</h2>

    <el-tabs v-model="activeTab">
      <el-tab-pane label="AI 生成记录" name="ai">
        <p class="muted usage-hint">文案记录的用量为 Token 数；文生图记录为生成张数（部分供应商为 credits）。</p>
        <div class="page-card filter-bar">
          <el-form inline>
            <el-form-item label="类型">
              <el-select v-model="aiFilters.type" clearable placeholder="全部" style="width: 120px">
                <el-option label="文案" value="text" />
                <el-option label="文生图" value="image" />
              </el-select>
            </el-form-item>
            <el-form-item label="供应商">
              <el-input v-model="aiFilters.provider" clearable placeholder="如 tongyi" style="width: 140px" />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="loadAi">查询</el-button>
            </el-form-item>
          </el-form>
        </div>
        <div class="page-card">
          <el-table :data="aiRecords" v-loading="aiLoading">
            <el-table-column prop="id" label="ID" width="70" />
            <el-table-column prop="type" label="类型" width="80" />
            <el-table-column prop="provider" label="供应商" width="110" />
            <el-table-column prop="prompt" label="Prompt" show-overflow-tooltip />
            <el-table-column prop="result_summary" label="结果摘要" show-overflow-tooltip />
            <el-table-column label="用量" width="120">
              <template #default="{ row }">{{ formatAiUsage(row.type, row.cost) }}</template>
            </el-table-column>
            <el-table-column label="时间" width="170">
              <template #default="{ row }">{{ formatDateTime(row.created_at) }}</template>
            </el-table-column>
          </el-table>
        </div>
      </el-tab-pane>

      <el-tab-pane label="操作日志" name="ops">
        <div class="page-card filter-bar">
          <el-form inline>
            <el-form-item label="动作">
              <el-input v-model="opFilters.action" clearable placeholder="如 account_group.create" style="width: 200px" />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="loadOps">查询</el-button>
            </el-form-item>
          </el-form>
        </div>
        <div class="page-card">
          <el-table :data="opLogs" v-loading="opLoading">
            <el-table-column prop="id" label="ID" width="70" />
            <el-table-column prop="action" label="动作" width="180" />
            <el-table-column prop="target_type" label="对象类型" width="120" />
            <el-table-column prop="target_id" label="对象ID" width="90" />
            <el-table-column prop="user_id" label="用户ID" width="90" />
            <el-table-column label="时间" width="170">
              <template #default="{ row }">{{ formatDateTime(row.created_at) }}</template>
            </el-table-column>
          </el-table>
        </div>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { api } from '@/api'
import { formatAiUsage } from '@/utils/aiUsage'
import { formatDateTime } from '@/utils/datetime'

const activeTab = ref('ai')
const aiLoading = ref(false)
const opLoading = ref(false)
const aiRecords = ref([])
const opLogs = ref([])
const aiFilters = reactive({ type: '', provider: '' })
const opFilters = reactive({ action: '' })

async function loadAi() {
  aiLoading.value = true
  try {
    const params = {}
    if (aiFilters.type) params.type = aiFilters.type
    if (aiFilters.provider) params.provider = aiFilters.provider
    aiRecords.value = await api.listAiGenerations(params)
  } finally {
    aiLoading.value = false
  }
}

async function loadOps() {
  opLoading.value = true
  try {
    const params = {}
    if (opFilters.action) params.action = opFilters.action
    opLogs.value = await api.listOperationLogs(params)
  } finally {
    opLoading.value = false
  }
}

onMounted(() => {
  loadAi()
  loadOps()
})
</script>

<style scoped>
.usage-hint {
  margin: 0 0 12px;
  font-size: 13px;
}
.filter-bar {
  margin-bottom: 16px;
}
</style>
