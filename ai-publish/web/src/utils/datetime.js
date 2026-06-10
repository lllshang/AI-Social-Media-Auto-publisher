/** 将 API 返回的 UTC 时间格式化为本地可读时间 */
export function formatDateTime(value) {
  if (!value) return '-'
  const raw = String(value)
  const iso = /[zZ]|[+-]\d{2}:\d{2}$/.test(raw) ? raw : `${raw}Z`
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return raw
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  })
}
