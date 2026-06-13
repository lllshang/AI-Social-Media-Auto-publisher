<template>
  <div>
    <div class="toolbar">
      <h2 class="page-title">平台账号</h2>
      <div v-if="can('accounts:write')">
        <el-button @click="showGroupManage = true">分组管理</el-button>
        <el-button type="primary" @click="openCreate">新建账号</el-button>
      </div>
    </div>
    <el-alert
      v-if="!runtime.bilibili_enabled"
      type="warning"
      :closable="false"
      show-icon
      class="runtime-alert"
      title="B站功能未开启"
      description="平台列表不显示 B站 是预期行为。请在服务器 ai-publish/.env 设置 BILIBILI_ENABLED=true，执行 bash scripts/upgrade.sh 或 docker compose restart api 后刷新本页。"
    />
    <el-alert
      v-if="runtime.docker && runtime.xhs_qr_login_supported"
      type="info"
      :closable="false"
      show-icon
      class="runtime-alert"
      title="服务器扫码说明"
      :description="runtime.docker_login_hint"
    />
    <el-alert
      v-else-if="runtime.docker && !runtime.xhs_qr_login_supported"
      type="warning"
      :closable="false"
      show-icon
      class="runtime-alert"
      title="扫码功能未就绪"
      :description="runtime.docker_login_hint"
    />
    <el-alert
      v-if="filterPlatform === 'bilibili'"
      type="info"
      :closable="false"
      show-icon
      class="runtime-alert"
      title="B站登录说明"
      :description="platformLoginHint('bilibili')"
    />
    <div class="page-card filter-bar">
      <el-radio-group v-model="filterPlatform" @change="load">
        <el-radio-button label="">全部平台</el-radio-button>
        <el-radio-button v-for="p in availablePlatforms" :key="p.value" :label="p.value">{{ p.label }}</el-radio-button>
      </el-radio-group>
      <el-select
        v-model="filterGroupId"
        clearable
        placeholder="全部分组"
        class="filter-group-select"
        @change="load"
      >
        <el-option v-for="g in groups" :key="g.id" :label="g.name" :value="g.id" />
      </el-select>
    </div>
    <div class="page-card">
      <el-table :data="accounts" v-loading="loading">
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column prop="account_name" label="账号名" />
        <el-table-column prop="remark" label="备注" min-width="120" show-overflow-tooltip />
        <el-table-column label="平台" width="100">
          <template #default="{ row }">{{ platformLabel(row.platform) }}</template>
        </el-table-column>
        <el-table-column label="分组" width="140">
          <template #default="{ row }">
            <el-select
              v-if="can('accounts:write')"
              :model-value="row.group_id"
              clearable
              placeholder="未分组"
              size="small"
              style="width: 120px"
              @change="(val) => assignGroup(row, val)"
            >
              <el-option v-for="g in groups" :key="g.id" :label="g.name" :value="g.id" />
            </el-select>
            <span v-else>{{ row.group_name || '未分组' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="本机/线路" width="140">
          <template #default="{ row }">
            <el-tag v-if="row.worker_name" size="small" type="warning">{{ row.worker_name }}</el-tag>
            <el-tag v-if="row.has_publish_proxy" size="small" style="margin-left: 4px">已配线路</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="statusType(row.status)">{{ row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column v-if="can('accounts:write')" label="操作" width="440">
          <template #default="{ row }">
            <el-button size="small" @click="openEdit(row)">编辑</el-button>
            <el-button size="small" :loading="checkingCookieId === row.id" @click="check(row)">检测 Cookie</el-button>
            <el-button size="small" type="warning" :loading="loggingInId === row.id" @click="login(row)">
              扫码登录
            </el-button>
            <el-button size="small" type="danger" @click="remove(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <el-dialog v-model="showEdit" title="编辑平台账号" width="480px">
      <el-form label-width="100px">
        <el-form-item label="平台">
          <span>{{ platformLabel(editForm.platform) }}</span>
        </el-form-item>
        <el-form-item label="账号名">
          <el-input v-model="editForm.account_name" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="editForm.remark" placeholder="可选" />
        </el-form-item>
        <el-form-item label="本机 Worker">
          <el-select v-model="editForm.worker_id" clearable placeholder="默认由服务器执行" style="width: 100%">
            <el-option v-for="w in publishWorkers" :key="w.id" :label="w.name" :value="w.id" />
          </el-select>
          <p class="muted field-hint">绑定后，该账号的发布任务将派发到对应本机电脑执行。</p>
        </el-form-item>
        <el-form-item label="网络线路">
          <el-input
            v-model="editForm.publish_proxy"
            placeholder="http://用户名:密码@地址:端口 或 socks5://地址:端口"
            clearable
          />
          <p v-if="editForm.publish_proxy_masked" class="muted field-hint">
            当前已配置：{{ editForm.publish_proxy_masked }}
            <el-button link type="primary" @click="clearPublishProxy">清除线路</el-button>
          </p>
          <p v-else class="muted field-hint">选填。为此账号单独指定网络，向服务商索取线路地址后粘贴。登录与发布使用同一线路。</p>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showEdit = false">取消</el-button>
        <el-button type="primary" @click="saveEdit">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="showCreate" :title="`新建${platformLabel(form.platform)}账号`" width="420px">
      <el-form label-width="80px">
        <el-form-item label="平台">
          <el-select v-model="form.platform" style="width: 100%">
            <el-option v-for="p in availablePlatforms" :key="p.value" :label="p.label" :value="p.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="账号名">
          <el-input v-model="form.account_name" placeholder="如 test1" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreate = false">取消</el-button>
        <el-button type="primary" @click="create">创建</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="showGroupManage" title="账号分组" width="520px">
      <el-form inline @submit.prevent>
        <el-form-item label="新分组">
          <el-input v-model="groupForm.name" placeholder="分组名称" style="width: 160px" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="createGroup">添加</el-button>
        </el-form-item>
      </el-form>
      <el-table :data="groups" size="small">
        <el-table-column prop="name" label="名称" />
        <el-table-column prop="account_count" label="账号数" width="80" />
        <el-table-column prop="remark" label="备注" show-overflow-tooltip />
        <el-table-column label="操作" width="90">
          <template #default="{ row }">
            <el-button size="small" type="danger" link @click="removeGroup(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-dialog>

    <el-dialog v-model="qrVisible" title="扫码登录" width="420px" :close-on-click-modal="false">
      <p class="muted">{{ qrMessage }}</p>
      <p v-if="loginPlatform === 'bilibili' && !qrDataUrl && loggingIn" class="muted bilibili-login-hint">
        首次 B 站登录可能需 1–3 分钟下载组件，请保持窗口打开；二维码出现后请在约 60 秒内扫码。
      </p>
      <div v-if="!qrDataUrl && loggingIn" class="qr-loading">
        {{ loginPlatform === 'bilibili' ? '正在准备 B 站二维码…' : '正在生成二维码...' }}
      </div>
      <img v-if="qrDataUrl" :src="qrDataUrl" alt="qrcode" class="qr-image" />
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { ElLoading, ElMessage, ElMessageBox } from 'element-plus'
import { api } from '@/api'
import { platformsForRuntime, platformAppName, platformLabel, platformLoginHint } from '@/constants/platforms'
import { usePermission } from '@/composables/usePermission'

const { can } = usePermission()

const loading = ref(false)
const loggingIn = ref(false)
const loggingInId = ref(null)
const checkingCookieId = ref(null)
const accounts = ref([])
const groups = ref([])
const filterPlatform = ref('')
const filterGroupId = ref(null)
const showCreate = ref(false)
const showEdit = ref(false)
const showGroupManage = ref(false)
const groupForm = reactive({ name: '' })
const form = reactive({ platform: 'xhs', account_name: 'test1' })
const publishWorkers = ref([])
const editForm = reactive({
  id: null,
  platform: '',
  account_name: '',
  remark: '',
  worker_id: null,
  publish_proxy: '',
  publish_proxy_masked: '',
  clear_publish_proxy: false,
})
const qrVisible = ref(false)
const qrDataUrl = ref('')
const qrMessage = ref('')
const pollTimer = ref(null)
const pollCount = ref(0)
const loginPlatform = ref('xhs')
const runtime = ref({
  docker: false,
  xhs_qr_login_supported: true,
  qr_login_supported: true,
  bilibili_enabled: false,
  docker_login_hint: '',
  local_app_url: 'http://127.0.0.1:8765/app/',
})
const availablePlatforms = computed(() => platformsForRuntime(runtime.value))

function statusType(status) {
  if (status === 'active') return 'success'
  if (status === 'expired') return 'danger'
  return 'info'
}

function openCreate() {
  form.platform = filterPlatform.value || 'xhs'
  showCreate.value = true
}

function openEdit(row) {
  editForm.id = row.id
  editForm.platform = row.platform
  editForm.account_name = row.account_name
  editForm.remark = row.remark || ''
  editForm.worker_id = row.worker_id ?? null
  editForm.publish_proxy = ''
  editForm.publish_proxy_masked = row.publish_proxy_masked || ''
  editForm.clear_publish_proxy = false
  showEdit.value = true
}

function clearPublishProxy() {
  editForm.publish_proxy = ''
  editForm.publish_proxy_masked = ''
  editForm.clear_publish_proxy = true
}

async function saveEdit() {
  try {
    const payload = {
      account_name: editForm.account_name,
      remark: editForm.remark,
      worker_id: editForm.worker_id,
    }
    if (editForm.publish_proxy) {
      payload.publish_proxy = editForm.publish_proxy
    } else if (editForm.clear_publish_proxy) {
      payload.clear_publish_proxy = true
    }
    await api.updateAccount(editForm.id, payload)
    ElMessage.success('已保存')
    showEdit.value = false
    await load()
  } catch (e) {
    ElMessage.error(e.message)
  }
}

function stopPolling() {
  if (pollTimer.value) {
    clearInterval(pollTimer.value)
    pollTimer.value = null
  }
}

async function finishLoginSuccess(message = '登录成功') {
  stopPolling()
  loggingIn.value = false
  loggingInId.value = null
  pollCount.value = 0
  ElMessage.success(message)
  qrVisible.value = false
  await load()
}

async function pollLoginSession(sessionId) {
  pollCount.value += 1
  const res = await api.getLoginSession(sessionId)
  if (res.qrcode_data_url) {
    qrDataUrl.value = res.qrcode_data_url
  }
    if (res.status === 'waiting_scan' && res.qrcode_data_url) {
    const waited = pollCount.value
    const isBili = loginPlatform.value === 'bilibili'
    if (res.message && res.message.includes('已扫码')) {
      qrMessage.value = res.message
    } else {
      qrMessage.value =
        waited >= 15
          ? `手机已确认？正在同步登录状态（已等待 ${waited} 秒，最长约 5 分钟）…`
          : isBili
            ? '请用哔哩哔哩 App 扫码；扫码后请在手机上点击确认登录…'
            : `请使用${platformAppName(loginPlatform.value)}扫码；手机确认后请稍候，正在同步登录状态…`
    }
  } else if (res.message) {
    qrMessage.value = res.message
  } else {
    qrMessage.value = `请使用${platformAppName(loginPlatform.value)}扫码`
  }
  if (res.success || res.status === 'success') {
    await finishLoginSuccess()
    return
  }
  if (['failed', 'timeout', 'cookie_invalid'].includes(res.status)) {
    stopPolling()
    loggingIn.value = false
    loggingInId.value = null
    pollCount.value = 0
    qrMessage.value = res.message || '登录失败'
    ElMessage.error(res.message || '登录失败')
  }
}

async function loadGroups() {
  groups.value = await api.listAccountGroups()
}

async function load() {
  loading.value = true
  try {
    const params = {}
    if (filterPlatform.value) params.platform = filterPlatform.value
    if (filterGroupId.value) params.group_id = filterGroupId.value
    accounts.value = await api.listAccounts(params)
    runtime.value = await api.getRuntimeInfo()
  } finally {
    loading.value = false
  }
}

async function createGroup() {
  if (!groupForm.name.trim()) return ElMessage.warning('请输入分组名称')
  try {
    await api.createAccountGroup({ name: groupForm.name.trim() })
    groupForm.name = ''
    await loadGroups()
    ElMessage.success('分组已创建')
  } catch (e) {
    ElMessage.error(e.message)
  }
}

async function removeGroup(row) {
  try {
    await ElMessageBox.confirm(`确定删除分组「${row.name}」？账号将变为未分组`, '删除确认', { type: 'warning' })
    await api.deleteAccountGroup(row.id)
    if (filterGroupId.value === row.id) filterGroupId.value = null
    await loadGroups()
    load()
    ElMessage.success('已删除')
  } catch (e) {
    if (e !== 'cancel') ElMessage.error(e.message)
  }
}

async function assignGroup(row, groupId) {
  try {
    await api.assignAccountGroup(row.id, groupId ?? null)
    ElMessage.success('分组已更新')
    load()
  } catch (e) {
    ElMessage.error(e.message)
    load()
  }
}

async function create() {
  try {
    await api.createAccount(form.platform, form.account_name)
    ElMessage.success('创建成功')
    showCreate.value = false
    filterPlatform.value = form.platform
    load()
  } catch (e) {
    ElMessage.error(e.message)
  }
}

async function check(row) {
  if (checkingCookieId.value) return
  checkingCookieId.value = row.id
  const loadingInstance = ElLoading.service({
    lock: true,
    text: `正在检测「${row.account_name}」Cookie，请稍候…`,
    background: 'rgba(0, 0, 0, 0.35)',
  })
  try {
    const res = await api.checkCookie(row.id)
    ElMessage.success(res.valid ? 'Cookie 有效' : 'Cookie 已失效')
    await load()
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    checkingCookieId.value = null
    loadingInstance.close()
  }
}

function loginPreparingMessage(platform) {
  if (platform === 'bilibili') {
    return '正在准备 B 站二维码（首次可能需 1–3 分钟）…'
  }
  return '正在启动浏览器，请稍候...'
}

async function login(row) {
  if (row.platform === 'bilibili' && !runtime.value.bilibili_enabled) {
    ElMessage.warning('B站功能未启用，请在服务器设置 BILIBILI_ENABLED=true 后重启')
    return
  }
  const qrSupported = runtime.value.qr_login_supported ?? runtime.value.xhs_qr_login_supported
  if (row.platform !== 'bilibili' && runtime.value.docker && !qrSupported) {
    ElMessage.warning(runtime.value.docker_login_hint)
    return
  }
  loginPlatform.value = row.platform
  stopPolling()
  pollCount.value = 0
  loggingIn.value = true
  loggingInId.value = row.id
  qrVisible.value = true
  qrDataUrl.value = ''
  qrMessage.value = loginPreparingMessage(row.platform)
  try {
    const res = await api.startLoginAccount(row.id)
    if (res.qrcode_data_url) {
      qrDataUrl.value = res.qrcode_data_url
    }
    qrMessage.value = res.message || `请使用${platformAppName(row.platform)}扫码`
    if (res.status === 'success' && res.success) {
      ElMessage.success('登录成功')
      qrVisible.value = false
      loggingIn.value = false
      loggingInId.value = null
      load()
      return
    }
    pollTimer.value = setInterval(() => {
      pollLoginSession(res.session_id).catch((e) => {
        stopPolling()
        loggingIn.value = false
        loggingInId.value = null
        ElMessage.error(e.message)
      })
    }, 1000)
    await pollLoginSession(res.session_id)
  } catch (e) {
    loggingIn.value = false
    loggingInId.value = null
    qrVisible.value = false
    ElMessage.error(e.message)
  }
}

async function remove(row) {
  try {
    await ElMessageBox.confirm(`确定删除账号「${row.account_name}」？`, '删除确认', { type: 'warning' })
    await api.deleteAccount(row.id)
    ElMessage.success('已删除')
    load()
  } catch (e) {
    if (e !== 'cancel') ElMessage.error(e.message || '删除失败')
  }
}

async function loadWorkers() {
  if (!can('settings:write')) return
  try {
    publishWorkers.value = await api.listPublishWorkers()
  } catch {
    publishWorkers.value = []
  }
}

onMounted(async () => {
  await loadGroups()
  await loadWorkers()
  load()
})
onBeforeUnmount(stopPolling)
</script>

<style scoped>
.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.filter-bar {
  margin-bottom: 16px;
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
}
.filter-bar :deep(.el-radio-group) {
  display: inline-flex;
  vertical-align: middle;
}
.filter-group-select {
  width: 160px;
}
.filter-group-select :deep(.el-input__wrapper) {
  height: 32px;
}
.filter-bar :deep(.el-radio-button__inner) {
  height: 32px;
  line-height: 32px;
  padding: 0 15px;
}
.runtime-alert {
  margin-bottom: 16px;
}
.qr-image {
  width: 100%;
  max-width: 320px;
  display: block;
  margin: 0 auto;
}
.qr-loading {
  text-align: center;
  color: #909399;
  padding: 24px 0;
}
.field-hint {
  margin: 6px 0 0;
  font-size: 12px;
  line-height: 1.5;
}
</style>
