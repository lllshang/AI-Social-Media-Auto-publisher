<template>
  <div>
    <div class="toolbar">
      <h2 class="page-title">平台账号</h2>
      <el-button type="primary" @click="showCreate = true">新建账号</el-button>
    </div>
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
    <div class="page-card">
      <el-table :data="accounts" v-loading="loading">
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column prop="account_name" label="账号名" />
        <el-table-column prop="platform" label="平台" width="90" />
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="statusType(row.status)">{{ row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="380">
          <template #default="{ row }">
            <el-button size="small" @click="check(row)">检测 Cookie</el-button>
            <el-button size="small" type="warning" :loading="loggingInId === row.id" @click="login(row)">
              扫码登录
            </el-button>
            <el-button size="small" type="danger" @click="remove(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <el-dialog v-model="showCreate" title="新建小红书账号" width="420px">
      <el-form label-width="80px">
        <el-form-item label="账号名">
          <el-input v-model="form.account_name" placeholder="如 test1" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreate = false">取消</el-button>
        <el-button type="primary" @click="create">创建</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="qrVisible" title="扫码登录" width="420px" :close-on-click-modal="false">
      <p class="muted">{{ qrMessage }}</p>
      <div v-if="!qrDataUrl && loggingIn" class="qr-loading">正在生成二维码...</div>
      <img v-if="qrDataUrl" :src="qrDataUrl" alt="qrcode" class="qr-image" />
    </el-dialog>
  </div>
</template>

<script setup>
import { onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { api } from '@/api'

const loading = ref(false)
const loggingIn = ref(false)
const loggingInId = ref(null)
const accounts = ref([])
const showCreate = ref(false)
const form = reactive({ account_name: 'test1' })
const qrVisible = ref(false)
const qrDataUrl = ref('')
const qrMessage = ref('')
const pollTimer = ref(null)
const runtime = ref({
  docker: false,
  xhs_qr_login_supported: true,
  docker_login_hint: '',
  local_app_url: 'http://127.0.0.1:8765/app/',
})

function statusType(status) {
  if (status === 'active') return 'success'
  if (status === 'expired') return 'danger'
  return 'info'
}

function stopPolling() {
  if (pollTimer.value) {
    clearInterval(pollTimer.value)
    pollTimer.value = null
  }
}

async function pollLoginSession(sessionId) {
  const res = await api.getLoginSession(sessionId)
  qrMessage.value = res.message || '请使用小红书 App 扫码'
  if (res.qrcode_data_url) {
    qrDataUrl.value = res.qrcode_data_url
  }
  if (res.success) {
    stopPolling()
    loggingIn.value = false
    loggingInId.value = null
    ElMessage.success('登录成功')
    qrVisible.value = false
    load()
    return
  }
  if (['failed', 'timeout'].includes(res.status)) {
    stopPolling()
    loggingIn.value = false
    loggingInId.value = null
    ElMessage.error(res.message || '登录失败')
  }
}

async function load() {
  loading.value = true
  try {
    accounts.value = await api.listAccounts('xhs')
    runtime.value = await api.getRuntimeInfo()
  } finally {
    loading.value = false
  }
}

async function create() {
  try {
    await api.createAccount('xhs', form.account_name)
    ElMessage.success('创建成功')
    showCreate.value = false
    load()
  } catch (e) {
    ElMessage.error(e.message)
  }
}

async function check(row) {
  try {
    const res = await api.checkCookie(row.id)
    ElMessage.success(res.valid ? 'Cookie 有效' : 'Cookie 失效')
    load()
  } catch (e) {
    ElMessage.error(e.message)
  }
}

async function login(row) {
  if (runtime.value.docker && !runtime.value.xhs_qr_login_supported) {
    ElMessage.warning(runtime.value.docker_login_hint)
    return
  }
  stopPolling()
  loggingIn.value = true
  loggingInId.value = row.id
  qrVisible.value = true
  qrDataUrl.value = ''
  qrMessage.value = '正在启动浏览器，请稍候...'
  try {
    const res = await api.startLoginAccount(row.id)
    if (res.qrcode_data_url) {
      qrDataUrl.value = res.qrcode_data_url
    }
    qrMessage.value = res.message || '请使用小红书 App 扫码'
    if (res.success) {
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
    }, 2000)
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

onMounted(load)
onBeforeUnmount(stopPolling)
</script>

<style scoped>
.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
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
</style>
