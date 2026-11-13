import type { ReactNode } from 'react'

import type { Feature } from '../../api/types'
import { useAccess } from '../../lib/access'
import { EmptyState } from '../ui'

/** Renders the page only if the user may use the feature; otherwise explains why it is locked. */
export function FeatureGate({ feature, children }: { feature: Feature; children: ReactNode }) {
  const { can, pending } = useAccess()
  if (can(feature)) return children
  return (
    <div className="page">
      <EmptyState
        emoji="🔒"
        title={pending ? 'Tài khoản đang chờ duyệt' : 'Tính năng chưa được mở'}
        text={
          pending
            ? 'Admin sẽ cấp quyền cho tài khoản của bạn sớm. Bạn vẫn có thể xem trang Tổng quan và Tài khoản.'
            : 'Tính năng này chưa được cấp cho tài khoản của bạn hoặc đang tạm tắt. Hãy liên hệ admin.'
        }
      />
    </div>
  )
}

export function AdminGate({ children }: { children: ReactNode }) {
  const { isAdmin } = useAccess()
  if (isAdmin) return children
  return (
    <div className="page">
      <EmptyState emoji="🛡️" title="Chỉ dành cho admin" text="Bạn không có quyền xem trang này." />
    </div>
  )
}
