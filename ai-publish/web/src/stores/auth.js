import { defineStore } from 'pinia'
import { api } from '@/api'

export const useAuthStore = defineStore('auth', {
  state: () => ({
    token: localStorage.getItem('ai_publish_token') || '',
    username: localStorage.getItem('ai_publish_user') || '',
  }),
  getters: {
    isLoggedIn: (state) => Boolean(state.token),
  },
  actions: {
    async login(username, password) {
      const data = await api.login(username, password)
      this.token = data.access_token
      this.username = username
      localStorage.setItem('ai_publish_token', this.token)
      localStorage.setItem('ai_publish_user', username)
    },
    logout() {
      this.token = ''
      this.username = ''
      localStorage.removeItem('ai_publish_token')
      localStorage.removeItem('ai_publish_user')
    },
  },
})
