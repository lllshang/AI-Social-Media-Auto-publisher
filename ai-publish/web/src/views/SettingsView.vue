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
            <el-switch
              v-if="isBoolConfig(row.config_key)"
              :model-value="boolConfigOn(row.config_value)"
              active-text="开启"
              inactive-text="关闭"
              @change="(v) => setBoolConfig(row, v)"
            />
            <el-input-number
              v-else-if="isIntConfig(row.config_key)"
              v-model="intConfigValues[row.config_key]"
              :min="intConfigMin(row.config_key)"
              :max="intConfigMax(row.config_key)"
              controls-position="right"
              style="width: 160px"
              @change="(v) => setIntConfig(row, v)"
            />
            <el-select
              v-else-if="isSelectConfig(row.config_key)"
              v-model="row.config_value"
              style="width: 180px"
            >
              <el-option
                v-for="opt in selectConfigOptions(row.config_key)"
                :key="opt.value"
                :label="opt.label"
                :value="opt.value"
              />
            </el-select>
            <el-input v-else v-model="row.config_value" />
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

    <div v-if="canManageSettings" class="page-card" style="margin-top: 16px">
      <div class="section-head">
        <h3>敏感词管理</h3>
        <div>
          <el-button size="small" @click="showWordImport = true">批量导入</el-button>
          <el-button type="primary" size="small" @click="showWordForm = true">新增敏感词</el-button>
        </div>
      </div>
      <p class="muted" style="margin-bottom: 12px">
        检测范围：标题、正文、主题、封面文案、评论引导、标签。策略由上方「sensitive_word_*」配置项控制。
      </p>
      <el-table :data="sensitiveWords" size="small" v-loading="wordsLoading">
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column prop="word" label="敏感词" min-width="160" />
        <el-table-column prop="remark" label="备注" min-width="160" show-overflow-tooltip />
        <el-table-column label="操作" width="100">
          <template #default="{ row }">
            <el-button size="small" type="danger" @click="removeWord(row)">删除</el-button>
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
          <template #default="{ row }">{{ roleLabel(row.role_name) }}</template>
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
          <template #default="{ row }">{{ roleLabel(row.role_name) }}</template>
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
            <el-option v-for="r in roles" :key="r.id" :label="roleLabel(r.role_name)" :value="r.id" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="userDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="userSaving" @click="saveUser">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="showWordForm" title="新增敏感词" width="420px">
      <el-form label-width="80px">
        <el-form-item label="敏感词">
          <el-input v-model="newWord" placeholder="如：绝对化用语" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="newWordRemark" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showWordForm = false">取消</el-button>
        <el-button type="primary" :loading="wordSaving" @click="submitWord">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="showWordImport" title="批量导入敏感词" width="480px">
      <p class="muted">每行一个词，或用逗号、中文逗号分隔。</p>
      <el-input v-model="importWordsText" type="textarea" :rows="8" placeholder="最佳&#10;第一&#10;根治" />
      <template #footer>
        <el-button @click="showWordImport = false">取消</el-button>
        <el-button type="primary" :loading="wordSaving" @click="submitWordImport">导入</el-button>
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
import { permissionLabel, roleLabel } from '@/utils/permissions'

const { can } = usePermission()
const canManageUsers = computed(() => can('users:write'))
const canManageSettings = computed(() => can('settings:write'))

const loading = ref(false)
const wordsLoading = ref(false)
const wordSaving = ref(false)
const sensitiveWords = ref([])
const showWordForm = ref(false)
const showWordImport = ref(false)
const newWord = ref('')
const newWordRemark = ref('')
const importWordsText = ref('')
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
    syncIntConfigValues()
    roles.value = results[1]
    users.value = canManageUsers.value ? results[2] : []
    if (canManageSettings.value) {
      await loadSensitiveWords()
    }
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

const BOOL_CONFIG_KEYS = new Set([
  'require_content_review',
  'scheduler_enabled',
  'auto_retry_enabled',
  'material_cleanup_enabled',
  'sensitive_word_enabled',
  'rate_limit_enabled',
  'rate_limit_include_retry',
  'image_moderation_enabled',
])
const SELECT_CONFIG_OPTIONS = {
  sensitive_word_action: [
    { label: '拦截 (block)', value: 'block' },
    { label: '仅记录 (warn)', value: 'warn' },
  ],
  image_moderation_provider: [{ label: 'Stub（默认通过）', value: 'stub' }],
}
const INT_CONFIG_KEYS = new Set([
  'max_auto_retries',
  'retry_delay_minutes',
  'material_retention_days',
  'scheduler_poll_interval_seconds',
  'rate_limit_min_interval_seconds',
  'rate_limit_daily_per_account',
  'rate_limit_max_concurrent',
])
const intConfigValues = reactive({})

function isBoolConfig(key) {
  return BOOL_CONFIG_KEYS.has(key)
}

function isIntConfig(key) {
  return INT_CONFIG_KEYS.has(key)
}

function isSelectConfig(key) {
  return Object.prototype.hasOwnProperty.call(SELECT_CONFIG_OPTIONS, key)
}

function selectConfigOptions(key) {
  return SELECT_CONFIG_OPTIONS[key] || []
}

async function loadSensitiveWords() {
  wordsLoading.value = true
  try {
    sensitiveWords.value = await api.listSensitiveWords({ include_disabled: true })
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    wordsLoading.value = false
  }
}

async function submitWord() {
  if (!newWord.value.trim()) return ElMessage.warning('请填写敏感词')
  wordSaving.value = true
  try {
    await api.createSensitiveWord({ word: newWord.value.trim(), remark: newWordRemark.value || null })
    ElMessage.success('已添加')
    showWordForm.value = false
    newWord.value = ''
    newWordRemark.value = ''
    await loadSensitiveWords()
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    wordSaving.value = false
  }
}

async function submitWordImport() {
  const words = importWordsText.value
    .split(/[\n,，]/)
    .map((w) => w.trim())
    .filter(Boolean)
  if (!words.length) return ElMessage.warning('请粘贴至少一个词')
  wordSaving.value = true
  try {
    const res = await api.batchImportSensitiveWords(words)
    ElMessage.success(`已导入 ${res.added} 个新词`)
    showWordImport.value = false
    importWordsText.value = ''
    await loadSensitiveWords()
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    wordSaving.value = false
  }
}

async function removeWord(row) {
  try {
    await ElMessageBox.confirm(`删除敏感词「${row.word}」？`, '确认')
    await api.deleteSensitiveWord(row.id)
    ElMessage.success('已删除')
    await loadSensitiveWords()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error(e.message || '删除失败')
  }
}

function intConfigMin(key) {
  if (key === 'max_auto_retries') return 0
  if (key === 'retry_delay_minutes') return 1
  if (key === 'material_retention_days') return 1
  if (key === 'rate_limit_min_interval_seconds') return 0
  if (key === 'rate_limit_daily_per_account') return 0
  if (key === 'rate_limit_max_concurrent') return 1
  return 5
}

function intConfigMax(key) {
  if (key === 'max_auto_retries') return 10
  if (key === 'retry_delay_minutes') return 120
  if (key === 'material_retention_days') return 3650
  if (key === 'rate_limit_min_interval_seconds') return 86400
  if (key === 'rate_limit_daily_per_account') return 500
  if (key === 'rate_limit_max_concurrent') return 20
  return 3600
}

function boolConfigOn(value) {
  return ['1', 'true', 'yes', 'on'].includes(String(value || '').trim().toLowerCase())
}

function setBoolConfig(row, on) {
  row.config_value = on ? 'true' : 'false'
}

function setIntConfig(row, value) {
  row.config_value = String(value ?? '')
}

function syncIntConfigValues() {
  for (const row of configs.value) {
    if (isIntConfig(row.config_key)) {
      const parsed = parseInt(row.config_value, 10)
      intConfigValues[row.config_key] = Number.isFinite(parsed) ? parsed : intConfigMin(row.config_key)
    }
  }
}

async function save(row) {
  savingKey.value = row.config_key
  try {
    await api.updateSystemConfig(row.config_key, { config_value: row.config_value, remark: row.remark })
    if (row.config_key === 'require_content_review') {
      ElMessage.success(boolConfigOn(row.config_value) ? '内容审核已开启' : '内容审核已关闭')
    } else {
      ElMessage.success('已保存')
    }
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
