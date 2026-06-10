import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

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
      { path: '', name: 'dashboard', component: () => import('@/views/DashboardView.vue') },
      { path: 'accounts', name: 'accounts', component: () => import('@/views/AccountsView.vue') },
      { path: 'models', name: 'models', component: () => import('@/views/ModelsView.vue') },
      { path: 'materials', name: 'materials', component: () => import('@/views/MaterialsView.vue') },
      { path: 'tasks', name: 'tasks', component: () => import('@/views/TasksView.vue') },
      { path: 'publish', name: 'publish', component: () => import('@/views/PublishView.vue') },
    ],
  },
]

const router = createRouter({
  history: createWebHistory('/app/'),
  routes,
})

router.beforeEach((to) => {
  const auth = useAuthStore()
  if (!to.meta.public && !auth.isLoggedIn) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }
  if (to.name === 'login' && auth.isLoggedIn) {
    return { name: 'dashboard' }
  }
})

export default router
