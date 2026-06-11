export const IMAGE_STYLES = [
  { value: 'default', label: '清新自然' },
  { value: 'minimal', label: '极简留白' },
  { value: 'vivid', label: '鲜艳醒目' },
  { value: 'elegant', label: '典雅精致' },
  { value: 'retro', label: '复古文艺' },
]

/** 历史模板可能存英文别名，展示前统一映射 */
export const IMAGE_STYLE_ALIASES = {
  fresh: 'default',
  natural: 'default',
  clean: 'minimal',
  bold: 'vivid',
}

export function normalizeImageStyle(style) {
  if (!style) return 'default'
  const aliased = IMAGE_STYLE_ALIASES[style] || style
  return IMAGE_STYLES.some((item) => item.value === aliased) ? aliased : 'default'
}

export function imageStyleLabel(style) {
  const normalized = normalizeImageStyle(style)
  return IMAGE_STYLES.find((item) => item.value === normalized)?.label || '清新自然'
}

export const BRAND_COLOR_CUSTOM = '__custom__'

export const BRAND_COLORS = [
  { value: '', label: '不指定品牌色', swatch: null },
  { value: '#2E8B57', label: '森林绿', swatch: '#2E8B57', hint: '茶叶、农产品、自然风' },
  { value: '#228B22', label: '草绿色', swatch: '#228B22', hint: '健康、有机、户外' },
  { value: '#C8102E', label: '中国红', swatch: '#C8102E', hint: '节庆、礼盒、促销' },
  { value: '#FF4500', label: '活力橙', swatch: '#FF4500', hint: '电商大促、爆款' },
  { value: '#1E90FF', label: '天空蓝', swatch: '#1E90FF', hint: '科技、清爽、饮品' },
  { value: '#D4AF37', label: '典雅金', swatch: '#D4AF37', hint: '高端、轻奢' },
  { value: '#6A5ACD', label: '高贵紫', swatch: '#6A5ACD', hint: '美妆、文创' },
  { value: '#FF6B6B', label: '珊瑚粉', swatch: '#FF6B6B', hint: '美妆、母婴、甜品' },
  { value: '#333333', label: '深邃黑', swatch: '#333333', hint: '简约、数码、男装' },
  { value: BRAND_COLOR_CUSTOM, label: '其他颜色（高级）', swatch: null },
]

export function brandColorLabel(hex) {
  if (!hex) return '不指定品牌色'
  const found = BRAND_COLORS.find((item) => item.value === hex)
  return found ? found.label : hex
}

export function resolveBrandColorPreset(hex) {
  const found = BRAND_COLORS.find((item) => item.value && item.value === hex)
  if (found) return found.value
  return hex ? BRAND_COLOR_CUSTOM : ''
}

export const IMAGE_RATIOS = ['1:1', '3:4', '4:5', '4:3', '9:16', '16:9']
