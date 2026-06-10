/** 文案 cost = API total_tokens；文生图 cost = 生成张数或 credits */
export function formatAiUsage(type, cost) {
  const n = Number(cost || 0)
  if (type === 'text') {
    return `${Math.round(n).toLocaleString()} Token`
  }
  if (type === 'image') {
    const units = Number.isInteger(n) ? n : Math.round(n)
    return `${units} 张`
  }
  return String(n)
}

export function aiUsageUnitLabel(type) {
  if (type === 'text') return 'Token'
  if (type === 'image') return '张数'
  return '用量'
}
