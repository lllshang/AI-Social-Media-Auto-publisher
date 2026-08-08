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
  getMe: () => http.get('/api/auth/me'),
  changePassword: (payload) => http.post('/api/auth/change-password', payload),
  listUsers: () => http.get('/api/users'),
  createUser: (payload) => http.post('/api/users', payload),
  updateUser: (id, payload) => http.put(`/api/users/${id}`, payload),
  resetUserPassword: (id, newPassword) => http.post(`/api/users/${id}/reset-password`, { new_password: newPassword }),
  listSystemConfigs: () => http.get('/api/system/configs'),
  updateSystemConfig: (key, payload) => http.put(`/api/system/configs/${key}`, payload),
  listSensitiveWords: (params) => http.get('/api/risk/sensitive-words', { params }),
  createSensitiveWord: (payload) => http.post('/api/risk/sensitive-words', payload),
  batchImportSensitiveWords: (words) => http.post('/api/risk/sensitive-words/batch', { words }),
  deleteSensitiveWord: (id) => http.delete(`/api/risk/sensitive-words/${id}`),
  listRoles: () => http.get('/api/roles'),
  getRuntimeInfo: () => http.get('/api/system/runtime'),
  getSystemFeatures: () => http.get('/api/system/features'),
  getDashboardSummary: () => http.get('/api/dashboard/summary'),
  listContentTemplates: (params) => http.get('/api/content-templates', { params }),
  listTemplateIndustries: () => http.get('/api/content-templates/industries'),
  getContentTemplate: (id) => http.get(`/api/content-templates/${id}`),
  createContentTemplate: (payload) => http.post('/api/content-templates', payload),
  updateContentTemplate: (id, payload) => http.put(`/api/content-templates/${id}`, payload),
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
  updateAccount: (id, payload) => http.put(`/api/platform-accounts/${id}`, payload),
  deleteAccount: (id) => http.delete(`/api/platform-accounts/${id}`),
  loginAccount: (id) => http.post(`/api/platform-accounts/${id}/login`),
  startLoginAccount: (id) => http.post(`/api/platform-accounts/${id}/login/start`),
  getLoginSession: (sessionId) => http.get(`/api/platform-accounts/login-sessions/${sessionId}`),
  checkCookie: (id) => http.post(`/api/platform-accounts/${id}/check-cookie`),
  listMaterialCategories: () => http.get('/api/materials/categories'),
  listMaterials: (params) => http.get('/api/materials', { params }),
  getMaterial: (id) => http.get(`/api/materials/${id}`),
  saveTextMaterial: (payload) => http.post('/api/materials/text', payload),
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
  generateImage: (payload) => {
    if (typeof payload === 'string') {
      const [topic, platform = 'xhs', ratio = '3:4', count = 1, cover_text] = arguments
      return http.post('/api/ai/image/generate', {
        topic,
        platform,
        ratio,
        count,
        cover_text: cover_text || null,
      })
    }
    return http.post('/api/ai/image/generate', payload)
  },
  generateVideo: (payload) => http.post('/api/ai/video/generate', payload),
  listAvatars: (params) => http.get('/api/avatars', { params }),
  getAvatar: (id) => http.get(`/api/avatars/${id}`),
  createAvatar: (payload) => http.post('/api/avatars', payload),
  updateAvatar: (id, payload) => http.put(`/api/avatars/${id}`, payload),
  deleteAvatar: (id) => http.delete(`/api/avatars/${id}`),
  // 为指定数字人生成 2 张带背景的候选参考图（图生图）
  generateAvatarBackground: (id, payload) =>
    http.post(`/api/avatars/${id}/generate-background`, payload),
  uploadAvatarThumbnail: (id, file) => {
    const form = new FormData()
    form.append('file', file)
    return http.post(`/api/avatars/${id}/upload-thumbnail`, form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },
  // === TTS 配音音色 ===
  listVoices: () => http.get('/api/voices'),
  // === 声音复刻（VRS）===
  listVoiceClones: () => http.get('/api/voice-clone'),
  createVoiceClone: (file, { name, voice_gender }) => {
    const form = new FormData()
    form.append('audio', file)
    if (name) form.append('name', name)
    if (voice_gender != null) form.append('voice_gender', String(voice_gender))
    return http.post('/api/voice-clone', form)
  },
  getVoiceCloneStatus: (taskId) => http.get(`/api/voice-clone/${taskId}/status`),
  getVoiceCloneTrainingText: () => http.get('/api/voice-clone/training-text'),
  previewVoice: ({ text, voice_id, rate, volume }) =>
    http.post(
      '/api/voices/preview',
      { text, voice_id, rate, volume },
      { responseType: 'blob' },
    ),
  getModels: () => http.get('/api/ai/models'),
  listProviders: () => http.get('/api/ai/models/providers'),
  saveProviderConfig: (payload) => http.put('/api/ai/models/providers/config', payload),
  addCustomProvider: (payload) => http.post('/api/ai/models/providers/custom', payload),
  deleteCustomProvider: (provider) => http.delete(`/api/ai/models/providers/custom/${provider}`),
  detectModels: () => http.post('/api/ai/models/detect'),
  selectModel: (payload) => http.post('/api/ai/models/select', payload),
  listTasks: (params) => http.get('/api/publish-tasks', { params }),
  listPendingReviews: (params) => http.get('/api/reviews/pending', { params }),
  listReviewHistory: (params) => http.get('/api/reviews/history', { params }),
  getTask: (id) => http.get(`/api/publish-tasks/${id}`),
  createTask: (payload) => http.post('/api/publish-tasks', payload),
  updateTask: (id, payload) => http.put(`/api/publish-tasks/${id}`, payload),
  submitTask: (id) => http.post(`/api/publish-tasks/${id}/submit`),
  approveTask: (id) => http.post(`/api/publish-tasks/${id}/approve`),
  rejectTask: (id, reason) => http.post(`/api/publish-tasks/${id}/reject`, { reason }),
  executeTask: (id) => http.post(`/api/publish-tasks/${id}/execute`),
  recoverTask: (id) => http.post(`/api/publish-tasks/${id}/recover`),
  retryTask: (id) => http.post(`/api/publish-tasks/${id}/retry`),
  reopenTask: (id) => http.post(`/api/publish-tasks/${id}/reopen`),
  deleteTask: (id) => http.delete(`/api/publish-tasks/${id}`),
  getTaskLogs: (id) => http.get(`/api/publish-tasks/${id}/logs`),
  listPublishWorkers: () => http.get('/api/publish-workers'),
  createPublishWorker: (name) => http.post('/api/publish-workers', { name }),
  deletePublishWorker: (id) => http.delete(`/api/publish-workers/${id}`),
  rotatePublishWorkerToken: (id) => http.post(`/api/publish-workers/${id}/rotate-token`),
  getTrendingStatus: () => http.get('/api/trending/status'),
  listTrendingItems: (params) => http.get('/api/trending/items', { params }),
  fetchTrending: () => http.post('/api/trending/fetch'),
  aiRecommendTrending: (payload) => http.post('/api/trending/ai-recommend', payload),
  saveTrendingTemplate: (id) => http.post(`/api/trending/items/${id}/save-template`),

  // 内容创作
  createSession: (data) => http.post('/api/create/session', data),
  getSessions: (params) => http.get('/api/create/sessions', { params }),
  getSession: (id) => http.get(`/api/create/${id}`),
  deleteSession: (id) => http.delete(`/api/create/${id}`),
  generateCopy: (id) => http.post(`/api/create/${id}/generate-copy`),
  polishCopy: (id, data) => http.post(`/api/create/${id}/polish`, data),
  getCopy: (id) => http.get(`/api/create/${id}/copy`),
  updateCopy: (id, data) => http.put(`/api/create/${id}/copy`, data),
  startGeneration: (id, data) => http.post(`/api/create/${id}/generate`, data),
  getGenerations: (id) => http.get(`/api/create/${id}/generations`),
  getGenerationStatus: (genId) => http.get(`/api/create/generations/${genId}`),
  completeSession: (id) => http.post(`/api/create/${id}/complete`),
  saveDraft: (id, data) => http.put(`/api/create/${id}/save-draft`, data),
  getDrafts: () => http.get('/api/create/drafts'),
}

export default http
