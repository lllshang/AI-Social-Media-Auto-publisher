<template>
  <div class="create-wizard">
    <h2>内容创作</h2>

    <!-- ========== 草稿列表（无活跃会话时显示） ========== -->
    <div v-if="showDraftList" class="step-card draft-list-card">
      <div class="draft-list-header">
        <h3>草稿箱</h3>
        <el-button type="primary" @click="startNewSession">新建创作</el-button>
      </div>
      <div v-if="drafts.length === 0" class="empty-drafts">
        <p>暂无草稿，点击"新建创作"开始</p>
      </div>
      <div v-for="draft in drafts" :key="draft.id" class="draft-item">
        <div class="draft-info">
          <span class="draft-keywords">{{ draft.keywords || '未命名草稿' }}</span>
          <el-tag size="small" :type="draft.content_type === 'video' ? '' : 'success'">
            {{ draft.content_type === 'video' ? '视频' : '图文' }}
          </el-tag>
          <el-tag v-if="draft.status === 'completed'" size="small" type="success">已完成</el-tag>
          <el-tag v-else-if="draft.status === 'drafting'" size="small" type="info">草稿中</el-tag>
          <el-tag v-else size="small" type="warning">生成中</el-tag>
          <span class="draft-time">{{ formatDraftTime(draft.updated_at) }}</span>
        </div>
        <div class="draft-actions">
          <el-button v-if="draft.status === 'completed'" size="small" type="success" @click="viewSession(draft)">查看成果</el-button>
          <el-button v-else size="small" type="primary" @click="resumeDraft(draft)">继续创作</el-button>
          <el-popconfirm title="确定删除这个草稿？" @confirm="removeDraft(draft.id)">
            <template #reference>
              <el-button size="small" type="danger">删除</el-button>
            </template>
          </el-popconfirm>
        </div>
      </div>
    </div>

    <!-- ========== 创作向导（有活跃会话时显示） ========== -->
    <template v-if="!showDraftList">
    <!-- 顶部工具条：返回草稿箱 -->
    <div class="wizard-toolbar">
      <el-button text @click="backToDrafts">
        <span>← 返回草稿箱</span>
      </el-button>
    </div>
    <!-- 步骤条 -->
    <el-steps :active="step" align-center finish-status="success" class="steps">
      <el-step title="灵感输入" />
      <el-step title="文案创作" />
      <el-step title="内容生成" />
      <el-step title="生成状态" />
    </el-steps>

    <!-- ========== Step 0: 灵感输入 ========== -->
    <div v-if="step === 0" class="step-card">
      <el-radio-group v-model="form.content_type" class="type-radio">
        <el-radio-button value="video">视频内容</el-radio-button>
        <el-radio-button value="note">图文内容</el-radio-button>
      </el-radio-group>

      <el-form label-width="100px" class="input-form">
        <el-form-item label="关键词" required>
          <el-input v-model="form.keywords" placeholder="产品卖点、核心话题、产品名称..." />
        </el-form-item>
        <el-form-item label="背景信息">
          <el-input v-model="form.background" type="textarea" :rows="3" placeholder="品牌定位、目标受众、调性..." />
        </el-form-item>
        <el-form-item label="主题/风格">
          <el-input v-model="form.theme_style" placeholder="故事化、教程类、搞笑、情感共鸣..." />
        </el-form-item>
        <el-form-item label="场景描述">
          <el-input v-model="form.scene_desc" type="textarea" :rows="2" placeholder="办公室日常、户外旅行..." />
        </el-form-item>
        <el-form-item label="目标平台">
          <el-checkbox-group v-model="form.platforms">
            <el-checkbox v-for="p in availablePlatforms" :key="p.value" :label="p.value" :value="p.value">
              {{ p.label }}
            </el-checkbox>
          </el-checkbox-group>
        </el-form-item>
      </el-form>

      <el-button type="primary" size="large" :disabled="!canStart" :loading="starting" @click="startSession">
        开始创作 →
      </el-button>
      <el-alert v-if="sessionError" type="error" :closable="true" :title="sessionError" @close="sessionError = ''" show-icon style="margin-top: 12px" />
    </div>

    <!-- ========== Step 1: 文案创作 + 润色 ========== -->
    <div v-if="step === 1" class="step-card split-layout">
      <!-- 左侧：AI 对话润色 -->
      <div class="chat-panel">
        <div class="chat-header">AI 润色对话</div>
        <div class="chat-messages" ref="chatBox">
          <div v-for="(msg, i) in chatMessages" :key="i" :class="['msg', msg.role]">
            <div class="msg-content">{{ msg.content }}</div>
          </div>
          <div v-if="generatingCopy && chatMessages.length === 0" class="msg assistant loading-bubble">
            <div class="msg-content">
              <span class="loading-spinner"></span>
              <span>AI 正在生成初稿文案...</span>
            </div>
          </div>
          <div v-else-if="generatingCopy" class="msg assistant loading-bubble">
            <div class="msg-content">
              <span class="loading-spinner"></span>
              <span>AI 正在重新生成...</span>
            </div>
          </div>
        </div>
        <!-- 快捷按钮 -->
        <div class="quick-actions">
          <el-button
            v-for="btn in quickActions"
            :key="btn.key"
            size="small"
            :disabled="isPolishing"
            @click="quickPolish(btn.key)"
          >{{ btn.label }}</el-button>
        </div>
        <div class="chat-input-row">
          <el-input v-model="polishMessage" placeholder="输入润色需求..." :disabled="isPolishing" @keyup.enter="doPolish" />
          <el-button type="primary" :disabled="!polishMessage.trim() || isPolishing" :loading="isPolishing" @click="doPolish">发送</el-button>
        </div>
      </div>

      <!-- 右侧：文案编辑区 -->
      <div class="editor-panel" v-loading="generatingCopy" element-loading-text="AI 正在生成文案，请稍候...">
        <div class="editor-header">
          <span>文案编辑</span>
          <el-button size="small" :loading="generatingCopy" @click="regenerateCopy">重新生成</el-button>
        </div>
        <el-form label-width="60px">
          <el-form-item label="标题">
            <el-input v-model="copy.title" placeholder="文章标题..." />
          </el-form-item>
          <el-form-item label="正文">
            <el-input v-model="copy.body" type="textarea" :rows="12" placeholder="正文内容..." />
          </el-form-item>
          <el-form-item label="标签">
            <el-input v-model="copy.tagsText" placeholder="#tag1 #tag2" />
          </el-form-item>
        </el-form>
        <div class="editor-actions">
          <el-button @click="step = 0">← 返回修改输入</el-button>
          <el-button type="primary" size="large" :disabled="!copy.body.trim()" @click="finalizeCopy">
            定稿文案，进入下一步 →
          </el-button>
        </div>
        <el-alert v-if="copyError" type="error" :closable="true" :title="copyError" @close="copyError = ''" show-icon style="margin-top: 12px" />
      </div>
    </div>

    <!-- ========== Step 2: 内容生成 ========== -->
    <div v-if="step === 2" class="step-card">
      <!-- 视频分支 -->
      <template v-if="form.content_type === 'video'">
        <h3>生成视频</h3>
        <el-radio-group v-model="videoGenType" class="type-radio">
          <el-radio-button value="text_to_video">文生视频</el-radio-button>
          <el-radio-button value="image_to_video">图生视频</el-radio-button>
          <el-radio-button value="simulation_human">仿真人</el-radio-button>
          <el-radio-button value="digital_human">数字人</el-radio-button>
        </el-radio-group>

        <el-form label-width="100px" class="output-form">
          <el-form-item label="视频描述">
            <el-input v-model="videoDesc" type="textarea" :rows="3" />
          </el-form-item>
          <template v-if="videoGenType === 'image_to_video'">
            <el-form-item label="驱动图片">
              <el-upload :auto-upload="false" :show-file-list="false" :on-change="onImageChange" accept="image/*">
                <el-button>选择图片</el-button>
              </el-upload>
              <img v-if="imagePreview" :src="imagePreview" class="preview-img" />
            </el-form-item>
          </template>
          <template v-if="videoGenType === 'simulation_human'">
            <el-form-item label="选择仿真人">
              <el-select v-model="selectedAvatarId" placeholder="选择已创建的仿真人" @focus="loadAvatars">
                <el-option v-for="av in avatars.filter(a => a.type === 'simulation_human')" :key="av.id" :label="av.name" :value="av.id" />
              </el-select>
            </el-form-item>
            <el-form-item label="口播词">
              <el-checkbox v-model="useCustomScript">自定义口播词（控制视频时长）</el-checkbox>
              <p class="muted">不勾选时，使用「文案创作」步骤的 AI 定稿文案作为口播内容，其长度决定配音与视频时长。勾选后可自行输入；文案越长，生成的视频越长。</p>
            </el-form-item>
            <el-form-item v-if="useCustomScript" label="自定义文案">
              <el-input
                v-model="avatarScript"
                type="textarea"
                :rows="3"
                maxlength="600"
                show-word-limit
                placeholder="输入口播文案，将按此文案合成配音（视频时长 ≈ 配音时长）"
              />
            </el-form-item>
            <el-form-item label="配音音色">
              <el-select v-model="voiceId" placeholder="选择音色" filterable @focus="loadVoices" @change="onVoiceChange">
                <el-option-group label="标准音色">
                  <el-option
                    v-for="v in voiceOptions"
                    :key="v.id"
                    :value="v.id"
                    :label="`${v.name}（${v.tag}）`"
                  >
                    <span style="float: left">{{ v.name }}（{{ v.tag }}）</span>
                    <el-button
                      link
                      type="primary"
                      size="small"
                      style="float: right; margin-left: 12px; padding: 0"
                      :loading="playingVoiceId === v.id"
                      @click.stop="previewThisVoice(v)"
                    >
                      <el-icon style="vertical-align: middle"><Headset /></el-icon>
                      {{ playingVoiceId === v.id ? '停止' : '试听' }}
                    </el-button>
                  </el-option>
                </el-option-group>
                <el-option-group v-if="myVoices.length" label="我的声音（复刻）">
                  <el-option
                    v-for="v in myVoices"
                    :key="v.id"
                    :value="v.id"
                    :label="v.status === 'succeeded' ? v.name : `${v.name}（训练中…）`"
                    :disabled="v.status !== 'succeeded'"
                  >
                    <span style="float: left">{{ v.status === 'succeeded' ? v.name : `${v.name}（训练中…）` }}</span>
                    <el-button
                      link
                      type="primary"
                      size="small"
                      style="float: right; margin-left: 12px; padding: 0"
                      :loading="playingVoiceId === v.id"
                      @click.stop="previewThisVoice(v)"
                    >
                      <el-icon style="vertical-align: middle"><Headset /></el-icon>
                      {{ playingVoiceId === v.id ? '停止' : '试听' }}
                    </el-button>
                  </el-option>
                </el-option-group>
              </el-select>
              <el-upload
                :show-file-list="false"
                :auto-upload="false"
                accept="audio/mpeg,audio/mp3,audio/wav,audio/m4a,.m4a"
                :on-change="onCloneVoiceChange"
                style="display: inline-block; margin-left: 12px"
              >
                <el-button :loading="uploadingVoice" size="small" type="primary" plain>
                  {{ uploadingVoice ? '复刻中…' : '用我的声音复刻' }}
                </el-button>
              </el-upload>
              <p class="muted">
                选「我的声音（复刻）」即用你上传的录音合成任意口播；复刻需一段 10 秒左右清晰单人中文录音（wav/mp3/m4a）。未复刻时使用上方标准音色。
              </p>
            </el-form-item>
          </template>
          <template v-if="videoGenType === 'digital_human'">
            <el-form-item label="选择数字人">
              <el-select v-model="selectedAvatarId" placeholder="选择已创建的数字人" @focus="loadAvatars">
                <el-option v-for="av in avatars.filter(a => a.type === 'digital_human')" :key="av.id" :label="av.name" :value="av.id" />
              </el-select>
              <el-alert
                v-if="selectedDigitalHuman && selectedDigitalHuman.background_image_url"
                type="success"
                :closable="false"
                style="margin-top: 8px"
                title="已配置背景图，生成时将自动使用「带背景参考图」作为驱动图（视频带背景）"
              />
              <el-alert
                v-else-if="selectedDigitalHuman"
                type="info"
                :closable="false"
                style="margin-top: 8px"
                title="该数字人未配置背景图，生成的视频使用原参考图（无背景）。可在「数字人管理」中生成背景图。"
              />
            </el-form-item>
            <el-form-item label="口播词">
              <el-checkbox v-model="useCustomScript">自定义口播词（控制视频时长）</el-checkbox>
              <p class="muted">不勾选时，使用「文案创作」步骤的 AI 定稿文案作为口播内容，其长度决定配音与视频时长。勾选后可自行输入；文案越长，生成的视频越长。</p>
            </el-form-item>
            <el-form-item v-if="useCustomScript" label="自定义文案">
              <el-input
                v-model="avatarScript"
                type="textarea"
                :rows="3"
                maxlength="600"
                show-word-limit
                placeholder="输入口播文案，将按此文案合成配音（视频时长 ≈ 配音时长）"
              />
            </el-form-item>
            <el-form-item label="配音音色">
              <el-select v-model="voiceId" placeholder="选择音色" filterable @focus="loadVoices" @change="onVoiceChange">
                <el-option-group label="标准音色">
                  <el-option
                    v-for="v in voiceOptions"
                    :key="v.id"
                    :value="v.id"
                    :label="`${v.name}（${v.tag}）`"
                  >
                    <span style="float: left">{{ v.name }}（{{ v.tag }}）</span>
                    <el-button
                      link
                      type="primary"
                      size="small"
                      style="float: right; margin-left: 12px; padding: 0"
                      :loading="playingVoiceId === v.id"
                      @click.stop="previewThisVoice(v)"
                    >
                      <el-icon style="vertical-align: middle"><Headset /></el-icon>
                      {{ playingVoiceId === v.id ? '停止' : '试听' }}
                    </el-button>
                  </el-option>
                </el-option-group>
                <el-option-group v-if="myVoices.length" label="我的声音（复刻）">
                  <el-option
                    v-for="v in myVoices"
                    :key="v.id"
                    :value="v.id"
                    :label="v.status === 'succeeded' ? v.name : `${v.name}（训练中…）`"
                    :disabled="v.status !== 'succeeded'"
                  >
                    <span style="float: left">{{ v.status === 'succeeded' ? v.name : `${v.name}（训练中…）` }}</span>
                    <el-button
                      link
                      type="primary"
                      size="small"
                      style="float: right; margin-left: 12px; padding: 0"
                      :loading="playingVoiceId === v.id"
                      @click.stop="previewThisVoice(v)"
                    >
                      <el-icon style="vertical-align: middle"><Headset /></el-icon>
                      {{ playingVoiceId === v.id ? '停止' : '试听' }}
                    </el-button>
                  </el-option>
                </el-option-group>
              </el-select>
              <el-upload
                :show-file-list="false"
                :auto-upload="false"
                accept="audio/mpeg,audio/mp3,audio/wav,audio/m4a,.m4a"
                :on-change="onCloneVoiceChange"
                style="display: inline-block; margin-left: 12px"
              >
                <el-button :loading="uploadingVoice" size="small" type="primary" plain>
                  {{ uploadingVoice ? '复刻中…' : '用我的声音复刻' }}
                </el-button>
              </el-upload>
              <p class="muted">
                选「我的声音（复刻）」即用你上传的录音合成任意口播；复刻需一段 10 秒左右清晰单人中文录音（wav/mp3/m4a）。未复刻时使用上方标准音色。
              </p>
            </el-form-item>
          </template>
          <el-form-item v-if="videoGenType !== 'digital_human' && videoGenType !== 'simulation_human'" label="时长">
            <el-input-number v-model="videoDuration" :min="1" :max="60" :step="1" style="width: 160px" />
            <span class="cost-tag" style="margin-left: 8px">预估 ¥{{ videoCostEstimate }}</span>
          </el-form-item>
          <el-alert
            v-else
            type="info"
            :closable="false"
            style="margin-bottom: 12px"
            title="数字人 / 仿真人视频时长由口播文案决定"
            description="音频时长即视频时长，无法单独设置「时长」参数。调整上方口播词（或 AI 定稿文案）的长度即可控制视频长短。"
          />
          <el-form-item label="分辨率">
            <el-select v-model="videoResolution">
              <el-option value="720p" label="720p" />
              <el-option value="1080p" label="1080p" />
              <el-option value="portrait" label="竖屏" />
            </el-select>
          </el-form-item>
        </el-form>

        <div class="step-actions">
          <el-button @click="step = 1">← 返回文案</el-button>
          <el-button type="primary" size="large" :loading="genStarting" @click="startVideoGen">
            开始生成视频 →
          </el-button>
        </div>
      </template>

      <!-- 图文分支 -->
      <template v-else>
        <h3>生成图文</h3>
        <el-form label-width="100px" class="output-form">
          <el-form-item label="封面风格">
            <el-select v-model="imageStyle" placeholder="选择风格">
              <el-option v-for="s in imageStyles" :key="s" :label="s" :value="s" />
            </el-select>
          </el-form-item>
          <el-form-item label="品牌色">
            <el-input v-model="brandColor" placeholder="#FF6B35" />
          </el-form-item>
          <el-form-item label="品牌说明">
            <el-input v-model="brandHint" placeholder="品牌简短描述" />
          </el-form-item>
        </el-form>

        <div class="step-actions">
          <el-button type="primary" :loading="genStarting" @click="startImageGen(1)">生成封面</el-button>
          <span class="cost-tag" style="margin-left: 8px">预估 ¥{{ imageCostEstimate }}</span>
        </div>

        <el-divider />

        <h4>生成配图</h4>
        <el-form label-width="100px" class="output-form">
          <el-form-item label="配图风格">
            <el-select v-model="imageStyle" placeholder="选择风格">
              <el-option v-for="s in imageStyles" :key="s" :label="s" :value="s" />
            </el-select>
          </el-form-item>
          <el-form-item label="数量">
            <el-select v-model="imageCount">
              <el-option v-for="n in [1,2,3,4,6,9]" :key="n" :label="`${n}张`" :value="n" />
            </el-select>
            <span class="cost-tag" style="margin-left: 8px">预估 ¥{{ multiImageCostEstimate }}</span>
          </el-form-item>
        </el-form>

        <div class="step-actions">
          <el-button @click="step = 1">← 返回文案</el-button>
          <el-button type="primary" size="large" :loading="genStarting" @click="startImageGen(imageCount)">
            生成配图，进入状态页 →
          </el-button>
        </div>
      </template>
    </div>

    <el-alert v-if="genError" type="error" :closable="true" :title="genError" @close="genError = ''" show-icon style="margin-top: 12px" />

    <!-- ========== Step 3: 生成状态页 ========== -->
    <div v-if="step === 3" class="step-card">
      <h3>内容生成状态</h3>

      <!-- 进行中的任务 -->
      <div v-if="activeTask" class="progress-card">
        <div class="progress-header">
          <span>{{ genTypeLabel(activeTask.gen_type) }} — {{ activeTask.provider || '准备中...' }}</span>
          <el-tag :type="activeTask.status === 'completed' ? 'success' : activeTask.status === 'failed' ? 'danger' : 'warning'">
            {{ activeTask.status === 'pending' ? '队列中' : activeTask.status === 'running' ? '生成中' : activeTask.status === 'completed' ? '已完成' : '失败' }}
          </el-tag>
        </div>
        <el-progress
          v-if="activeTask.status !== 'failed'"
          :percentage="displayProgress"
          :stroke-width="16"
          :text-inside="true"
          :status="activeTask.status === 'completed' ? 'success' : activeTask.status === 'running' ? '' : undefined"
        />
        <div v-if="activeTask.status === 'failed'" class="error-msg">
          {{ activeTask.error_message }}
        </div>
        <div v-if="actualCostSeconds !== null" class="progress-cost">
          实际生成耗时：{{ actualCostSeconds }} 秒
        </div>
        <div class="progress-hint">
          {{
            activeTask.status === 'completed'
              ? '生成完成'
              : activeTask.status === 'pending'
                ? '排队中，等待生成槽位...'
                : activeTask.progress <= 5
                  ? '排队中，等待生成槽位...'
                  : displayProgress < 30
                    ? '正在调用 AI 生成服务...'
                    : displayProgress >= 95
                      ? (isHardStalled
                          ? '生成较慢，请稍候或刷新页面查看素材库是否已生成'
                          : progressStalled ? '生成即将完成，请稍候...' : '即将完成...')
                      : `预计还需 ${remainingMinutes} 分钟...`
          }}
        </div>
      </div>

      <el-divider />

      <!-- 生成历史 -->
      <h4>生成历史</h4>
      <div v-if="generationTasks.length === 0" class="empty">暂无生成记录</div>
      <div v-for="gen in sortedGenerations" :key="gen.id" class="gen-item">
        <div class="gen-item-head">
          <span>{{ genTypeLabel(gen.gen_type) }}</span>
          <el-tooltip v-if="gen.status === 'failed' && gen.error_message" :content="gen.error_message" placement="top" effect="light">
            <el-tag size="small" type="danger" style="cursor: help;">
              失败
            </el-tag>
          </el-tooltip>
          <el-tag v-else size="small" :type="gen.status === 'completed' ? 'success' : gen.status === 'failed' ? 'danger' : gen.status === 'running' ? 'warning' : 'info'">
            {{ gen.status === 'pending' ? '队列中' : gen.status === 'running' ? `${gen.progress}%` : gen.status === 'completed' ? '已完成' : '失败' }}
          </el-tag>
          <span class="gen-time">{{ formatTime(gen.created_at) }}</span>
          <span v-if="gen.status === 'completed' && gen.completed_at" class="gen-cost">
            耗时 {{ genCostSeconds(gen) }} 秒
          </span>
          <div class="gen-actions">
            <el-button v-if="gen.status === 'completed' && gen.result?.material_ids?.length" size="small" :loading="gen._previewing" @click="previewGeneration(gen)">
              {{ gen._previewOpen ? '收起' : '预览' }}
            </el-button>
            <el-button size="small" @click="regenerateWith(gen)">重新生成</el-button>
            <el-button
              v-if="gen.status === 'completed' && gen.result?.material_ids?.length"
              :type="isSelected(gen) ? 'primary' : 'default'"
              size="small"
              @click="toggleSelect(gen)"
            >{{ isSelected(gen) ? '已选定' : '选定' }}</el-button>
          </div>
        </div>

        <!-- 内联预览区 -->
        <div v-if="gen._previewOpen && gen.status === 'completed'" class="gen-preview">
          <template v-for="mid in (gen.result?.material_ids || [])" :key="mid">
            <div v-if="materialCache[mid]" class="preview-block">
              <div class="preview-name">{{ materialCache[mid].name || ('素材 #' + mid) }}</div>
              <video v-if="materialCache[mid].type === 'video' && materialCache[mid].url" :src="materialCache[mid].url" controls class="preview-media" />
              <img v-else-if="materialCache[mid].type === 'image' && materialCache[mid].url" :src="materialCache[mid].url" class="preview-media" alt="预览" />
              <a v-else-if="materialCache[mid].url" :href="materialCache[mid].url" target="_blank" class="preview-link">打开素材</a>
              <span v-else class="preview-empty">无可用预览</span>
            </div>
          </template>
        </div>
      </div>

      <div class="step-actions">
        <el-button @click="goBackToGen">← 返回生成</el-button>
        <el-button type="primary" size="large" :loading="completing" :disabled="selectedGenIds.length === 0" @click="finishCreation">
          选定产出 → 完成创作
        </el-button>
      </div>
      <el-alert v-if="statusError" type="error" :closable="true" :title="statusError" @close="statusError = ''" show-icon style="margin-top: 12px" />
    </div>
    </template>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { onBeforeRouteLeave, useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Headset } from '@element-plus/icons-vue'
import { api } from '@/api'

const route = useRoute()
const router = useRouter()

// ── 常量 ──────────────────────────────────────────────────────
const availablePlatforms = [
  { value: 'douyin', label: '抖音' },
  { value: 'bilibili', label: 'B站' },
  { value: 'xhs', label: '小红书' },
  { value: 'kuaishou', label: '快手' },
  { value: 'channels', label: '视频号' },
]

const imageStyles = ['科技感', '简约', '清新', '复古', '卡通风', '高级感', '美食风', '潮流']
const quickActions = [
  { key: 'shorten', label: '缩短' },
  { key: 'expand', label: '扩写' },
  { key: 'humorous', label: '变幽默' },
  { key: 'add_emoji', label: '加 Emoji' },
  { key: 'formal', label: '变正式' },
  { key: 'bilibili_style', label: 'B站风格' },
  { key: 'xiaohongshu_style', label: '小红书风格' },
  { key: 'douyin_style', label: '抖音风格' },
]

// ── 草稿列表 ──────────────────────────────────────────────────
const showDraftList = ref(false)
const drafts = ref([])

async function loadDrafts() {
  try {
    const res = await api.getSessions({ page: 1, page_size: 20 })
    drafts.value = res.items || []
  } catch { drafts.value = [] }
}

function formatDraftTime(ts) {
  if (!ts) return ''
  const d = new Date(ts)
  const now = new Date()
  const diffMs = now - d
  const diffMin = Math.floor(diffMs / 60000)
  if (diffMin < 1) return '刚刚'
  if (diffMin < 60) return `${diffMin}分钟前`
  const diffH = Math.floor(diffMin / 60)
  if (diffH < 24) return `${diffH}小时前`
  const diffD = Math.floor(diffH / 24)
  if (diffD < 7) return `${diffD}天前`
  return d.toLocaleDateString()
}

function startNewSession() {
  showDraftList.value = false
  step.value = 0
  sessionId.value = null
  resetForm()
}

function backToDrafts() {
  showDraftList.value = true
  loadDrafts()
}

async function removeDraft(id) {
  try {
    await api.deleteSession(id)
    ElMessage.success('草稿已删除')
    loadDrafts()
  } catch (e) {
    ElMessage.error(e.message || '删除失败')
  }
}

async function viewSession(draft) {
  console.log('[viewSession] start, draft.id=', draft?.id, 'status=', draft?.status)
  sessionId.value = draft.id
  showDraftList.value = false
  step.value = 3
  // 恢复基础信息
  let loadOk = false
  try {
    const res = await api.getSession(draft.id)
    console.log('[viewSession] getSession OK', res)
    const s = res.session || res
    form.keywords = s.keywords || ''
    form.background = s.background || ''
    form.content_type = s.content_type || 'video'
    loadAvatars()
    loadOk = true
  } catch (e) {
    console.error('[viewSession] getSession failed:', e)
  }
  console.log('[viewSession] about to loadGenerations, sessionId=', sessionId.value, 'step=', step.value)
  // 注：历史原本调的是不存在的 refreshTasks()，导致整段被中断。
  // 改为 loadGenerations + startPolling，与 resumeDraft 保持一致。
  // 不论 getSession 成功与否都拉历史——草稿箱里"已完成"的草稿用户期望看到历史。
  try {
    await loadGenerations()
    console.log('[viewSession] loadGenerations done, count=', generationTasks.value.length)
  } catch (e) {
    console.error('[viewSession] loadGenerations failed:', e)
  }
  startPolling()
  if (loadOk) {
    ElMessage.success('已加载创作成果')
  }
}

function resetForm() {
  form.content_type = 'video'
  form.keywords = ''
  form.background = ''
  form.theme_style = ''
  form.scene_desc = ''
  form.platforms = []
  copy.title = ''
  copy.body = ''
  copy.tagsText = ''
  chatMessages.value = []
  polishMessage.value = ''
  videoGenType.value = 'text_to_video'
  videoDesc.value = ''
  videoDuration.value = 5
  videoResolution.value = '720p'
  imagePreview.value = ''
  imageFile.value = null
  selectedAvatarId.value = null
  avatarScript.value = ''
  useCustomScript.value = false
  avatars.value = []
  imageStyle.value = '科技感'
  brandColor.value = ''
  brandHint.value = ''
  imageCount.value = 4
  generationTasks.value = []
  selectedGenIds.value = []
  starting.value = false
}

async function resumeDraft(draft) {
  console.log('[resumeDraft] start, draft.id=', draft?.id, 'status=', draft?.status, 'draft_data=', draft?.draft_data)
  sessionId.value = draft.id
  showDraftList.value = false

  // 恢复 Step 0 表单
  form.content_type = draft.content_type || 'video'
  form.keywords = draft.keywords || ''
  form.background = draft.background || ''
  form.theme_style = draft.theme_style || ''
  form.scene_desc = draft.scene_desc || ''
  form.platforms = draft.platforms || []

  // 恢复文案
  if (draft.final_copy) {
    copy.title = draft.final_copy.title || ''
    copy.body = draft.final_copy.body || ''
    copy.tagsText = (draft.final_copy.tags || []).join(' ')
  }

  // 恢复 draft_data
  const dd = draft.draft_data
  if (dd) {
    // 恢复 Step 2 参数
    if (dd.video_params) {
      videoGenType.value = dd.video_params.genType || 'text_to_video'
      videoDesc.value = dd.video_params.desc || ''
      videoDuration.value = dd.video_params.duration || 5
      videoResolution.value = dd.video_params.resolution || '720p'
    }
    if (dd.image_params) {
      imageStyle.value = dd.image_params.style || '科技感'
      brandColor.value = dd.image_params.brandColor || ''
      brandHint.value = dd.image_params.brandHint || ''
      if (dd.image_params.count) imageCount.value = dd.image_params.count
    }

    // 恢复步骤
    step.value = dd.step || 0
  } else {
    // 无 draft_data 时，根据状态推断
    if (draft.status === 'generating') {
      step.value = 3
    } else if (draft.final_copy && draft.final_copy.body) {
      step.value = 1
    } else {
      step.value = 0
    }
  }

  // 兜底：如果这条草稿有"生成中"或"已完成"任务（用户从生成状态步骤被切走），
  // 强制跳到"生成状态"步骤去看历史；否则用户可能看到的是步骤 2 内容生成，
  // 完全没有"生成历史"卡片，会以为历史丢了。
  const hasAnyGen = (draft.generation_count && draft.generation_count > 0)
    || draft.status === 'generating'
    || draft.status === 'completed'
    || draft.status === 'failed'
  if (hasAnyGen && step.value < 3) {
    console.log('[resumeDraft] 强制跳到 step=3，因为有历史/未完成任务')
    step.value = 3
  }
  console.log('[resumeDraft] after restore, step=', step.value, 'sessionId=', sessionId.value)

  // 如果恢复后已经进入"生成状态"（step=3），必须把生成历史拉回来，并继续轮询，
  // 否则会看到"暂无生成记录"。
  // 注意：把 loadGenerations 放到 try-catch 外面，不依赖 getSession 成功。
  if (step.value === 3) {
    try {
      await loadGenerations()
      console.log('[resumeDraft] loadGenerations done, count=', generationTasks.value.length)
    } catch (e) {
      console.error('[resumeDraft] loadGenerations failed:', e)
    }
    startPolling()
  }

  ElMessage.success('已恢复草稿，继续创作')
}

// ── 状态 ──────────────────────────────────────────────────────
const step = ref(0)
const sessionError = ref('')
const copyError = ref('')
const genError = ref('')
const statusError = ref('')

// 切换步骤时清除对应错误
watch(step, (newStep) => {
  if (newStep !== 1) copyError.value = ''
  if (newStep !== 2) genError.value = ''
  if (newStep !== 3) statusError.value = ''
  if (newStep !== 0) sessionError.value = ''
})
const sessionId = ref(null)
const starting = ref(false)
const generatingCopy = ref(false)
const isPolishing = ref(false)
const genStarting = ref(false)
const completing = ref(false)

const form = reactive({
  content_type: 'video',
  keywords: '',
  background: '',
  theme_style: '',
  scene_desc: '',
  platforms: [],
})

const copy = reactive({ title: '', body: '', tagsText: '' })
const chatMessages = ref([])
const polishMessage = ref('')
const chatBox = ref(null)

const videoGenType = ref('text_to_video')
const videoDesc = ref('')
const videoDuration = ref(5)
const videoResolution = ref('720p')
const imagePreview = ref('')
const imageFile = ref(null)
const selectedAvatarId = ref(null)
const avatars = ref([])
const avatarScript = ref('') // 仿真人/数字人口播词（可选，覆盖视频描述）
const useCustomScript = ref(false) // 是否使用自定义口播词（否则用 AI 定稿文案，其长度决定视频时长）

// ====== TTS 配音音色 ======
const voiceId = ref(loadPickedVoice() || 'zh-CN-XiaoxiaoNeural') // 默认晓晓（女·温柔）；若用户曾手动选过，恢复用户的偏好
const voiceOptions = ref([])                  // 拉取到的标准音色下拉
const myVoices = ref([])                       // 我的声音（复刻音色），id = clone:<voice_type>
const uploadedVoice = ref(null)               // 兼容旧逻辑保留字段（不再使用）
const playingVoiceId = ref('')                // 当前正在试听的音色 id（高亮用）
const previewAudio = new Audio()              // 复用的音频播放器
const previewText = '这是一段用于试听音色效果的示例口播，希望声音清晰自然。'
const uploadingVoice = ref(false)            // 复刻中

// 关键修复：用户是否手动选过音色（持久化）。
// 用 localStorage 持久化，既跨刷新生效，也能避免 Vite/esbuild 把 set-only 的 ref 当死代码消除掉。
// 标志为 '1' 即视为「用户已显式选过音色」，autoPickVoiceByAvatar 不再覆盖。
const VOICE_PICKED_KEY = 'createView.userPickedVoice'
function markVoicePicked() {
  try { localStorage.setItem(VOICE_PICKED_KEY, '1') } catch (e) { /* noop */ }
}
function isVoicePicked() {
  try { return localStorage.getItem(VOICE_PICKED_KEY) === '1' } catch (e) { return false }
}
function loadPickedVoice() {
  try {
    const v = localStorage.getItem('createView.lastPickedVoice')
    return v || null
  } catch (e) { return null }
}
function savePickedVoice(v) {
  try { localStorage.setItem('createView.lastPickedVoice', v) } catch (e) { /* noop */ }
}

async function loadVoices() {
  if (!voiceOptions.value.length) {
    try {
      const res = await api.listVoices()
      voiceOptions.value = res?.voices || res || []
    } catch (e) {
      ElMessage.warning('标准音色加载失败，使用默认音色。')
    }
  }
  // 每次聚焦都刷新复刻音色状态（训练完成后会出现在列表）
  try {
    const res = await api.listVoiceClones()
    const items = res?.items || []
    myVoices.value = items.map(v => ({
      id: `clone:${v.voice_type}`,
      name: v.name,
      status: v.status,
    }))
  } catch (e) {
    // 复刻音色列表加载失败不阻塞主流程
  }
}

async function onCloneVoiceChange(file) {
  if (!file?.raw) return
  // 前端先用 Web Audio API 测时长，腾讯云 VRS 一句话声音复刻硬性要求 5-15s，
  // 超过 15s 必然被服务端拒（AudioDurationExceedsLimit）。
  // 提前给用户清晰提示，避免无效请求。
  let durationSec = 0
  try {
    durationSec = await readAudioDurationSec(file.raw)
  } catch (e) {
    // 浏览器解码失败时不强阻止，仍交给后端处理
    console.warn('[clone-voice] 读取音频时长失败:', e)
  }
  if (durationSec > 0 && durationSec > 15) {
    ElMessage.error(
      `录音时长 ${durationSec.toFixed(1)}s，超过腾讯云 VRS 复刻上限 15 秒，请裁剪到 5-15 秒后重新上传。`,
    )
    uploadingVoice.value = false
    return
  }
  if (durationSec > 0 && durationSec < 5) {
    ElMessage.warning(
      `录音时长仅 ${durationSec.toFixed(1)}s，建议 5-15 秒以获得更好效果。仍将继续提交。`,
    )
  }
  uploadingVoice.value = true
  try {
    // 用文件名推断性别：含"女"→女，含"男"→男，默认男
    const fname = (file.name || '').toLowerCase()
    const gender = fname.includes('女') ? 2 : fname.includes('男') ? 1 : 1
    const res = await api.createVoiceClone(file.raw, {
      name: file.name?.replace(/\.[^.]+$/, '') || '我的声音',
      voice_gender: gender,
    })
    ElMessage.success('已创建复刻任务，训练通常需几分钟，完成后在「我的声音」中可选（下拉可刷新状态）。')
    loadVoices()
    if (res?.id) pollCloneStatus(res.id)
  } catch (e) {
    ElMessage.error('复刻失败：' + (e.response?.data?.detail || e.message || '未知错误'))
  } finally {
    uploadingVoice.value = false
  }
}

// 用 Web Audio API 解码音频获取时长（秒），失败抛错
function readAudioDurationSec(file) {
  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(file)
    const audio = new Audio()
    audio.preload = 'metadata'
    audio.onloadedmetadata = () => {
      URL.revokeObjectURL(url)
      if (!isFinite(audio.duration) || audio.duration <= 0) {
        reject(new Error('invalid duration'))
        return
      }
      resolve(audio.duration)
    }
    audio.onerror = () => {
      URL.revokeObjectURL(url)
      reject(audio.error || new Error('audio decode failed'))
    }
    audio.src = url
  })
}

let _cloneTimer = null
async function pollCloneStatus(taskId) {
  if (_cloneTimer) clearInterval(_cloneTimer)
  _cloneTimer = setInterval(async () => {
    try {
      const st = await api.getVoiceCloneStatus(taskId)
      if (st?.status === 'succeeded') {
        clearInterval(_cloneTimer)
        ElMessage.success('声音复刻完成，已可用！')
        loadVoices()
      } else if (st?.status === 'failed') {
        clearInterval(_cloneTimer)
        ElMessage.error('声音复刻失败：' + (st.error_message || '未知'))
      }
    } catch (e) {
      // 忽略轮询错误
    }
  }, 8000)
}

const imageStyle = ref('科技感')
const brandColor = ref('')
const brandHint = ref('')
const imageCount = ref(4)

// 费用预估（以常见默认价格估算）
const videoCostEstimate = computed(() => (videoDuration.value * 0.5).toFixed(2))
const imageCostEstimate = computed(() => '0.02')
const multiImageCostEstimate = computed(() => (imageCount.value * 0.02).toFixed(2))

const generationTasks = ref([])
const selectedGenIds = ref([])
let pollTimer = null

// ── 计算属性 ──────────────────────────────────────────────────
const canStart = computed(() => form.keywords.trim())

const activeTask = computed(() =>
  generationTasks.value.find(t => ['pending', 'running', 'failed', 'completed'].includes(t.status)) || null
)

// 实际生成耗时（秒）：从 API 调用（任务创建）到视频产物生成完成（completed_at）。
// 仅当任务已完成（拿到 completed_at）才展示，进行中/失败不展示。
const actualCostSeconds = computed(() => {
  const t = activeTask.value
  if (!t || t.status !== 'completed') return null
  const start = new Date(t.created_at).getTime()
  const end = t.completed_at ? new Date(t.completed_at).getTime() : null
  if (!end || isNaN(end) || end < start) return null
  return Math.max(0, Math.round((end - start) / 1000))
})

// 显示进度：后端 progress 优先级最高；如果卡在低值但任务在 running，前端按 elapsed
// 时间在 [20%, 95%] 区间线性增长，避免 UI 一直停在 20%。
// 后端一旦推 100% 或 completed 状态会立即接管。
const nowTick = ref(Date.now())
let progressTicker = null

// 视频/图片生成大概耗时估计（毫秒）。用于前端把 20%→95% 线性铺到这段时间。
const ESTIMATED_VIDEO_MS = 90 * 1000       // 90 秒
const ESTIMATED_IMAGE_MS = 30 * 1000       // 30 秒

const displayProgress = computed(() => {
  const t = activeTask.value
  if (!t) return 0
  if (t.status === 'completed') return 100
  if (t.status === 'failed') return t.progress || 0
  // 后端推到 95% 以上就以它为准（避免 100% 假完成被前端覆盖）
  if (t.progress >= 95) return Math.min(99, t.progress)
  // 硬卡：超过预估时间 + 90s 仍 running，强制封顶 95%，不再让进度卡在中间值
  if (isHardStalled.value) return stalledProgress
  // 凡是后端已经"进入生成阶段"（status=running 且 progress >= 3），无论
  // progress 卡在 3% 还是 20%，前端都按 elapsed 时间在 [20%, 95%] 平滑铺
  if (t.status === 'running' && t.progress >= 3) {
    const start = new Date(t.created_at).getTime()
    const totalMs = t.gen_type && t.gen_type.includes('video')
      ? ESTIMATED_VIDEO_MS : ESTIMATED_IMAGE_MS
    const elapsed = nowTick.value - start
    const fraction = Math.min(1.0, Math.max(0, elapsed / totalMs))
    return Math.floor(20 + (95 - 20) * fraction)
  }
  return t.progress || 0
})

// 生成是否已超过预估时间但仍未完成（用于显示"即将完成"提示，避免卡在中间值）
const progressStalled = computed(() => {
  const t = activeTask.value
  if (!t || t.status !== 'running') return false
  const start = new Date(t.created_at).getTime()
  const totalMs = t.gen_type && t.gen_type.includes('video')
    ? ESTIMATED_VIDEO_MS : ESTIMATED_IMAGE_MS
  return (nowTick.value - start) > totalMs
})

// 生成超过预估时间 + 90 秒仍未完成/失败，说明后端可能卡死或前端数据滞后，
// 此时强制把进度封顶 95% 并提示"生成较慢"，避免永远卡在 91% 等。
const isHardStalled = computed(() => {
  const t = activeTask.value
  if (!t || t.status !== 'running') return false
  const start = new Date(t.created_at).getTime()
  const totalMs = (t.gen_type && t.gen_type.includes('video')
    ? ESTIMATED_VIDEO_MS : ESTIMATED_IMAGE_MS)
  return (nowTick.value - start) > totalMs + 90000
})

// 硬卡时使用的固定百分比
const stalledProgress = 95

const remainingMinutes = computed(() => {
  const t = activeTask.value
  if (!t) return 0
  // 按当前 displayProgress 反推总剩余时间（displayProgress 范围 20~95）
  const dp = displayProgress.value
  if (dp >= 95) return 0
  const totalMs = t.gen_type && t.gen_type.includes('video')
    ? ESTIMATED_VIDEO_MS : ESTIMATED_IMAGE_MS
  // 把 [20%, 95%] 映射到 [0, totalMs] 剩余时间
  const remainMs = Math.max(0, ((95 - dp) / (95 - 20)) * totalMs)
  if (remainMs < 30 * 1000) return 1   // 不足 30 秒也显示"1 分钟内"
  return Math.max(1, Math.ceil(remainMs / 60000))
})

const sortedGenerations = computed(() =>
  [...generationTasks.value].sort((a, b) => new Date(b.created_at || 0) - new Date(a.created_at || 0))
)

// ── 辅助 ──────────────────────────────────────────────────────
function genTypeLabel(type) {
  const map = {
    text_to_video: '文生视频', image_to_video: '图生视频',
    simulation_human: '仿真人', digital_human: '数字人',
    cover: '封面图', images: '配图',
  }
  return map[type] || type
}

function formatTime(ts) {
  if (!ts) return ''
  return new Date(ts).toLocaleTimeString()
}

// 实际生成耗时（秒）：任务创建 → 完成，用于生成历史展示
function genCostSeconds(gen) {
  if (!gen.completed_at) return '-'
  const start = new Date(gen.created_at).getTime()
  const end = new Date(gen.completed_at).getTime()
  if (isNaN(end) || end < start) return '-'
  return Math.max(0, Math.round((end - start) / 1000))
}

function isSelected(gen) {
  return generationTasks.value
    .filter(g => selectedGenIds.value.includes(g.id))
    .includes(gen)
}

function toggleSelect(gen) {
  const idx = selectedGenIds.value.indexOf(gen.id)
  if (idx > -1) selectedGenIds.value.splice(idx, 1)
  else selectedGenIds.value.push(gen.id)
}

// ── 收集草稿数据 ──────────────────────────────────────────────
function collectDraftData() {
  return {
    step: step.value,
    form: { ...form },
    copy_data: { title: copy.title, body: copy.body, tagsText: copy.tagsText },
    video_params: {
      genType: videoGenType.value,
      desc: videoDesc.value,
      duration: videoDuration.value,
      resolution: videoResolution.value,
    },
    image_params: {
      style: imageStyle.value,
      brandColor: brandColor.value,
      brandHint: brandHint.value,
      count: imageCount.value,
    },
  }
}

// ── 保存草稿（带防重入） ──────────────────────────────────────
let savingDraft = false
async function doSaveDraft() {
  if (!sessionId.value || savingDraft) return
  savingDraft = true
  try {
    await api.saveDraft(sessionId.value, collectDraftData())
  } catch {
    // 静默失败，不影响用户操作
  } finally {
    savingDraft = false
  }
}

// ── Step 0: 开始创作 ──────────────────────────────────────────
async function startSession() {
  starting.value = true
  sessionError.value = ''
  try {
    const session = await api.createSession({
      content_type: form.content_type,
      keywords: form.keywords,
      background: form.background || null,
      theme_style: form.theme_style || null,
      scene_desc: form.scene_desc || null,
      platforms: form.platforms.length ? form.platforms : ['douyin'],
    })
    sessionId.value = session.id
    step.value = 1
    showDraftList.value = false
    // 自动生成初始文案
    await generateInitialCopy()
  } catch (e) {
    sessionError.value = e.message || '创建失败'
  } finally {
    starting.value = false
  }
}

// ── Step 1: 文案 ──────────────────────────────────────────────
async function generateInitialCopy() {
  generatingCopy.value = true
  copyError.value = ''
  try {
    const res = await api.generateCopy(sessionId.value)
    copy.title = res.title || ''
    copy.body = res.body || ''
    copy.tagsText = (res.tags || []).join(' ')
    chatMessages.value = [{ role: 'assistant', content: `已根据你的输入生成初稿：「${copy.title}」` }]
  } catch (e) {
    copyError.value = e.message || '生成文案失败'
  } finally {
    generatingCopy.value = false
  }
}

async function regenerateCopy() {
  await generateInitialCopy()
}

async function doPolish() {
  if (!polishMessage.value.trim()) return
  isPolishing.value = true
  copyError.value = ''
  const msg = polishMessage.value.trim()
  polishMessage.value = ''
  chatMessages.value.push({ role: 'user', content: msg })

  try {
    const res = await api.polishCopy(sessionId.value, { message: msg })
    copy.title = res.title || ''
    copy.body = res.body || ''
    copy.tagsText = (res.tags || []).join(' ')
    chatMessages.value.push({ role: 'assistant', content: `已根据「${msg}」润色文案` })
  } catch (e) {
    copyError.value = e.message || '润色失败'
    chatMessages.value.push({ role: 'assistant', content: `润色失败：${e.message || '未知错误'}` })
  } finally {
    isPolishing.value = false
    nextTick(() => {
      if (chatBox.value) chatBox.value.scrollTop = chatBox.value.scrollHeight
    })
  }
}

async function quickPolish(action) {
  isPolishing.value = true
  copyError.value = ''
  const label = quickActions.find(a => a.key === action)?.label || action
  chatMessages.value.push({ role: 'user', content: `[${label}]` })

  try {
    const res = await api.polishCopy(sessionId.value, { quick_action: action })
    copy.title = res.title || ''
    copy.body = res.body || ''
    copy.tagsText = (res.tags || []).join(' ')
    chatMessages.value.push({ role: 'assistant', content: `已按「${label}」风格润色` })
  } catch (e) {
    copyError.value = e.message || '润色失败'
  } finally {
    isPolishing.value = false
    nextTick(() => {
      if (chatBox.value) chatBox.value.scrollTop = chatBox.value.scrollHeight
    })
  }
}

// 内联编辑防抖保存
let saveTimer = null
watch([() => copy.title, () => copy.body, () => copy.tagsText], () => {
  if (!sessionId.value) return
  clearTimeout(saveTimer)
  saveTimer = setTimeout(() => {
    api.updateCopy(sessionId.value, {
      title: copy.title,
      body: copy.body,
      tags: copy.tagsText.split(/\s+/).filter(Boolean),
    }).catch(() => {})
  }, 1500)
})

function finalizeCopy() {
  // 定稿保存
  api.updateCopy(sessionId.value, {
    title: copy.title,
    body: copy.body,
    tags: copy.tagsText.split(/\s+/).filter(Boolean),
  }).catch(() => {})
  // 初始化生成描述
  if (form.content_type === 'video') {
    videoDesc.value = `${copy.title} ${copy.body}`.slice(0, 200)
  }
  step.value = 2
}

// ── Step 2: 生成 ──────────────────────────────────────────────
function onImageChange(file) {
  imageFile.value = file.raw
  imagePreview.value = URL.createObjectURL(file.raw)
}

async function loadAvatars() {
  try {
    avatars.value = await api.listAvatars()
    // 仅在「用户尚未手动选过音色」且「当前还没有有效音色」时，
    // 按数字人性别匹配一次默认音色。绝不在每次加载时覆盖用户已选音色。
    if (!isVoicePicked() && !voiceId.value) {
      if (selectedAvatarId.value) autoPickVoiceByAvatar()
    }
  } catch { /* ignore */ }
}

// 根据当前所选数字人的 gender 自动匹配默认音色:
// 男→云希(沉稳, zh-CN-YunxiNeural), 女→晓晓(温柔, zh-CN-XiaoxiaoNeural)
// 只有在用户「从未手动选择」时才自动匹配，且调用方需保证 voiceId 为空。
function autoPickVoiceByAvatar() {
  // 双保险：用户已手动选过音色(localStorage 持久化)则一律不覆盖。
  if (isVoicePicked()) {
    console.log('[voice] autoPick skip: 用户已手动选过音色(picked=true), 尊重 voiceId=', voiceId.value)
    return
  }
  if (voiceId.value) return  // voiceId 已有值（含用户选择或初始化）则不覆盖
  if (voiceId.value?.startsWith('clone:')) return  // 已选复刻音色时不覆盖
  const a = avatars.value.find(x => x.id === selectedAvatarId.value)
  if (!a) return
  const before = voiceId.value
  if (a.gender === 'male') voiceId.value = 'zh-CN-YunxiNeural'
  else if (a.gender === 'female') voiceId.value = 'zh-CN-XiaoxiaoNeural'
  if (before !== voiceId.value) {
    console.log('[voice] autoPick OVERRIDE:', before, '->', voiceId.value, '(avatar=', a.name, 'gender=', a.gender, ')')
  }
}

// 用户手动选了音色:同时写 localStorage(守卫标志 + 最后一次选择,便于下次刷新恢复)
function onVoiceChange(val) {
  console.log('[voice] 用户手动选音色:', val, '| 被覆盖前的守卫状态 picked=before:', isVoicePicked())
  markVoicePicked()
  if (val) savePickedVoice(val)
  console.log('[voice] 守卫已 set, picked=after:', isVoicePicked())
}

// 试听某个音色：调用后端 /api/voices/preview 实时合成一段，浏览器直接播放。
// 用于确认每个音色（尤其 85 号那种「和别的音色不一样」的情况）是不是本身就这么发声。
async function previewThisVoice(v) {
  const id = v?.id || v
  if (!id) return
  // 点同一个则停止
  if (playingVoiceId.value === id) {
    previewAudio.pause()
    playingVoiceId.value = ''
    return
  }
  playingVoiceId.value = id
  try {
    const res = await api.previewVoice({ text: previewText, voice_id: id })
    // axios 响应拦截器已剥掉外层 (res) => res.data，所以 res 直接是 body Blob。
    const data = res
    const isAudio = data instanceof Blob && (data.type === '' || data.type.startsWith('audio/'))
    if (!isAudio) {
      let msg = `试听失败: 收到非音频响应 (Content-Type=${data?.type || 'unknown'}, size=${data?.size ?? 0})`
      try {
        const txt = data instanceof Blob ? await data.text() : JSON.stringify(data)
        msg += ` | 服务端: ${txt.slice(0, 300)}`
      } catch { /* ignore */ }
      ElMessage.error(msg)
      playingVoiceId.value = ''
      return
    }
    const blobUrl = URL.createObjectURL(data)
    previewAudio.src = blobUrl
    previewAudio.play().catch(() => { /* autoplay 限制忽略 */ })
    previewAudio.onended = () => {
      playingVoiceId.value = ''
      URL.revokeObjectURL(blobUrl)
    }
  } catch (e) {
    ElMessage.error(e?.message || '试听失败')
    playingVoiceId.value = ''
  }
}

// 当前选中的数字人（用于展示背景图提示）
const selectedDigitalHuman = computed(() =>
  avatars.value.find(x => x.id === selectedAvatarId.value && x.type === 'digital_human') || null
)

watch(selectedAvatarId, () => autoPickVoiceByAvatar())

async function uploadImageIfNeeded() {
  if (!imageFile.value) return null
  const fd = new FormData()
  fd.append('file', imageFile.value)
  fd.append('name', imageFile.value.name || '驱动图')
  fd.append('category', '创作素材')
  const material = await api.uploadMaterial(fd)
  return material.url || null
}

async function startVideoGen() {
  genStarting.value = true
  genError.value = ''
  try {
    const imageUrl = videoGenType.value === 'image_to_video' ? await uploadImageIfNeeded() : null
    // 数字人/仿真人：口播词优先作为视频描述（后端用作驱动文本）
    const isAvatar = videoGenType.value === 'simulation_human' || videoGenType.value === 'digital_human'
    const desc = isAvatar && avatarScript.value.trim() ? avatarScript.value.trim() : videoDesc.value
    // 数字人/仿真人必须先选一个数字人，否则后端会因缺少参考图/主体而报错
    if (isAvatar && !selectedAvatarId.value) {
      ElMessage.warning('请先选择数字人（数字人/仿真人为必选项）')
      return
    }
    // 数字人/仿真人必须有口播词，否则 Kling 拿不到干净音频会自己"猜"出乱码字幕
    if (isAvatar && !(avatarScript.value.trim() || videoDesc.value.trim())) {
      ElMessage.warning('请先填写口播词（数字人/仿真人必须驱动口型）')
      return
    }
    const payload = {
      gen_type: videoGenType.value,
      description: desc,
      duration: videoDuration.value,
      resolution: videoResolution.value,
      fps: 24,
      image_url: imageUrl,
    }
    if (isAvatar) {
      payload.avatar_id = selectedAvatarId.value || undefined
      payload.avatar_type = videoGenType.value
      // 配音：选中的音色（标准音色 id 或 复刻音色 clone:<voice_type>）
      payload.voice_id = voiceId.value
      payload.tts_text = avatarScript.value.trim() || videoDesc.value
      // 注：复刻音色直接通过 voice_id=clone:<voice_type> 走后端 VRS 合成，
      // 不再依赖前端上传样本 URL（旧的 reference_audio_url 路径已废弃）。
    }
    await api.startGeneration(sessionId.value, payload)
    step.value = 3
    loadGenerations()
    startPolling()
  } catch (e) {
    genError.value = e.message || '启动生成失败'
  } finally {
    genStarting.value = false
  }
}

async function startImageGen(count) {
  genStarting.value = true
  genError.value = ''
  try {
    await api.startGeneration(sessionId.value, {
      gen_type: count === 1 ? 'cover' : 'images',
      description: `${copy.title} ${copy.body}`.slice(0, 200),
      style: imageStyle.value,
      brand_color: brandColor.value || null,
      brand_hint: brandHint.value || null,
      count,
    })
    step.value = 3
    loadGenerations()
    startPolling()
  } catch (e) {
    genError.value = e.message || '启动生成失败'
  } finally {
    genStarting.value = false
  }
}

// ── Step 3: 状态页 ────────────────────────────────────────────
const DEBUG_MODE = new URLSearchParams(location.search).has('debug')

// 调试模式：不调后端，注入一条伪 running 任务，用于零成本验证进度条链路
function loadDebugTask() {
  const now = Date.now()
  generationTasks.value = [{
    id: 99999,
    session_id: sessionId.value,
    gen_type: 'text_to_video',
    status: 'running',
    progress: 20,
    provider: 'debug',
    created_at: new Date(now - 2000).toISOString(),
    result: null,
    error_message: null,
  }]
}

async function loadGenerations() {
  if (DEBUG_MODE) { loadDebugTask(); return }
  if (!sessionId.value) {
    console.warn('[loadGenerations] sessionId is null, skip')
    return
  }
  console.log('[loadGenerations] fetching for sessionId=', sessionId.value)
  try {
    const data = await api.getGenerations(sessionId.value)
    console.log('[loadGenerations] got', Array.isArray(data) ? data.length : '?', 'tasks')
    generationTasks.value = data
  } catch (e) {
    console.error('[loadGenerations] failed:', e)
  }
}

function startPolling() {
  stopPolling()
  // 调试模式：用伪任务驱动 UI，不调后端、不花钱
  if (DEBUG_MODE) {
    nowTick.value = Date.now()
    progressTicker = setInterval(() => { nowTick.value = Date.now() }, 1000)
    // 10 秒后把伪任务置为 completed，模拟生成完成
    pollTimer = setInterval(() => {
      const t = generationTasks.value[0]
      if (t && t.id === 99999 && Date.now() - new Date(t.created_at).getTime() > 10000) {
        t.status = 'completed'
        t.progress = 100
        t.result = { material_ids: [1], video_url: '/static/materials/debug.mp4', image_urls: [] }
        generationTasks.value = [...generationTasks.value]
        stopPolling()
      }
    }, 1000)
    return
  }
  // 1 秒一刷本地时间，配合 displayProgress 让进度条在生成中平滑推进
  nowTick.value = Date.now()
  progressTicker = setInterval(() => { nowTick.value = Date.now() }, 1000)
  // 3 秒一拉后端
  pollTimer = setInterval(async () => {
    if (!sessionId.value) return
    try {
      const tasks = await api.getGenerations(sessionId.value)
      // 空数组说明轮询暂时无数据，不要停 ticker，避免进度冻结
      if (!tasks.length) return
      // 按 id 合并：保留本地 UI 标志（_previewOpen / _previewing），
      // 否则每秒整体替换会冲掉预览状态导致预览区瞬间关闭、视频播放被中断。
      const prevById = new Map(generationTasks.value.map(t => [t.id, t]))
      generationTasks.value = tasks.map(t => {
        const prev = prevById.get(t.id)
        if (!prev) return t
        // 后端字段为主，本地 UI 标志保留
        return { ...t, _previewOpen: prev._previewOpen, _previewing: prev._previewing }
      })
      // 仅当确实有终态任务且不存在 running/pending 时才停止轮询
      const hasActive = tasks.some(t => t.status === 'running' || t.status === 'pending')
      if (!hasActive) stopPolling()
    } catch { /* ignore */ }
  }, 3000)
}

function stopPolling() {
  if (pollTimer) { clearInterval(pollTimer); pollTimer = null }
  if (progressTicker) { clearInterval(progressTicker); progressTicker = null }
}

function goBackToGen() {
  stopPolling()
  step.value = 2
}

const materialCache = ref({}) // { [materialId]: { url, type, name } }

async function previewGeneration(gen) {
  const ids = gen.result?.material_ids || []
  if (!ids.length) {
    if (gen.result?.video_url) window.open(gen.result.video_url, '_blank')
    return
  }
  // 内联展示：逐条拉取素材 url
  gen._previewing = true
  try {
    for (const mid of ids) {
      if (!materialCache.value[mid]) {
        const m = await api.getMaterial(mid)
        materialCache.value[mid] = {
          url: m.url,
          type: m.type, // 'video' | 'image' | 'text'
          name: m.name,
          thumbnail_url: m.thumbnail_url,
        }
      }
    }
    gen._previewOpen = !gen._previewOpen
  } catch (e) {
    ElMessage.error('预览加载失败：' + (e.message || ''))
  } finally {
    gen._previewing = false
  }
}

async function regenerateWith(gen) {
  genStarting.value = true
  statusError.value = ''
  try {
    const params = {
      gen_type: gen.gen_type,
      ...(gen.input_params || {}),
    }
    await api.startGeneration(sessionId.value, params)
    loadGenerations()
  } catch (e) {
    statusError.value = e.message || '重新生成失败'
  } finally {
    genStarting.value = false
    startPolling()
  }
}

async function finishCreation() {
  completing.value = true
  statusError.value = ''
  try {
    const res = await api.completeSession(sessionId.value)
    ElMessage.success(`创作完成！产出 ${res.materials?.length || 0} 个素材`)
    router.push({ path: '/publish', query: { withSession: sessionId.value } })
  } catch (e) {
    statusError.value = e.message || '完成失败'
  } finally {
    completing.value = false
  }
}

// ── 路由守卫：离开页面前自动保存草稿 ──────────────────────────
onBeforeRouteLeave(async (_to, _from, next) => {
  if (sessionId.value) {
    await doSaveDraft()
  }
  next()
})

// ── 浏览器关闭/刷新：尽力保存草稿 ────────────────────────────
function onBeforeUnload() {
  if (sessionId.value && !savingDraft) {
    // 使用 keepalive fetch 在页面关闭时发送请求
    const data = collectDraftData()
    fetch(`/api/create/${sessionId.value}/save-draft`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
      keepalive: true,
    })
  }
}

// ── 生命周期 ──────────────────────────────────────────────────
onMounted(async () => {
  window.addEventListener('beforeunload', onBeforeUnload)

  // 检查是否有恢复参数
  if (route.query.resume) {
    try {
      const session = await api.getSession(parseInt(route.query.resume))
      if (session && session.status !== 'completed') {
        await resumeDraft(session)
        return
      }
    } catch { /* ignore */ }
  }

  if (route.query.platform) {
    form.platforms = [route.query.platform]
  }

  // 提前拉取标准音色，保证默认选中项能显示中文名而非 id
  loadVoices()
  // 提前拉取数字人列表，避免用户没点过头像下拉就发请求时拿到 null
  loadAvatars()

  // 加载草稿列表
  await loadDrafts()
  // 如果没有活跃 session 且有草稿，显示草稿列表
  if (!sessionId.value && route.query.resume === undefined) {
    showDraftList.value = true
  }
})

onBeforeUnmount(() => {
  stopPolling()
  clearTimeout(saveTimer)
  window.removeEventListener('beforeunload', onBeforeUnload)
  // 离开时保存草稿
  if (sessionId.value) {
    // 立即保存（非异步等待）
    const data = collectDraftData()
    api.saveDraft(sessionId.value, data).catch(() => {})
  }
})
</script>

<style scoped>
.create-wizard { max-width: 960px; margin: 0 auto; }
.steps { margin: 24px 0 32px; }
.wizard-toolbar { display: flex; justify-content: flex-start; padding: 8px 0 0 4px; }
.step-card {
  background: #fff;
  border-radius: 8px;
  padding: 24px;
  box-shadow: 0 1px 4px rgba(0,0,0,0.08);
}
.type-radio { margin-bottom: 20px; }
.input-form { margin-top: 12px; }

/* 草稿列表 */
.draft-list-card { min-height: 200px; }
.draft-list-header {
  display: flex; justify-content: space-between; align-items: center;
  margin-bottom: 20px; padding-bottom: 12px; border-bottom: 1px solid #eee;
}
.draft-list-header h3 { margin: 0; }
.empty-drafts { text-align: center; color: #999; padding: 60px 0; }
.draft-item {
  display: flex; justify-content: space-between; align-items: center;
  padding: 14px 16px; border: 1px solid #eee; border-radius: 8px;
  margin-bottom: 10px; transition: background 0.2s;
}
.draft-item:hover { background: #f9fafb; }
.draft-info { display: flex; align-items: center; gap: 12px; flex: 1; min-width: 0; }
.draft-keywords { font-weight: 600; font-size: 15px; max-width: 260px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.draft-time { color: #999; font-size: 13px; margin-left: auto; }
.draft-actions { display: flex; gap: 8px; margin-left: 16px; flex-shrink: 0; }

/* Step 1 左右分栏 */
.split-layout { display: flex; gap: 20px; min-height: 520px; }
.chat-panel { width: 38%; display: flex; flex-direction: column; border-right: 1px solid #eee; padding-right: 16px; }
.editor-panel { flex: 1; display: flex; flex-direction: column; }
.chat-header, .editor-header { font-weight: 600; margin-bottom: 12px; display: flex; align-items: center; justify-content: space-between; }
.chat-messages {
  flex: 1; overflow-y: auto; border: 1px solid #eee; border-radius: 6px;
  padding: 10px; margin-bottom: 10px; max-height: 280px; background: #fafafa;
}
.msg { margin-bottom: 8px; }
.msg.user .msg-content { background: #1d9bf0; color: #fff; padding: 6px 10px; border-radius: 8px; display: inline-block; max-width: 90%; }
.msg.assistant .msg-content { background: #e8ecf0; padding: 6px 10px; border-radius: 8px; display: inline-block; max-width: 90%; }
.quick-actions { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 10px; }
.chat-input-row { display: flex; gap: 8px; }
.editor-actions { margin-top: auto; padding-top: 16px; display: flex; justify-content: space-between; }
.loading-bubble .msg-content { display: inline-flex !important; align-items: center; gap: 6px; color: #666; }
.loading-spinner {
  display: inline-block; width: 12px; height: 12px;
  border: 2px solid #c8c8c8; border-top-color: #1d9bf0;
  border-radius: 50%; animation: spin 0.8s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }
.step-actions { margin-top: 20px; display: flex; justify-content: space-between; }

/* Step 2 */
.output-form { margin-top: 16px; }
.preview-img { width: 120px; margin-top: 8px; border-radius: 4px; border: 1px solid #ddd; }

/* Step 3 */
.progress-card { background: #f5f7fa; padding: 20px; border-radius: 8px; margin-bottom: 16px; }
.progress-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
.progress-hint { margin-top: 8px; color: #999; font-size: 13px; }
.progress-cost { margin-top: 8px; color: #409eff; font-size: 13px; font-weight: 600; }
.error-msg { color: #f56c6c; margin-top: 6px; font-size: 13px; }
.gen-cost { margin-left: 10px; color: #409eff; font-size: 12px; }
.gen-item {
  padding: 10px 0; border-bottom: 1px solid #f0f0f0;
}
.gen-item-head {
  display: flex; align-items: center; gap: 12px;
}
.gen-time { color: #999; font-size: 12px; margin-left: auto; }
.gen-actions { display: flex; gap: 6px; }
.gen-preview {
  margin-top: 10px; padding: 12px; background: #fafafa; border-radius: 8px;
  display: flex; flex-wrap: wrap; gap: 12px;
}
.preview-block { max-width: 320px; }
.preview-name { font-size: 12px; color: #666; margin-bottom: 4px; }
.preview-media {
  max-width: 300px; max-height: 220px; border-radius: 6px; background: #000;
}
.preview-link { font-size: 13px; color: #409eff; }
.preview-empty { font-size: 12px; color: #999; }
.empty { color: #999; padding: 20px 0; }
.cost-tag {
  font-size: 12px;
  color: #e6a23c;
  white-space: nowrap;
  padding: 2px 8px;
  background: #fdf6ec;
  border: 1px solid #faecd8;
  border-radius: 4px;
}
</style>
