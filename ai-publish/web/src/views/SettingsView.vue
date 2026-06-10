<template>
  <div v-loading="loading">
    <h2 class="page-title">系统设置</h2>
    <p class="muted">以下配置保存在数据库，修改后立即生效（优先于部分环境变量）。</p>

    <div class="page-card">
      <el-table :data="configs">
        <el-table-column prop="config_key" label="配置项" width="260" />
        <el-table-column prop="remark" label="说明" min-width="220" show-overflow-tooltip />
        <el-table-column label="值" min-width="200">
          <template #default="{ row }">
            <el-input v-model="row.config_value" />
          </template>
        </el-table-column>
        <el-table-column label="操作" width="100">
          <template #default="{ row }">
            <el-button size="small" type="primary" :loading="savingKey === row.config_key" @click="save(row)">
              保存
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <div class="page-card" style="margin-top: 16px">
      <h3>角色列表</h3>
      <el-table :data="roles" size="small">
        <el-table-column prop="role_name" label="角色" width="120" />
        <el-table-column label="权限">
          <template #default="{ row }">
            <el-tag v-for="p in row.permissions || []" :key="p" size="small" style="margin: 2px 4px 2px 0">
              {{ p }}
            </el-tag>
          </template>
        </el-table-column>
      </el-table>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { api } from '@/api'

const loading = ref(false)
const savingKey = ref('')
const configs = ref([])
const roles = ref([])

async function load() {
  loading.value = true
  try {
    const [cfg, roleList] = await Promise.all([api.listSystemConfigs(), api.listRoles()])
    configs.value = cfg
    roles.value = roleList
  } finally {
    loading.value = false
  }
}

async function save(row) {
  savingKey.value = row.config_key
  try {
    await api.updateSystemConfig(row.config_key, { config_value: row.config_value, remark: row.remark })
    ElMessage.success('已保存')
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    savingKey.value = ''
  }
}

onMounted(load)
</script>
