<template>
  <el-container class="layout">
    <el-aside width="220px" class="sidebar">
      <div class="brand">AI 发布系统</div>
      <el-menu :default-active="route.path" router background-color="#0f1419" text-color="#c8d1dc" active-text-color="#1d9bf0">
        <el-menu-item index="/">概览</el-menu-item>
        <el-menu-item index="/accounts">平台账号</el-menu-item>
        <el-menu-item index="/models">AI 模型</el-menu-item>
        <el-menu-item index="/materials">素材库</el-menu-item>
        <el-menu-item index="/tasks">发布任务</el-menu-item>
        <el-menu-item index="/publish">发布向导</el-menu-item>
      </el-menu>
    </el-aside>
    <el-container>
      <el-header class="header">
        <span class="muted">当前用户：{{ auth.username }}</span>
        <el-button link type="primary" @click="logout">退出</el-button>
      </el-header>
      <el-main class="main">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

function logout() {
  auth.logout()
  router.push({ name: 'login' })
}
</script>

<style scoped>
.layout {
  min-height: 100vh;
}
.sidebar {
  background: var(--sidebar-bg);
  color: var(--sidebar-text);
}
.brand {
  padding: 20px 16px 12px;
  font-size: 18px;
  font-weight: 700;
}
.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: #fff;
  border-bottom: 1px solid #e6ecf0;
}
.main {
  padding: 20px;
}
</style>
