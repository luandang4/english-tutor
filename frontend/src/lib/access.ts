import { useMe } from '../api/hooks'
import type { Feature } from '../api/types'

const DAY_MS = 86_400_000

/** What the signed-in user may use. Only for showing / hiding UI — the API enforces the same rules. */
export function useAccess() {
  const { data: me } = useMe()
  const features = new Set(me?.features ?? [])
  const viewable = new Set(me?.view_features ?? [])
  return {
    can: (feature: Feature) => features.has(feature),
    /** May open own past work of this feature (also after the plan expired). */
    canView: (feature: Feature) => viewable.has(feature),
    isAdmin: !!me?.is_admin,
    pending: !!me?.pending,
    expired: me?.access_status === 'expired',
    plan: me?.plan ?? null,
    contact: me?.upgrade_contact ?? '',
  }
}

/** Whole days left until `expiresAt` (0 = expires today); null = never expires. */
export function daysLeft(expiresAt: string | null | undefined): number | null {
  if (!expiresAt) return null
  return Math.max(0, Math.ceil((new Date(expiresAt).getTime() - Date.now()) / DAY_MS))
}

export function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString('vi-VN')
}

/** "Liên hệ: …" sentence for limit / expiry messages. */
export function contactText(contact: string): string {
  return contact ? `Liên hệ để nâng gói: ${contact}` : 'Hãy liên hệ admin để được cấp gói.'
}
