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
      <p class="muted" style="margin-bottom: 12px">
        登录密码经 bcrypt 加密存入数据库，<strong>修改后无法在系统中查看</strong>。下表「初始密码」仅对应首次部署时自动创建的默认账号，可在
        <code>.env</code> 中通过 <code>ADMIN_PASSWORD</code>、<code>OPERATOR_PASSWORD</code>、<code>VIEWER_PASSWORD</code> 配置（仅新建账号时生效）。
      </p>
      <el-table :data="roles" size="small">
        <el-table-column label="角色" width="160">
          <template #default="{ row }">{{ roleDisplayLabel(row.role_name) }}</template>
        </el-table-column>
        <el-table-column label="登录账号" width="140">
          <template #default="{ row }">
            <span v-if="row.users?.length">{{ row.users.map((u) => u.username).join('、') }}</span>
            <span v-else class="muted">暂无</span>
          </template>
        </el-table-column>
        <el-table-column label="初始密码" width="160">
          <template #default="{ row }">
            <template v-if="row.users?.length">
              <div v-for="u in row.users" :key="u.username" style="line-height: 1.6">
                <span v-if="u.initial_password">{{ u.username }}：{{ u.initial_password }}</span>
                <span v-else class="muted">{{ u.username }}：已加密，不可查看</span>
              </div>
            </template>
            <span v-else class="muted">—</span>
          </template>
        </el-table-column>
        <el-table-column label="权限说明" min-width="280">
          <template #default="{ row }">
            <el-tag v-for="p in row.permissions || []" :key="p" size="small" style="margin: 2px 4px 2px 0">
              {{ permissionLabel(p) }}
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
import { permissionLabel, roleDisplayLabel } from '@/utils/permissions'

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
