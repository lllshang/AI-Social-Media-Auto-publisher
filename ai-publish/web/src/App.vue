<template>
  <router-view v-if="isRouterReady" />
  <div v-else style="padding:40px;font-family:system-ui;color:#666">
    应用初始化中...（若长时间停留在此页，请截图控制台给开发）
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import router from '@/router'

console.log('[app] App.vue setup @', new Date().toISOString(), 'location=', location.href)

const isRouterReady = ref(router.isReady())

router.isReady().then(() => {
  console.log('[app] router isReady')
  isRouterReady.value = true
}).catch((e) => {
  console.error('[app] router isReady failed', e)
  isRouterReady.value = true // 不要因为这个卡死
})

onMounted(() => {
  console.log('[app] App.vue onMounted, document.body child count =', document.body.childElementCount)
})
</script>
