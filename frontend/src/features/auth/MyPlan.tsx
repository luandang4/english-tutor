import { useMe, useUsage } from '../../api/hooks'
import { UsageBars } from '../../components/ui/UsageBars'
import { contactText, daysLeft, formatDate } from '../../lib/access'

/** "Gói của bạn": plan name, expiry, and day / month usage against the plan's limits. */
export function MyPlan() {
  const { data: me } = useMe()
  const { data: usage } = useUsage()
  if (!me) return null

  const left = daysLeft(me.plan?.expires_at)
  return (
    <section className="card stack">
      <div className="card-title" style={{ marginBottom: 0 }}>
        <h3>Gói của bạn</h3>
        {me.plan && <span className="badge level">{me.plan.name}</span>}
      </div>
      <p className="small muted">{planStatusText(me.access_status, me.plan, left)}</p>
      {me.access_status !== 'admin' && me.access_status !== 'active' && (
        <p className="small">{contactText(me.upgrade_contact)}</p>
      )}
      {usage && usage.length > 0 && (
        <>
          <UsageBars usage={usage} />
          <p className="small muted">Lượt ngày mở lại lúc 0h, lượt tháng mở lại ngày 1 (giờ Việt Nam).</p>
        </>
      )}
      {me.access_status === 'active' && me.upgrade_contact && (
        <p className="small muted">Muốn thêm lượt hoặc nâng gói? {me.upgrade_contact}</p>
      )}
    </section>
  )
}

function planStatusText(
  status: string,
  plan: { name: string; expires_at: string | null } | null,
  left: number | null,
): string {
  if (status === 'admin') return 'Admin dùng được mọi tính năng đang bật, không giới hạn.'
  if (status === 'pending') return 'Tài khoản đang chờ admin duyệt và chọn gói.'
  if (status === 'expired' && plan?.expires_at)
    return `Gói đã hết hạn ngày ${formatDate(plan.expires_at)}. Các tính năng AI tạm khoá; bạn vẫn ôn từ vựng và xem lại bài cũ được.`
  if (!plan) return ''
  if (!plan.expires_at) return 'Không hết hạn.'
  return `Hết hạn ngày ${formatDate(plan.expires_at)}${left != null ? ` (còn ${left} ngày)` : ''}.`
}
