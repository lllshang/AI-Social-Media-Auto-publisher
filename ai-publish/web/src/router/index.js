import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { can as canPerm, canAny as canAnyPerm } from '@/utils/permissions'

const routes = [
  {
    path: '/login',
    name: 'login',
    component: () => import('@/views/LoginView.vue'),
    meta: { public: true },
  },
  {
    path: '/',
    component: () => import('@/layouts/MainLayout.vue'),
    children: [
      { path: '', name: 'dashboard', meta: { permission: 'dashboard:read' }, component: () => import('@/views/DashboardView.vue') },
      { path: 'accounts', name: 'accounts', meta: { permission: 'accounts:read' }, component: () => import('@/views/AccountsView.vue') },
      { path: 'models', name: 'models', meta: { permission: 'models:read' }, component: () => import('@/views/ModelsView.vue') },
      { path: 'avatars', name: 'avatars', meta: { permission: 'avatars:read' }, component: () => import('@/views/AvatarsView.vue') },
      { path: 'materials', name: 'materials', meta: { permission: 'materials:read' }, component: () => import('@/views/MaterialsView.vue') },
      {
        path: 'templates',
        name: 'templates',
        meta: { permission: 'templates:read' },
        component: () => import('@/views/ContentTemplatesView.vue'),
      },
      {
        path: 'trending',
        name: 'trending',
        meta: { permission: 'trending:read' },
        component: () => import('@/views/TrendingView.vue'),
      },
      { path: 'tasks', name: 'tasks', meta: { permission: 'tasks:read' }, component: () => import('@/views/TasksView.vue') },
      {
        path: 'reviews',
        name: 'reviews',
        meta: { permissionAny: ['review:write', 'tasks:write'] },
        component: () => import('@/views/ReviewView.vue'),
      },
      { path: 'logs', name: 'logs', meta: { permission: 'logs:read' }, component: () => import('@/views/LogsView.vue') },
      { path: 'settings', name: 'settings', meta: { permission: 'settings:write' }, component: () => import('@/views/SettingsView.vue') },
      { path: 'publish', name: 'publish', meta: { permission: 'publish:write' }, component: () => import('@/views/PublishView.vue') },
      { path: 'create', name: 'create', meta: { permission: 'publish:write' }, component: () => import('@/views/CreateView.vue') },
    ],
  },
]

const router = createRouter({
  history: createWebHistory('/app/'),
  routes,
})

router.beforeEach(async (to) => {
  const auth = useAuthStore()
  if (!to.meta.public && !auth.isLoggedIn) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }
  if (auth.isLoggedIn) {
    await auth.refreshSession()
  }
  if (to.name === 'login' && auth.isLoggedIn) {
    return { name: 'dashboard' }
  }
  const required = to.matched
    .map((record) => record.meta?.permission)
    .filter(Boolean)
    .at(-1)
  const requiredAny = to.matched
    .map((record) => record.meta?.permissionAny)
    .filter(Boolean)
    .at(-1)
  if (required && !canPerm(auth.permissions, required)) {
    return { name: 'dashboard' }
  }
  if (requiredAny && !canAnyPerm(auth.permissions, requiredAny)) {
    return { name: 'dashboard' }
  }
})

export default router
