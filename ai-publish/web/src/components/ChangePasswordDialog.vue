<template>
  <el-dialog v-model="visible" title="修改密码" width="420px" @closed="reset">
    <el-form label-width="90px">
      <el-form-item label="原密码">
        <el-input v-model="form.old_password" type="password" show-password />
      </el-form-item>
      <el-form-item label="新密码">
        <el-input v-model="form.new_password" type="password" show-password placeholder="至少 6 位" />
      </el-form-item>
      <el-form-item label="确认新密码">
        <el-input v-model="form.confirm_password" type="password" show-password />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button type="primary" :loading="saving" @click="submit">保存</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { api } from '@/api'

const visible = ref(false)
const saving = ref(false)
const form = reactive({
  old_password: '',
  new_password: '',
  confirm_password: '',
})

function reset() {
  form.old_password = ''
  form.new_password = ''
  form.confirm_password = ''
}

function open() {
  visible.value = true
}

async function submit() {
  if (!form.old_password || !form.new_password) {
    return ElMessage.warning('请填写完整')
  }
  if (form.new_password.length < 6) {
    return ElMessage.warning('新密码至少 6 位')
  }
  if (form.new_password !== form.confirm_password) {
    return ElMessage.warning('两次输入的新密码不一致')
  }
  saving.value = true
  try {
    await api.changePassword({
      old_password: form.old_password,
      new_password: form.new_password,
    })
    ElMessage.success('密码已修改')
    visible.value = false
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    saving.value = false
  }
}

defineExpose({ open })
</script>
