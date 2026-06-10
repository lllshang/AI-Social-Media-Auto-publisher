<template>
  <div>
    <div class="page-header">
      <h2 class="page-title">{{ draftId ? `编辑草稿 #${draftId}` : '发布向导（小红书图文）' }}</h2>
      <el-button v-if="draftId" type="danger" plain @click="removeDraft">删除草稿</el-button>
    </div>
    <el-steps :active="step" finish-status="success" align-center style="margin-bottom: 24px">
      <el-step title="主题账号" />
      <el-step title="AI 文案" />
      <el-step title="AI 封面" />
      <el-step title="素材确认" />
      <el-step title="排期提交" />
    </el-steps>

    <!-- Step 0 -->
    <div v-show="step === 0" class="page-card">
      <el-form label-width="100px">
        <el-form-item label="平台账号">
          <el-select v-model="form.account_id" placeholder="选择账号" style="width: 100%">
            <el-option v-for="a in accounts" :key="a.id" :label="`${a.account_name} (${a.status})`" :value="a.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="内容主题">
          <el-input v-model="form.topic" placeholder="如：春茶上新" />
        </el-form-item>
      </el-form>
      <el-button type="primary" :disabled="!canGoStep1" @click="step = 1">下一步：生成文案</el-button>
    </div>

    <!-- Step 1 -->
    <div v-show="step === 1" class="page-card">
      <el-form label-width="100px">
        <el-form-item label="主题">
          <el-input v-model="form.topic" disabled />
          <el-button style="margin-top: 8px" :loading="generating" @click="generateText">AI 生成文案</el-button>
        </el-form-item>
        <el-form-item label="标题">
          <el-input v-model="form.title" />
        </el-form-item>
        <el-form-item label="正文">
          <el-input v-model="form.content" type="textarea" :rows="5" />
        </el-form-item>
        <el-form-item label="标签">
          <el-input v-model="form.tagsText" placeholder="逗号分隔" />
        </el-form-item>
        <el-form-item label="封面文案">
          <el-input v-model="form.cover_text" />
        </el-form-item>
        <el-form-item label="评论引导">
          <el-input v-model="form.comment_guide" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <el-button @click="step = 0">上一步</el-button>
      <el-button :loading="saving" @click="saveDraft">保存草稿</el-button>
      <el-button type="primary" :disabled="!form.title" @click="step = 2">下一步：生成封面</el-button>
    </div>

    <!-- Step 2 -->
    <div v-show="step === 2" class="page-card">
      <p class="muted">将根据主题与封面文案生成 3:4 小红书封面图。Key 未配置时可跳过，改用手动上传。</p>
      <el-button type="primary" :loading="generatingImage" @click="generateCover">生成封面图</el-button>
      <el-button v-if="coverPreview" @click="generateCover">重新生成</el-button>
      <el-button @click="skipCover">跳过，稍后选手动素材</el-button>
      <div v-if="coverPreview" class="cover-preview">
        <el-image :src="coverPreview" fit="contain" style="max-height: 320px" />
      </div>
      <div style="margin-top: 16px">
        <el-button @click="step = 1">上一步</el-button>
        <el-button :loading="saving" @click="saveDraft">保存草稿</el-button>
        <el-button type="primary" @click="step = 3">下一步：确认素材</el-button>
      </div>
    </div>

    <!-- Step 3 -->
    <div v-show="step === 3" class="page-card">
      <el-form label-width="100px">
        <el-form-item label="图片素材">
          <el-select v-model="form.material_ids" multiple placeholder="选择图片" style="width: 100%">
            <el-option
              v-for="m in imageMaterials"
              :key="m.id"
              :label="`#${m.id} ${m.name || '未命名'} [${m.category || '默认'}]`"
              :value="m.id"
            />
          </el-select>
          <el-upload :show-file-list="false" :http-request="upload" accept="image/*" style="margin-top: 8px">
            <el-button>上传新图片</el-button>
          </el-upload>
        </el-form-item>
      </el-form>
      <el-button @click="step = 2">上一步</el-button>
      <el-button :loading="saving" @click="saveDraft">保存草稿</el-button>
      <el-button type="primary" :disabled="!form.material_ids.length" @click="step = 4">下一步：排期提交</el-button>
    </div>

    <!-- Step 4 -->
    <div v-show="step === 4" class="page-card">
      <el-form label-width="120px">
        <el-form-item label="计划发布时间">
          <el-date-picker
            v-model="form.publish_time"
            type="datetime"
            placeholder="可选，留空表示尽快发布"
            style="width: 100%"
          />
          <p class="muted">当前版本到点不会自动发布，请在任务列表手动点「执行」。</p>
        </el-form-item>
        <el-form-item label="摘要">
          <div class="summary">
            <p><strong>标题：</strong>{{ form.title }}</p>
            <p><strong>账号：</strong>{{ accountLabel }}</p>
            <p><strong>素材：</strong>{{ form.material_ids.join(', ') || '-' }}</p>
          </div>
        </el-form-item>
      </el-form>
      <el-button @click="step = 3">上一步</el-button>
      <el-button :loading="saving" @click="saveDraft">保存草稿</el-button>
      <el-button type="primary" :loading="saving" @click="submitPending">提交待发布</el-button>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { api } from '@/api'

const route = useRoute()
const router = useRouter()

const accounts = ref([])
const materials = ref([])
const step = ref(0)
const draftId = ref(null)
const generating = ref(false)
const generatingImage = ref(false)
const saving = ref(false)
const coverPreview = ref('')

const form = reactive({
  account_id: null,
  topic: '春茶上新',
  title: '',
  content: '',
  tagsText: '',
  cover_text: '',
  comment_guide: '',
  material_ids: [],
  publish_time: null,
})

const imageMaterials = computed(() => materials.value.filter((m) => m.type === 'image'))

const accountLabel = computed(() => {
  const acc = accounts.value.find((a) => a.id === form.account_id)
  return acc ? acc.account_name : '-'
})

const canGoStep1 = computed(() => Boolean(form.account_id && form.topic.trim()))

function buildTaskPayload(submit) {
  return {
    title: form.title || form.topic.trim(),
    content: form.content,
    comment_guide: form.comment_guide || null,
    topic: form.topic.trim() || null,
    cover_text: form.cover_text || null,
    wizard_step: step.value,
    tags: form.tagsText.split(',').map((s) => s.trim()).filter(Boolean),
    platform: 'xhs',
    account_id: form.account_id,
    content_type: 'note',
    material_ids: form.material_ids,
    publish_time: form.publish_time ? new Date(form.publish_time).toISOString() : null,
    submit,
  }
}

function inferWizardStep(task) {
  if (task.wizard_step != null && task.wizard_step >= 0 && task.wizard_step <= 4) {
    return task.wizard_step
  }
  if (task.material_ids?.length) return 4
  if (task.title && task.content) return 2
  if (task.title || task.topic) return 1
  return 0
}

async function loadBase() {
  const [acc, mats] = await Promise.all([api.listAccounts('xhs'), api.listMaterials()])
  accounts.value = acc
  materials.value = mats
  if (acc.length && !form.account_id) form.account_id = acc[0].id
}

async function loadDraft(id) {
  const task = await api.getTask(id)
  if (task.status !== 'draft') {
    ElMessage.warning('仅 draft 任务可在此编辑')
    router.replace('/tasks')
    return
  }
  draftId.value = task.id
  form.account_id = task.account_id
  form.topic = task.topic || task.title || form.topic
  form.title = task.title
  form.content = task.content || ''
  form.comment_guide = task.comment_guide || ''
  form.cover_text = task.cover_text || ''
  form.tagsText = (task.tags || []).join(',')
  form.material_ids = task.material_ids || []
  form.publish_time = task.publish_time ? new Date(task.publish_time) : null
  if (form.material_ids.length) {
    const first = materials.value.find((m) => m.id === form.material_ids[0])
    if (first?.url) coverPreview.value = first.url
  }
  step.value = inferWizardStep(task)
}

async function generateText() {
  generating.value = true
  try {
    const res = await api.generateText(form.topic)
    form.title = res.title
    form.content = res.content
    form.tagsText = (res.tags || []).join(',')
    form.cover_text = res.cover_text || ''
    form.comment_guide = res.comment_guide || ''
    ElMessage.success(`文案已生成 (${res.provider}/${res.model || '-'})`)
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    generating.value = false
  }
}

async function generateCover() {
  generatingImage.value = true
  try {
    const res = await api.generateImage(form.topic, 'xhs', '3:4', 1, form.cover_text || undefined)
    const mat = res.materials?.[0]
    if (!mat) throw new Error('未返回图片素材')
    if (mat.url?.includes('stub') || mat.file_path?.includes('stub')) {
      ElMessage.warning('当前为占位图，请配置文生图 Key 或改用手动上传')
    } else {
      ElMessage.success('封面已生成')
    }
    await loadBase()
    form.material_ids = [mat.id]
    coverPreview.value = mat.url
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    generatingImage.value = false
  }
}

function skipCover() {
  step.value = 3
}

async function upload({ file }) {
  const res = await api.uploadMaterial(file, {
    name: file.name.replace(/\.[^.]+$/, ''),
    category: '发布素材',
  })
  materials.value.unshift(res)
  form.material_ids = [res.id]
  coverPreview.value = res.url
  ElMessage.success('图片已上传')
}

async function persistTask(submit) {
  if (!form.account_id) return ElMessage.warning('请选择账号')
  const title = form.title || form.topic.trim()
  if (!title) return ElMessage.warning('请填写标题或主题')
  if (submit && !form.material_ids.length) return ElMessage.warning('请选择图片素材')

  saving.value = true
  try {
    let task
    const payload = buildTaskPayload(submit)
    payload.title = title
    if (draftId.value) {
      const { submit: _s, ...updatePayload } = payload
      await api.updateTask(draftId.value, updatePayload)
      task = submit ? await api.submitTask(draftId.value) : await api.getTask(draftId.value)
    } else {
      task = await api.createTask(payload)
      if (submit && task.status === 'draft') {
        task = await api.submitTask(task.id)
      }
    }
    ElMessage.success(submit ? `任务 #${task.id} 已提交待发布` : `草稿 #${task.id} 已保存`)
    if (submit) {
      router.push('/tasks')
    } else {
      draftId.value = task.id
      router.replace({ path: '/publish', query: { id: task.id } })
    }
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    saving.value = false
  }
}

function saveDraft() {
  persistTask(false)
}

function submitPending() {
  persistTask(true)
}

async function removeDraft() {
  if (!draftId.value) return
  try {
    await ElMessageBox.confirm(`确定删除草稿 #${draftId.value}？删除后不可恢复。`, '删除草稿', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })
    await api.deleteTask(draftId.value)
    ElMessage.success('草稿已删除')
    router.push('/tasks')
  } catch (e) {
    if (e !== 'cancel') ElMessage.error(e.message || '删除失败')
  }
}

onMounted(async () => {
  await loadBase()
  const id = route.query.id
  if (id) await loadDraft(Number(id))
})
</script>

<style scoped>
.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}
.page-header .page-title {
  margin: 0;
}
.muted {
  color: #888;
  font-size: 13px;
  margin: 8px 0;
}
.cover-preview {
  margin-top: 16px;
  text-align: center;
}
.summary p {
  margin: 4px 0;
}
</style>
