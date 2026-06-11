/** B站投稿分区 tid（常用子集，完整列表见 B站创作中心） */
export const BILIBILI_TIDS = [
  { value: 21, label: '日常' },
  { value: 138, label: '搞笑' },
  { value: 76, label: '美食' },
  { value: 183, label: '影视' },
  { value: 249, label: '足球' },
  { value: 17, label: '单机游戏' },
  { value: 65, label: '网络游戏' },
  { value: 122, label: '知识' },
  { value: 155, label: '时尚' },
  { value: 160, label: '生活' },
]

export function bilibiliTidLabel(tid) {
  const item = BILIBILI_TIDS.find((t) => t.value === tid)
  return item ? `${item.label} (${tid})` : String(tid ?? '-')
}
