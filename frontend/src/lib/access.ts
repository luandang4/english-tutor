import { useMe } from '../api/hooks'
import type { Feature } from '../api/types'

/** What the signed-in user may use. Only for showing / hiding UI — the API enforces the same rules. */
export function useAccess() {
  const { data: me } = useMe()
  const features = new Set(me?.features ?? [])
  return {
    can: (feature: Feature) => features.has(feature),
    isAdmin: !!me?.is_admin,
    pending: !!me?.pending,
  }
}
