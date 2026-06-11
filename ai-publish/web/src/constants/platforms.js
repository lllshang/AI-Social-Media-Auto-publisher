export const PLATFORMS = [
  {
    value: 'xhs',
    label: '小红书',
    appName: '小红书 App',
    coverRatio: '3:4',
    videoCoverRatio: '3:4',
    videoHint: '建议竖屏 9:16、MP4 格式；可在下一步生成或上传 3:4 视频封面（可选）',
    contentTypes: [
      { value: 'note', label: '图文' },
      { value: 'video', label: '视频' },
    ],
  },
  {
    value: 'douyin',
    label: '抖音',
    appName: '抖音 App',
    coverRatio: '9:16',
    contentTypes: [
      { value: 'note', label: '图文' },
      { value: 'video', label: '视频' },
    ],
  },
  {
    value: 'kuaishou',
    label: '快手',
    appName: '快手 App',
    coverRatio: '9:16',
    contentTypes: [
      { value: 'note', label: '图文' },
      { value: 'video', label: '视频' },
    ],
  },
  {
    value: 'channels',
    label: '视频号',
    appName: '微信 App',
    coverRatio: '3:4',
    videoCoverRatio: '3:4',
    experimental: true,
    videoHint: '仅支持短视频（竖屏 MP4 等）；可选 3:4 封面与短标题（6-16字）',
    contentTypes: [{ value: 'video', label: '短视频' }],
  },
  {
    value: 'bilibili',
    label: 'B站',
    appName: '哔哩哔哩 App',
    coverRatio: '16:9',
    experimental: true,
    loginHint:
      'B站登录需在本地终端执行：cd vendor/social-auto-upload && sau bilibili login --account <账号名>，完成后点击「校验 Cookie」。',
    videoHint: '仅支持视频投稿（MP4 等），需选择分区 tid；上传通过 biliup CLI 执行',
    contentTypes: [{ value: 'video', label: '视频' }],
  },
]

export function platformLabel(value) {
  const item = PLATFORMS.find((p) => p.value === value)
  if (!item) return value
  return item.experimental ? `${item.label}（实验）` : item.label
}

export function platformLoginHint(value) {
  return PLATFORMS.find((p) => p.value === value)?.loginHint || ''
}

export function platformAppName(value) {
  return PLATFORMS.find((p) => p.value === value)?.appName || '对应 App'
}

export function platformCoverRatio(value) {
  return PLATFORMS.find((p) => p.value === value)?.coverRatio || '3:4'
}

export function platformVideoCoverRatio(value) {
  return PLATFORMS.find((p) => p.value === value)?.videoCoverRatio || platformCoverRatio(value)
}

export function platformVideoHint(value) {
  return PLATFORMS.find((p) => p.value === value)?.videoHint || '请上传 MP4 等常见视频格式'
}

export const CONTENT_TYPE_LABELS = {
  note: '图文',
  video: '视频',
}

export function contentTypeLabel(value) {
  return CONTENT_TYPE_LABELS[value] || value
}
