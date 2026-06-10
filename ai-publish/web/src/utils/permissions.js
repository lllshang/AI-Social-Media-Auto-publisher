export function can(permissions, required) {
  if (!permissions || permissions.length === 0) return true
  if (permissions.includes('*')) return true
  return permissions.includes(required)
}
