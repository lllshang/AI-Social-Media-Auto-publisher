import axios from 'axios'
import { useAuthStore } from '@/stores/auth'
import router from '@/router'

const http = axios.create({
  baseURL: import.meta.env.DEV ? '' : '',
  timeout: 300000,
})

http.interceptors.request.use((config) => {
  const auth = useAuthStore()
  if (auth.token) {
    config.headers.Authorization = `Bearer ${auth.token}`
  }
  return config
})

http.interceptors.response.use(
  (res) => res.data,
  (err) => {
    const status = err.response?.status
    const detail = err.response?.data?.detail
    let message = err.message || '请求失败'
    if (typeof detail === 'string') {
      message = detail
    } else if (detail && typeof detail === 'object') {
      message = JSON.stringify(detail)
    } else if (status === 500) {
      message = '服务器内部错误，请查看 API 日志或确认 AI Key 是否已配置'
    }

    if (status === 401 && !err.config?.url?.includes('/api/auth/login')) {
      const auth = useAuthStore()
      auth.logout()
      const current = router.currentRoute.value
      if (current.name !== 'login') {
        router.replace({
          name: 'login',
          query: {
            redirect: current.fullPath,
            reason: 'expired',
          },
        })
      }
    }

    return Promise.reject(new Error(message))
  },
)

export const api = {
  login: (username, password) => http.post('/api/auth/login', { username, password }),
  getRuntimeInfo: () => http.get('/api/system/runtime'),
  getDashboardSummary: () => http.get('/api/dashboard/summary'),
  listAccountGroups: () => http.get('/api/account-groups'),
  createAccountGroup: (payload) => http.post('/api/account-groups', payload),
  updateAccountGroup: (id, payload) => http.put(`/api/account-groups/${id}`, payload),
  deleteAccountGroup: (id) => http.delete(`/api/account-groups/${id}`),
  assignAccountGroup: (accountId, groupId) =>
    http.post(`/api/platform-accounts/${accountId}/group`, { group_id: groupId }),
  listAccounts: (params) => {
    const query = typeof params === 'string' ? { platform: params } : params || {}
    return http.get('/api/platform-accounts', { params: query })
  },
  buildPrompt: (payload) => http.post('/api/ai/prompt/build', payload),
  listAiGenerations: (params) => http.get('/api/logs/ai-generations', { params }),
  listOperationLogs: (params) => http.get('/api/logs/operations', { params }),
  createAccount: (platform, account_name) => http.post('/api/platform-accounts', { platform, account_name }),
  deleteAccount: (id) => http.delete(`/api/platform-accounts/${id}`),
  loginAccount: (id) => http.post(`/api/platform-accounts/${id}/login`),
  startLoginAccount: (id) => http.post(`/api/platform-accounts/${id}/login/start`),
  getLoginSession: (sessionId) => http.get(`/api/platform-accounts/login-sessions/${sessionId}`),
  checkCookie: (id) => http.post(`/api/platform-accounts/${id}/check-cookie`),
  listMaterialCategories: () => http.get('/api/materials/categories'),
  listMaterials: (params) => http.get('/api/materials', { params }),
  deleteMaterial: (id) => http.delete(`/api/materials/${id}`),
  uploadMaterial: (file, { name, category } = {}) => {
    const form = new FormData()
    form.append('file', file)
    if (name) form.append('name', name)
    if (category) form.append('category', category)
    return http.post('/api/materials/upload', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },
  generateText: (topic, platform = 'xhs', content_type = 'note') =>
    http.post('/api/ai/text/generate', { topic, platform, content_type }),
  generateImage: (topic, platform = 'xhs', ratio = '3:4', count = 1, cover_text) =>
    http.post('/api/ai/image/generate', { topic, platform, ratio, count, cover_text: cover_text || null }),
  getModels: () => http.get('/api/ai/models'),
  listProviders: () => http.get('/api/ai/models/providers'),
  saveProviderConfig: (payload) => http.put('/api/ai/models/providers/config', payload),
  addCustomProvider: (payload) => http.post('/api/ai/models/providers/custom', payload),
  deleteCustomProvider: (provider) => http.delete(`/api/ai/models/providers/custom/${provider}`),
  detectModels: () => http.post('/api/ai/models/detect'),
  selectModel: (payload) => http.post('/api/ai/models/select', payload),
  listTasks: (params) => http.get('/api/publish-tasks', { params }),
  getTask: (id) => http.get(`/api/publish-tasks/${id}`),
  createTask: (payload) => http.post('/api/publish-tasks', payload),
  updateTask: (id, payload) => http.put(`/api/publish-tasks/${id}`, payload),
  submitTask: (id) => http.post(`/api/publish-tasks/${id}/submit`),
  approveTask: (id) => http.post(`/api/publish-tasks/${id}/approve`),
  rejectTask: (id, reason) => http.post(`/api/publish-tasks/${id}/reject`, { reason }),
  executeTask: (id) => http.post(`/api/publish-tasks/${id}/execute`),
  retryTask: (id) => http.post(`/api/publish-tasks/${id}/retry`),
  reopenTask: (id) => http.post(`/api/publish-tasks/${id}/reopen`),
  deleteTask: (id) => http.delete(`/api/publish-tasks/${id}`),
  getTaskLogs: (id) => http.get(`/api/publish-tasks/${id}/logs`),
}

export default http
