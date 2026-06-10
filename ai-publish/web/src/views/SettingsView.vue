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

    <div v-if="canManageUsers" class="page-card" style="margin-top: 16px">
      <div class="section-head">
        <h3>用户管理</h3>
        <el-button type="primary" size="small" @click="openCreateUser">新建用户</el-button>
      </div>
      <el-table :data="users" size="small">
        <el-table-column prop="username" label="用户名" width="140" />
        <el-table-column label="角色" width="160">
          <template #default="{ row }">{{ roleDisplayLabel(row.role_name) }}</template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.status === 'active' ? 'success' : 'info'">{{ row.status === 'active' ? '启用' : '禁用' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" min-width="220">
          <template #default="{ row }">
            <el-button size="small" @click="openEditUser(row)">编辑</el-button>
            <el-button size="small" @click="openResetPassword(row)">重置密码</el-button>
            <el-button
              size="small"
              :type="row.status === 'active' ? 'warning' : 'success'"
              @click="toggleUserStatus(row)"
            >
              {{ row.status === 'active' ? '禁用' : '启用' }}
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <div class="page-card" style="margin-top: 16px">
      <h3>角色列表</h3>
      <p class="muted" style="margin-bottom: 12px">各角色拥有的权限说明；账号与密码请在上方「用户管理」中维护。</p>
      <el-table :data="roles" size="small">
        <el-table-column label="角色" width="200">
          <template #default="{ row }">{{ roleDisplayLabel(row.role_name) }}</template>
        </el-table-column>
        <el-table-column label="权限说明" min-width="360">
          <template #default="{ row }">
            <el-tag v-for="p in row.permissions || []" :key="p" size="small" style="margin: 2px 4px 2px 0">
              {{ permissionLabel(p) }}
            </el-tag>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <el-dialog v-model="userDialogVisible" :title="userDialogTitle" width="440px">
      <el-form label-width="90px">
        <el-form-item v-if="userFormMode === 'create'" label="用户名">
          <el-input v-model="userForm.username" placeholder="登录用户名" />
        </el-form-item>
        <el-form-item v-if="userFormMode === 'create'" label="初始密码">
          <el-input v-model="userForm.password" type="password" show-password placeholder="至少 6 位" />
        </el-form-item>
        <el-form-item label="角色">
          <el-select v-model="userForm.role_id" placeholder="选择角色" style="width: 100%">
            <el-option v-for="r in roles" :key="r.id" :label="roleDisplayLabel(r.role_name)" :value="r.id" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="userDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="userSaving" @click="saveUser">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="resetDialogVisible" title="重置密码" width="400px">
      <el-form label-width="90px">
        <el-form-item label="用户">
          <span>{{ resetTarget?.username }}</span>
        </el-form-item>
        <el-form-item label="新密码">
          <el-input v-model="resetPassword" type="password" show-password placeholder="至少 6 位" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="resetDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="userSaving" @click="submitResetPassword">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { api } from '@/api'
import { usePermission } from '@/composables/usePermission'
import { permissionLabel, roleDisplayLabel } from '@/utils/permissions'

const { can } = usePermission()
const canManageUsers = computed(() => can('users:write'))

const loading = ref(false)
const savingKey = ref('')
const configs = ref([])
const roles = ref([])
const users = ref([])
const userDialogVisible = ref(false)
const userDialogTitle = ref('新建用户')
const userFormMode = ref('create')
const userSaving = ref(false)
const editingUserId = ref(null)
const resetDialogVisible = ref(false)
const resetTarget = ref(null)
const resetPassword = ref('')
const userForm = reactive({
  username: '',
  password: '',
  role_id: null,
})

async function load() {
  loading.value = true
  try {
    const tasks = [api.listSystemConfigs(), api.listRoles()]
    if (canManageUsers.value) tasks.push(api.listUsers())
    const results = await Promise.all(tasks)
    configs.value = results[0]
    roles.value = results[1]
    users.value = canManageUsers.value ? results[2] : []
  } finally {
    loading.value = false
  }
}

function openCreateUser() {
  userFormMode.value = 'create'
  userDialogTitle.value = '新建用户'
  editingUserId.value = null
  userForm.username = ''
  userForm.password = ''
  userForm.role_id = roles.value[0]?.id ?? null
  userDialogVisible.value = true
}

function openEditUser(row) {
  userFormMode.value = 'edit'
  userDialogTitle.value = `编辑用户：${row.username}`
  editingUserId.value = row.id
  userForm.role_id = row.role_id
  userDialogVisible.value = true
}

async function saveUser() {
  userSaving.value = true
  try {
    if (userFormMode.value === 'create') {
      await api.createUser({
        username: userForm.username,
        password: userForm.password,
        role_id: userForm.role_id,
      })
      ElMessage.success('用户已创建')
    } else {
      await api.updateUser(editingUserId.value, { role_id: userForm.role_id })
      ElMessage.success('用户已更新')
    }
    userDialogVisible.value = false
    await load()
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    userSaving.value = false
  }
}

function openResetPassword(row) {
  resetTarget.value = row
  resetPassword.value = ''
  resetDialogVisible.value = true
}

async function submitResetPassword() {
  if (!resetPassword.value || resetPassword.value.length < 6) {
    return ElMessage.warning('密码至少 6 位')
  }
  userSaving.value = true
  try {
    await api.resetUserPassword(resetTarget.value.id, resetPassword.value)
    ElMessage.success('密码已重置')
    resetDialogVisible.value = false
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    userSaving.value = false
  }
}

async function toggleUserStatus(row) {
  const next = row.status === 'active' ? 'disabled' : 'active'
  const action = next === 'disabled' ? '禁用' : '启用'
  try {
    await ElMessageBox.confirm(`确定${action}用户 ${row.username}？`, '确认')
    await api.updateUser(row.id, { status: next })
    ElMessage.success(`已${action}`)
    await load()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error(e.message || '操作失败')
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

<style scoped>
.section-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}
.section-head h3 {
  margin: 0;
}
</style>
