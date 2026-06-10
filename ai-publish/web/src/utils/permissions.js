/** 权限标识 → 中文说明（仅用于界面展示，鉴权仍用英文 key） */
export const PERMISSION_LABELS = {
  '*': '全部权限',
  'dashboard:read': '查看工作台',
  'accounts:read': '查看平台账号',
  'accounts:write': '管理平台账号',
  'materials:read': '查看素材库',
  'materials:write': '管理素材库',
  'tasks:read': '查看发布任务',
  'tasks:write': '管理发布任务',
  'tasks:execute': '执行发布任务',
  'publish:write': '使用发布向导',
  'models:read': '查看 AI 模型',
  'models:write': '配置 AI 模型',
  'logs:read': '查看日志中心',
  'settings:write': '系统设置',
}

export const ROLE_LABELS = {
  admin: '管理员',
  operator: '运营人员',
  viewer: '只读用户',
}

export function permissionLabel(perm) {
  return PERMISSION_LABELS[perm] || perm
}

export function roleLabel(name) {
  return ROLE_LABELS[name] || name
}

export function can(permissions, required) {
  if (!permissions || permissions.length === 0) return true
  if (permissions.includes('*')) return true
  return permissions.includes(required)
}
