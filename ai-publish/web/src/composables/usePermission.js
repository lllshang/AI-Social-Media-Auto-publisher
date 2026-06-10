import { useAuthStore } from '@/stores/auth'
import { can as canPerm, canAny as canAnyPerm } from '@/utils/permissions'

export function usePermission() {
  const auth = useAuthStore()

  function can(permission) {
    return canPerm(auth.permissions, permission)
  }

  function canAny(permissions) {
    return canAnyPerm(auth.permissions, permissions)
  }

  return { can, canAny, permissions: auth.permissions }
}
