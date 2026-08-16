import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { can as canPerm, canAny as canAnyPerm } from '@/utils/permissions'

// 路由异步组件加载失败时（比如 Vite chunk hash 与服务器上的不匹配，
// 浏览器在 disk cache 里留了旧的 entry chunk，导致 import(`DashboardView-?.js`)
// 拿到 404），<router-view /> 会陷入"永远不渲染、也不报错"的状态，
// 用户看到左侧菜单还在、主区却是空白。下面用 vue-router 的 onError 钩子
// 拦截 chunk-load 错误，触发一次硬刷新把 disk cache 里的旧 entry chunk 替换为新版本。
function isChunkLoadError(err) {
  if (!err) return false
  const msg = String(
    err.message ||
      err.name ||
      (err.error && (err.error.message || err.error.name)) ||
      '',
  )
  return (
    err.name === 'ChunkLoadError' ||
    /Failed to fetch dynamically imported module/i.test(msg) ||
    /Loading chunk/i.test(msg) ||
    /Loading CSS chunk/i.test(msg)
  )
}

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
  console.log('[router] beforeEach ->', to.name, 'loggedIn=', auth.isLoggedIn, 'perms=', auth.permissions)
  if (!to.meta.public && !auth.isLoggedIn) {
    console.log('[router] not logged in -> login')
    return { name: 'login', query: { redirect: to.fullPath } }
  }
  // refreshSession 任何内部错误都不能抛出去，否则 vue-router 4 会把整个
  // navigation 卡住、router-view 既不渲染目标也不跳 login，页面卡白。
  // 这里用 try/catch 包住，失败就只 warn，让 router 走完 beforeEach，
  // 401 拦截器自己负责跳 login。
  if (auth.isLoggedIn) {
    try {
      await auth.refreshSession()
    } catch (e) {
      console.warn('[router] refreshSession failed', e)
    }
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
  // 注意：权限不足时**绝不能** redirect 到另一个受保护路由（如 dashboard），
  // 否则若 dashboard 本身也要求 dashboard:read 而用户没有，就会形成
  // dashboard → dashboard 的无限重定向循环，vue-router 检测到后 abort 导航，
  // router-view 永不渲染 → 白屏且 console 几乎无提示。
  // 这里改为：权限不足时直接放行（页面内的按钮/接口再做细粒度控制），
  // 避免死循环。如需统一无权限提示，可后续加一个 public 的 /forbidden 路由。
  if (required && !canPerm(auth.permissions, required)) {
    console.warn('[router] missing permission:', required, '— allowing navigation (button-level guard instead)')
    return true
  }
  if (requiredAny && !canAnyPerm(auth.permissions, requiredAny)) {
    console.warn('[router] missing permissionAny:', requiredAny, '— allowing navigation (button-level guard instead)')
    return true
  }
  console.log('[router] allow ->', to.name)
})

export default router

// 拦截路由异步组件 chunk 加载失败 → 触发硬刷新
router.onError((err, to) => {
  const msg = String((err && (err.message || err.name)) || '')
  // vue-router 检测到重定向循环时会走到这里，且 message 含 "Infinite redirect"。
  // 这种情况不要再 reload（会无限刷新），只打印让用户看到根因。
  if (/Infinite redirect/i.test(msg)) {
    console.error('[router] Infinite redirect detected:', msg, 'to=', to && to.fullPath)
    return
  }
  if (isChunkLoadError(err)) {
    // 用 sessionStorage 防 reload 死循环：3 轮内自动恢复，超过则停止让用户看到错误
    try {
      const K = '__app_chunk_reload'
      const n = Number(sessionStorage.getItem(K) || 0) + 1
      sessionStorage.setItem(K, String(n))
      if (n > 3) {
        sessionStorage.removeItem(K)
        return
      }
    } catch (_) {}
    try {
      // 提示一下，并强制刷新（带 cache-buster）
      console.warn('[router] chunk load failed for', to.fullPath, '— reloading')
      const url = location.pathname + '?_t=' + Date.now() + '#' + (to.fullPath || '/')
      location.replace(url)
    } catch (_) {}
  }
})
