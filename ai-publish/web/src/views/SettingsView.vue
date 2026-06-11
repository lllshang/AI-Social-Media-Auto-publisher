<template>
  <div v-loading="loading">
    <h2 class="page-title">系统设置</h2>
    <p class="muted">以下配置保存在数据库，修改后立即生效（优先于部分环境变量）。</p>

    <div class="page-card">
      <el-table :data="visibleConfigs">
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
        <h3>图片内容审核</h3>
      </div>
      <el-alert
        type="warning"
        :closable="false"
        show-icon
        title="开启图片审核后，每次上传或文生图入库可能调用云 API 并按张计费（试用额度用尽后产生费用）。Stub 不产生费用。"
        style="margin-bottom: 12px"
      />
      <el-form label-width="160px" class="image-mod-form">
        <el-form-item label="腾讯云 SecretId">
          <el-input v-model="imageModForm.tencent_secret_id" placeholder="选用腾讯云时填写" show-password />
        </el-form-item>
        <el-form-item label="腾讯云 SecretKey">
          <el-input v-model="imageModForm.tencent_secret_key" placeholder="选用腾讯云时填写" show-password />
        </el-form-item>
        <el-form-item label="腾讯云地域">
          <el-input v-model="imageModForm.tencent_region" placeholder="ap-guangzhou" />
        </el-form-item>
        <el-form-item label="阿里云 AccessKeyId">
          <el-input v-model="imageModForm.alibaba_access_key_id" placeholder="选用阿里云时填写" show-password />
        </el-form-item>
        <el-form-item label="阿里云 AccessKeySecret">
          <el-input v-model="imageModForm.alibaba_access_key_secret" placeholder="选用阿里云时填写" show-password />
        </el-form-item>
        <el-form-item label="阿里云地域">
          <el-input v-model="imageModForm.alibaba_region" placeholder="cn-shanghai" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="imageModSaving" @click="saveImageModSecrets">保存密钥配置</el-button>
        </el-form-item>
      </el-form>
    </div>

    <div v-if="canManageSettings" class="page-card" style="margin-top: 16px">
      <div class="section-head">
        <h3>本机发布 Worker</h3>
        <el-button type="primary" size="small" @click="openCreateWorker">新建 Worker</el-button>
      </div>
      <el-alert
        type="info"
        :closable="false"
        show-icon
        title="用于在本机电脑执行浏览器发布（方案 1 + D.4）"
        description="创建后复制 Token，在本机运行 worker/local_publish_worker.py；将账号绑定到对应 Worker 后，发布任务会派发到该机器。本机需安装 Chrome 并保持常开。"
        style="margin-bottom: 12px"
      />
      <el-table :data="publishWorkers" size="small" v-loading="workersLoading">
        <el-table-column prop="name" label="名称" width="140" />
        <el-table-column prop="worker_key" label="标识" width="160" />
        <el-table-column prop="hostname" label="主机名" min-width="120" />
        <el-table-column label="在线" width="90">
          <template #default="{ row }">
            <el-tag :type="row.online ? 'success' : 'info'">{{ row.online ? '在线' : '离线' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="220">
          <template #default="{ row }">
            <el-button size="small" @click="rotateWorkerToken(row)">重置 Token</el-button>
            <el-button size="small" type="danger" @click="removeWorker(row)">删除</el-button>
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

    <el-dialog v-model="showWorkerToken" title="本机 Worker 配置（Token 仅显示一次）" width="580px">
      <el-alert
        type="info"
        :closable="false"
        show-icon
        title="「服务器地址」不是本机域名"
        description="请填你当前打开管理后台用的地址（浏览器地址栏里的内容，去掉 /app 路径）。Worker 程序跑在你本机，但要连到这台服务器领取发布任务。"
        style="margin-bottom: 12px"
      />
      <el-form label-width="108px">
        <el-form-item label="服务器地址">
          <el-input v-model="workerApiBase" placeholder="http://127.0.0.1:8765" />
        </el-form-item>
        <el-form-item label="Worker Token">
          <el-input v-model="workerTokenValue" readonly type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item label="终端启动命令">
          <el-input
            ref="workerCommandInputRef"
            :model-value="workerStartCommand"
            readonly
            type="textarea"
            :rows="6"
            @focus="selectWorkerCommand"
            @click="selectWorkerCommand"
          />
          <p class="muted field-hint">HTTP 非 localhost 时浏览器可能禁止自动复制，可点击上方文本框后按 ⌘C 手动复制。</p>
        </el-form-item>
      </el-form>
      <p class="muted" style="margin: 0">
        Mac 也可在 Finder 中双击 <code>ai-publish/worker/一键启动.command</code>（首次会引导填写上述信息）。
      </p>
      <template #footer>
        <el-button @click="copyWorkerToken">复制 Token</el-button>
        <el-button @click="copyWorkerCommand">复制启动命令</el-button>
        <el-button type="warning" @click="confirmLocalWorkerStart">在本机启动</el-button>
        <el-button type="primary" @click="showWorkerToken = false">我已保存</el-button>
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
const imageModSaving = ref(false)
const workersLoading = ref(false)
const publishWorkers = ref([])
const showWorkerToken = ref(false)
const workerTokenValue = ref('')
const workerApiBase = ref('')
const workerCommandInputRef = ref(null)

const workerStartCommand = computed(() => {
  const base = (workerApiBase.value || detectWorkerApiBase()).replace(/\/$/, '')
  const token = workerTokenValue.value || '<Token>'
  const root = 'cd "$HOME/Desktop/混合开发/AI-Social-Media-Auto-publisher/ai-publish/worker"'
  return [
    '# 若路径不对，在 Finder 里把 ai-publish/worker 文件夹拖进终端可得到正确 cd 路径',
    `${root}`,
    `cat > worker.env << 'EOF'`,
    `AI_PUBLISH_API_BASE=${base}`,
    `AI_PUBLISH_WORKER_TOKEN=${token}`,
    'EOF',
    './run-worker.sh',
  ].join('\n')
})

function detectWorkerApiBase() {
  if (typeof window === 'undefined') return 'http://127.0.0.1:8765'
  return window.location.origin
}

function openWorkerTokenDialog(token) {
  workerTokenValue.value = token
  workerApiBase.value = detectWorkerApiBase()
  showWorkerToken.value = true
}

function fallbackCopyText(text) {
  const textarea = document.createElement('textarea')
  textarea.value = text
  textarea.setAttribute('readonly', '')
  textarea.style.position = 'fixed'
  textarea.style.top = '0'
  textarea.style.left = '0'
  textarea.style.opacity = '0'
  document.body.appendChild(textarea)
  textarea.focus()
  textarea.select()
  textarea.setSelectionRange(0, text.length)
  let ok = false
  try {
    ok = document.execCommand('copy')
  } catch {
    ok = false
  }
  document.body.removeChild(textarea)
  return ok
}

async function copyText(text, okMessage) {
  if (window.isSecureContext && navigator.clipboard?.writeText) {
    try {
      await navigator.clipboard.writeText(text)
      ElMessage.success(okMessage)
      return true
    } catch {
      /* 降级到 execCommand */
    }
  }
  if (fallbackCopyText(text)) {
    ElMessage.success(okMessage)
    return true
  }
  selectWorkerCommand()
  ElMessage.warning('自动复制不可用，已选中命令文本，请按 ⌘C 复制')
  return false
}

function selectWorkerCommand() {
  const component = workerCommandInputRef.value
  const textarea = component?.textarea ?? component?.$el?.querySelector('textarea')
  if (!textarea) return
  textarea.focus()
  textarea.select()
}

function copyWorkerToken() {
  if (!workerTokenValue.value) return ElMessage.warning('暂无 Token')
  copyText(workerTokenValue.value, 'Token 已复制')
}

function copyWorkerCommand() {
  copyText(workerStartCommand.value, '启动命令已复制，请打开 Mac「终端」粘贴执行')
}

async function confirmLocalWorkerStart() {
  if (!workerTokenValue.value) return ElMessage.warning('暂无 Token')
  const base = (workerApiBase.value || detectWorkerApiBase()).replace(/\/$/, '')
  try {
    await ElMessageBox.confirm(
      `将复制一段脚本到剪贴板。请打开 Mac「终端」，粘贴后回车即可在本机启动 Worker。\n\n服务器地址：${base}\n\n说明：网页出于安全限制，不能直接替你打开终端运行程序。`,
      '在本机启动 Worker',
      {
        confirmButtonText: '复制脚本',
        cancelButtonText: '取消',
        type: 'info',
      },
    )
    await copyText(workerStartCommand.value, '脚本已复制！请打开「终端」粘贴执行')
  } catch {
    /* cancel */
  }
}
const imageModForm = reactive({
  tencent_secret_id: '',
  tencent_secret_key: '',
  tencent_region: 'ap-guangzhou',
  alibaba_access_key_id: '',
  alibaba_access_key_secret: '',
  alibaba_region: 'cn-shanghai',
})

const HIDDEN_CONFIG_KEYS = new Set([
  'image_moderation_tencent_secret_id',
  'image_moderation_tencent_secret_key',
  'image_moderation_tencent_region',
  'image_moderation_alibaba_access_key_id',
  'image_moderation_alibaba_access_key_secret',
  'image_moderation_alibaba_region',
])

const PAID_IMAGE_PROVIDERS = new Set(['tencent', 'alibaba'])

const visibleConfigs = computed(() =>
  configs.value.filter((row) => !HIDDEN_CONFIG_KEYS.has(row.config_key)),
)
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
    syncImageModForm()
    roles.value = results[1]
    users.value = canManageUsers.value ? results[2] : []
    if (canManageSettings.value) {
      await Promise.all([loadSensitiveWords(), loadPublishWorkers()])
    }
  } finally {
    loading.value = false
  }
}

async function loadPublishWorkers() {
  workersLoading.value = true
  try {
    publishWorkers.value = await api.listPublishWorkers()
  } finally {
    workersLoading.value = false
  }
}

async function openCreateWorker() {
  try {
    const { value } = await ElMessageBox.prompt('为本机电脑起个名字，如「办公室 Mac」', '新建 Worker', {
      confirmButtonText: '创建',
      cancelButtonText: '取消',
      inputPattern: /.+/,
      inputErrorMessage: '名称不能为空',
    })
    const created = await api.createPublishWorker(value.trim())
    openWorkerTokenDialog(created.token)
    await loadPublishWorkers()
    ElMessage.success('Worker 已创建')
  } catch (e) {
    if (e !== 'cancel') ElMessage.error(e.message || '创建失败')
  }
}

async function rotateWorkerToken(row) {
  try {
    await ElMessageBox.confirm(`确定重置「${row.name}」的 Token？旧 Token 将立即失效。`, '重置 Token', {
      type: 'warning',
    })
    const result = await api.rotatePublishWorkerToken(row.id)
    openWorkerTokenDialog(result.token)
    await loadPublishWorkers()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error(e.message)
  }
}

async function removeWorker(row) {
  try {
    await ElMessageBox.confirm(`确定删除 Worker「${row.name}」？`, '删除确认', { type: 'warning' })
    await api.deletePublishWorker(row.id)
    await loadPublishWorkers()
    ElMessage.success('已删除')
  } catch (e) {
    if (e !== 'cancel') ElMessage.error(e.message)
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
  image_moderation_provider: [
    { label: 'Stub（免费，默认通过）', value: 'stub' },
    { label: '腾讯云 IMS（按量计费）', value: 'tencent' },
    { label: '阿里云 Green（按量计费）', value: 'alibaba' },
  ],
}
const INT_CONFIG_KEYS = new Set([
  'max_auto_retries',
  'retry_delay_minutes',
  'material_retention_days',
  'scheduler_poll_interval_seconds',
  'rate_limit_min_interval_seconds',
  'rate_limit_daily_per_account',
  'rate_limit_max_concurrent',
  'publish_running_timeout_minutes',
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
  if (key === 'publish_running_timeout_minutes') return 0
  return 5
}

function intConfigMax(key) {
  if (key === 'max_auto_retries') return 10
  if (key === 'retry_delay_minutes') return 120
  if (key === 'material_retention_days') return 3650
  if (key === 'rate_limit_min_interval_seconds') return 86400
  if (key === 'rate_limit_daily_per_account') return 500
  if (key === 'rate_limit_max_concurrent') return 20
  if (key === 'publish_running_timeout_minutes') return 1440
  return 3600
}

function boolConfigOn(value) {
  return ['1', 'true', 'yes', 'on'].includes(String(value || '').trim().toLowerCase())
}

function configValue(key) {
  return configs.value.find((row) => row.config_key === key)?.config_value
}

function providerLabel(provider) {
  return (
    {
      stub: 'Stub（免费）',
      tencent: '腾讯云 IMS',
      alibaba: '阿里云 Green',
    }[provider] || provider
  )
}

async function confirmImageModerationBilling(provider, actionText) {
  const paid = PAID_IMAGE_PROVIDERS.has(provider)
  const detail = paid
    ? `将使用 ${providerLabel(provider)}。每次图片上传或文生图入库会调用云内容安全 API，试用额度用尽后按张计费。`
    : '将使用 Stub，不产生云审费用（默认全部通过，仅用于开发/联调）。'
  await ElMessageBox.confirm(`${actionText}\n\n${detail}\n\n是否继续？`, '图片内容审核', {
    type: 'warning',
    confirmButtonText: '确认',
    cancelButtonText: '取消',
  })
}

function syncImageModForm() {
  imageModForm.tencent_secret_id = configValue('image_moderation_tencent_secret_id') || ''
  imageModForm.tencent_secret_key = configValue('image_moderation_tencent_secret_key') || ''
  imageModForm.tencent_region = configValue('image_moderation_tencent_region') || 'ap-guangzhou'
  imageModForm.alibaba_access_key_id = configValue('image_moderation_alibaba_access_key_id') || ''
  imageModForm.alibaba_access_key_secret = configValue('image_moderation_alibaba_access_key_secret') || ''
  imageModForm.alibaba_region = configValue('image_moderation_alibaba_region') || 'cn-shanghai'
}

async function saveImageModSecrets() {
  imageModSaving.value = true
  try {
    const entries = [
      ['image_moderation_tencent_secret_id', imageModForm.tencent_secret_id],
      ['image_moderation_tencent_secret_key', imageModForm.tencent_secret_key],
      ['image_moderation_tencent_region', imageModForm.tencent_region || 'ap-guangzhou'],
      ['image_moderation_alibaba_access_key_id', imageModForm.alibaba_access_key_id],
      ['image_moderation_alibaba_access_key_secret', imageModForm.alibaba_access_key_secret],
      ['image_moderation_alibaba_region', imageModForm.alibaba_region || 'cn-shanghai'],
    ]
    for (const [key, value] of entries) {
      const row = configs.value.find((item) => item.config_key === key)
      await api.updateSystemConfig(key, {
        config_value: value,
        remark: row?.remark,
      })
      if (row) row.config_value = value
    }
    ElMessage.success('图片审核密钥已保存')
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    imageModSaving.value = false
  }
}

async function setBoolConfig(row, on) {
  if (row.config_key === 'image_moderation_enabled' && on) {
    const provider = configValue('image_moderation_provider') || 'stub'
    try {
      await confirmImageModerationBilling(provider, '开启图片内容审核')
    } catch {
      return
    }
  }
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
    if (row.config_key === 'image_moderation_enabled' && boolConfigOn(row.config_value)) {
      const provider = configValue('image_moderation_provider') || 'stub'
      await confirmImageModerationBilling(provider, '保存并开启图片内容审核')
    }
    if (row.config_key === 'image_moderation_provider' && PAID_IMAGE_PROVIDERS.has(row.config_value)) {
      await ElMessageBox.confirm(
        `切换为 ${providerLabel(row.config_value)} 后，开启图片审核将产生按量费用。是否保存？`,
        '图片审核 Provider',
        { type: 'warning', confirmButtonText: '保存', cancelButtonText: '取消' },
      )
    }
    await api.updateSystemConfig(row.config_key, { config_value: row.config_value, remark: row.remark })
    if (row.config_key === 'require_content_review') {
      ElMessage.success(boolConfigOn(row.config_value) ? '内容审核已开启' : '内容审核已关闭')
    } else if (row.config_key === 'image_moderation_enabled') {
      ElMessage.success(boolConfigOn(row.config_value) ? '图片内容审核已开启' : '图片内容审核已关闭')
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
.image-mod-form {
  max-width: 640px;
}
.field-hint {
  margin: 6px 0 0;
  font-size: 12px;
  line-height: 1.5;
}
</style>
