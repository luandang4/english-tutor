import type { ReactNode } from 'react'

import type { Feature } from '../../api/types'
import { contactText, useAccess } from '../../lib/access'
import { EmptyState, Icon } from '../ui'

/** Renders the page if the user may use the feature. With an expired plan the page still opens (old lessons /
 * history stay readable) under a notice; new AI requests are refused by the server with a clear message. */
export function FeatureGate({ feature, children }: { feature: Feature; children: ReactNode }) {
  const { can, canView, pending, expired, contact } = useAccess()
  if (can(feature)) return children
  if (canView(feature)) {
    return (
      <>
        <div className="pending-banner view-only-banner">
          <Icon name="lock" size={16} />
          <span>
            {expired ? 'Gói của bạn đã hết hạn' : 'Tính năng này đang tạm khoá'}: bạn vẫn xem lại được bài cũ, nhưng chưa
            tạo bài mới được. {contactText(contact)}
          </span>
        </div>
        {children}
      </>
    )
  }
  return (
    <div className="page">
      <EmptyState
        emoji="🔒"
        title={pending ? 'Tài khoản đang chờ duyệt' : 'Tính năng chưa được mở'}
        text={
          pending
            ? `Admin sẽ chọn gói cho tài khoản của bạn sớm. Bạn vẫn có thể xem trang Tổng quan và Tài khoản. ${contactText(contact)}`
            : `Gói hiện tại của bạn không có tính năng này hoặc tính năng đang tạm tắt. ${contactText(contact)}`
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
