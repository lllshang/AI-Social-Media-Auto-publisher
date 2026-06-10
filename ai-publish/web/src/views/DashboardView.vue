<template>
  <div>
    <h2 class="page-title">概览</h2>
    <el-row :gutter="16">
      <el-col :span="6" v-for="item in cards" :key="item.label">
        <div class="page-card stat">
          <div class="muted">{{ item.label }}</div>
          <div class="value">{{ item.value }}</div>
        </div>
      </el-col>
    </el-row>
    <div class="page-card" style="margin-top: 16px">
      <h3>当前 AI 模型</h3>
      <p>文案：{{ models.text || '-' }}</p>
      <p>文生图：{{ models.image || '-' }}</p>
      <p class="muted">文生图 Key 未配置时将使用占位图，发布请上传真实图片。</p>
      <el-button type="primary" @click="$router.push('/publish')">去发布</el-button>
    </div>
  </div>
</template>

<script setup>
import { onMounted, reactive } from 'vue'
import { api } from '@/api'

const cards = reactive([
  { label: '平台账号', value: '-' },
  { label: '素材数量', value: '-' },
  { label: '发布任务', value: '-' },
  { label: '成功任务', value: '-' },
])
const models = reactive({ text: '', image: '' })

onMounted(async () => {
  const [accounts, materials, tasks, modelData] = await Promise.all([
    api.listAccounts('xhs'),
    api.listMaterials(),
    api.listTasks(),
    api.getModels(),
  ])
  cards[0].value = accounts.length
  cards[1].value = materials.length
  cards[2].value = tasks.length
  cards[3].value = tasks.filter((t) => t.status === 'success').length
  models.text = `${modelData.text.current.provider} / ${modelData.text.current.model}`
  models.image = `${modelData.image.current.provider} / ${modelData.image.current.model}`
})
</script>

<style scoped>
.stat .value {
  font-size: 28px;
  font-weight: 700;
  margin-top: 8px;
}
</style>
