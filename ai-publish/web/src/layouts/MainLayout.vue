<template>
  <el-container class="layout">
    <el-aside width="220px" class="sidebar">
      <div class="brand">AI 发布系统</div>
      <el-menu :default-active="route.path" router background-color="#0f1419" text-color="#c8d1dc" active-text-color="#1d9bf0">
        <el-menu-item v-if="can('dashboard:read')" index="/">工作台</el-menu-item>
        <el-menu-item v-if="can('accounts:read')" index="/accounts">平台账号</el-menu-item>
        <el-menu-item v-if="can('models:read')" index="/models">AI 模型</el-menu-item>
        <el-menu-item v-if="can('materials:read')" index="/materials">素材库</el-menu-item>
        <el-menu-item v-if="can('tasks:read')" index="/tasks">发布任务</el-menu-item>
        <el-menu-item v-if="can('publish:write')" index="/publish">发布向导</el-menu-item>
        <el-menu-item v-if="can('logs:read')" index="/logs">日志中心</el-menu-item>
        <el-menu-item v-if="can('settings:write')" index="/settings">系统设置</el-menu-item>
      </el-menu>
    </el-aside>
    <el-container>
      <el-header class="header">
        <span class="muted">当前用户：{{ userDisplayLabel(auth.username, auth.roleName || 'operator') }}</span>
        <div class="header-actions">
          <el-button link type="primary" @click="openChangePassword">修改密码</el-button>
          <el-button link type="primary" @click="logout">退出</el-button>
        </div>
      </el-header>
      <el-main class="main">
        <router-view />
      </el-main>
    </el-container>
    <ChangePasswordDialog ref="changePasswordRef" />
  </el-container>
</template>

<script setup>
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import ChangePasswordDialog from '@/components/ChangePasswordDialog.vue'
import { useAuthStore } from '@/stores/auth'
import { can as canPerm, userDisplayLabel } from '@/utils/permissions'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const changePasswordRef = ref(null)

function openChangePassword() {
  changePasswordRef.value?.open()
}

function can(permission) {
  return canPerm(auth.permissions, permission)
}

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
.header-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}
</style>
