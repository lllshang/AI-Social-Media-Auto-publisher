import { defineStore } from 'pinia'
import { api } from '@/api'

export const useAuthStore = defineStore('auth', {
  state: () => ({
    token: localStorage.getItem('ai_publish_token') || '',
    username: localStorage.getItem('ai_publish_user') || '',
    roleName: localStorage.getItem('ai_publish_role') || '',
    permissions: JSON.parse(localStorage.getItem('ai_publish_permissions') || '[]'),
  }),
  getters: {
    isLoggedIn: (state) => Boolean(state.token),
  },
  actions: {
    async login(username, password) {
      const data = await api.login(username, password)
      this.token = data.access_token
      this.username = data.username || username
      this.roleName = data.role_name || ''
      this.permissions = data.permissions || []
      localStorage.setItem('ai_publish_token', this.token)
      localStorage.setItem('ai_publish_user', this.username)
      localStorage.setItem('ai_publish_role', this.roleName)
      localStorage.setItem('ai_publish_permissions', JSON.stringify(this.permissions))
    },
    logout() {
      this.token = ''
      this.username = ''
      this.roleName = ''
      this.permissions = []
      localStorage.removeItem('ai_publish_token')
      localStorage.removeItem('ai_publish_user')
      localStorage.removeItem('ai_publish_role')
      localStorage.removeItem('ai_publish_permissions')
    },
  },
})
