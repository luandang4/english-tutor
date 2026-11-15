import { useMemo, useState } from 'react'

import { useAdminPlans, useAdminUsers, useMe, useUpdateUser, useUserPlanActions } from '../../api/hooks'
import type { AdminUser, Feature, FeatureInfo, Plan } from '../../api/types'
import { EmptyState, ErrorBox, Icon, Loading, Spinner } from '../../components/ui'
import { UsageBars } from '../../components/ui/UsageBars'
import { daysLeft, formatDate } from '../../lib/access'
import { timeAgo } from '../../lib/format'

type Filter = 'all' | 'pending' | 'expiring' | 'expired' | 'locked'

const STATUS_BADGE: Record<string, [string, string]> = {
  pending: ['pending', 'Chờ duyệt'],
  expired: ['failed', 'Hết hạn'],
  locked: ['failed', 'Bị khoá'],
}

function expiringSoon(u: AdminUser): boolean {
  const left = daysLeft(u.subscription?.expires_at)
  return u.access_status === 'active' && left != null && left <= 7
}

const FILTERS: [Filter, string, (u: AdminUser) => boolean][] = [
  ['all', 'Tất cả', () => true],
  ['pending', 'Chờ duyệt', (u) => u.access_status === 'pending'],
  ['expiring', 'Sắp hết hạn (7 ngày)', expiringSoon],
  ['expired', 'Đã hết hạn', (u) => u.access_status === 'expired'],
  ['locked', 'Bị khoá', (u) => u.access_status === 'locked'],
]

export function UsersTab({ features }: { features: FeatureInfo[] }) {
  const { data: users, error, isPending, refetch } = useAdminUsers()
  const { data: plans } = useAdminPlans()
  const [filter, setFilter] = useState<Filter>('all')
  const [query, setQuery] = useState('')
  const test = FILTERS.find(([value]) => value === filter)![2]
  const shown = useMemo(
    () =>
      (users ?? []).filter((u) => {
        const q = query.trim().toLowerCase()
        return test(u) && (!q || u.email.includes(q) || u.display_name.toLowerCase().includes(q))
      }),
    [users, test, query],
  )

  return (
    <section className="card stack admin-section">
      <div className="card-title row">
        <h3 className="spacer">Người dùng {users ? `(${users.length})` : ''}</h3>
        <input
          className="input admin-search"
          placeholder="Tìm theo tên / email"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
      </div>
      <div className="tabs" role="tablist">
        {FILTERS.map(([value, label, match]) => {
          const count = value === 'all' ? 0 : (users ?? []).filter(match).length
          return (
            <button key={value} className={`tab ${filter === value ? 'active' : ''}`} onClick={() => setFilter(value)}>
              {label}
              {count ? ` (${count})` : ''}
            </button>
          )
        })}
      </div>

      {isPending ? (
        <Loading />
      ) : error ? (
        <ErrorBox error={error} onRetry={() => refetch()} />
      ) : shown.length === 0 ? (
        <EmptyState emoji="👥" title="Không có tài khoản nào" text="Thử bộ lọc khác." />
      ) : (
        <div className="stack" style={{ gap: 10 }}>
          {shown.map((u) => (
            <UserRow key={u.id} user={u} features={features} plans={plans ?? []} />
          ))}
        </div>
      )}
    </section>
  )
}

function UserRow({ user, features, plans }: { user: AdminUser; features: FeatureInfo[]; plans: Plan[] }) {
  const { data: me } = useMe()
  const update = useUpdateUser()
  const isSelf = me?.id === user.id
  const patch = (p: Parameters<typeof update.mutate>[0]['patch']) => update.mutate({ id: user.id, patch: p })
  const sub = user.subscription
  const badge = STATUS_BADGE[user.access_status]
  const left = daysLeft(sub?.expires_at)

  return (
    <div className={`admin-user ${user.is_active ? '' : 'locked'}`}>
      <div className="row admin-user-head">
        <span className="avatar">{user.display_name.charAt(0).toUpperCase()}</span>
        <div className="spacer" style={{ minWidth: 0 }}>
          <b>{user.display_name}</b> {isSelf && <span className="small muted">(bạn)</span>}
          <div className="small muted ellipsis">{user.email}</div>
        </div>
        <div className="row" style={{ gap: 6, flexWrap: 'wrap', justifyContent: 'flex-end' }}>
          {user.is_admin && <span className="badge level">Admin</span>}
          {sub && <span className="badge ready">{sub.plan_name}</span>}
          {badge && <span className={`badge ${badge[0]}`}>{badge[1]}</span>}
          {expiringSoon(user) && <span className="badge pending">Còn {left} ngày</span>}
        </div>
      </div>

      <div className="small muted">
        Tạo {timeAgo(user.created_at)} · {user.last_login_at ? `đăng nhập ${timeAgo(user.last_login_at)}` : 'chưa đăng nhập'}
        {sub && (sub.expires_at ? ` · hạn ${formatDate(sub.expires_at)}` : ' · không hết hạn')}
        {sub?.note && ` · ${sub.note}`}
      </div>

      {user.usage.length > 0 && <UsageBars usage={user.usage} compact />}

      {!user.is_admin && user.is_active && (
        <details className="admin-details" open={user.access_status === 'pending'}>
          <summary>{user.access_status === 'pending' ? 'Duyệt: chọn gói' : 'Gói và lượt cộng thêm'}</summary>
          <PlanPicker user={user} plans={plans} />
          {sub && <GrantForm user={user} features={features} />}
        </details>
      )}
      {user.is_admin && <span className="small muted">Admin dùng được mọi tính năng đang bật, không giới hạn.</span>}

      {update.error && <ErrorBox error={update.error} />}
      {!isSelf && (
        <div className="row" style={{ gap: 8, flexWrap: 'wrap' }}>
          <button
            className={`btn sm ${user.is_active ? 'danger' : ''}`}
            disabled={update.isPending}
            onClick={() =>
              (!user.is_active || confirm(`Khoá tài khoản ${user.email}? Người này sẽ bị đăng xuất ngay.`)) &&
              patch({ is_active: !user.is_active })
            }
          >
            <Icon name="lock" size={14} /> {user.is_active ? 'Khoá' : 'Mở khoá'}
          </button>
          <button
            className="btn sm ghost"
            disabled={update.isPending || !user.is_active}
            onClick={() =>
              confirm(user.is_admin ? `Bỏ quyền admin của ${user.email}?` : `Cấp quyền admin cho ${user.email}?`) &&
              patch({ is_admin: !user.is_admin })
            }
          >
            <Icon name="shield" size={14} /> {user.is_admin ? 'Bỏ admin' : 'Cấp admin'}
          </button>
        </div>
      )}
    </div>
  )
}

// ---------- plan + expiry ----------
function toDateInput(d: Date): string {
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}

function addMonths(from: Date, months: number): Date {
  const d = new Date(from)
  d.setMonth(d.getMonth() + months)
  return d
}

function addDays(from: Date, days: number): Date {
  return new Date(from.getTime() + days * 86_400_000)
}

/** "+1 tháng" extends from the current expiry when it is still ahead, otherwise from today. */
function extensionBase(user: AdminUser): Date {
  const sub = user.subscription
  const now = new Date()
  const current = sub?.status === 'active' && sub.expires_at ? new Date(sub.expires_at) : null
  return current && current > now ? current : now
}

/** End of the chosen day in the browser's timezone, as ISO; '' = never expires. */
function endOfDay(date: string): string | null {
  return date ? new Date(`${date}T23:59:59`).toISOString() : null
}

function PlanPicker({ user, plans }: { user: AdminUser; plans: Plan[] }) {
  const { assign, cancel } = useUserPlanActions()
  const sub = user.subscription
  const offered = plans.filter((p) => p.is_active)
  const [planId, setPlanId] = useState<number | ''>(sub?.status === 'active' ? sub.plan_id : '')
  const [expires, setExpires] = useState(sub?.expires_at ? toDateInput(new Date(sub.expires_at)) : '')
  const [note, setNote] = useState('')
  const [minDate] = useState(() => toDateInput(addDays(new Date(), 1)))
  const extend = (months: number) => setExpires(toDateInput(addMonths(extensionBase(user), months)))

  const choosePlan = (id: number) => {
    setPlanId(id)
    const plan = plans.find((p) => p.id === id)
    if (plan) setExpires(plan.duration_days ? toDateInput(addDays(new Date(), plan.duration_days)) : '')
  }

  return (
    <div className="stack plan-picker">
      <div className="plan-form-grid">
        <label className="field">
          Gói
          <select
            className="select"
            value={planId}
            onChange={(e) => e.target.value && choosePlan(Number(e.target.value))}
          >
            <option value="">Chọn gói…</option>
            {offered.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
                {p.price_label ? ` · ${p.price_label}` : ''}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          Hết hạn (trống = không hết hạn)
          <input
            className="input"
            type="date"
            min={minDate}
            value={expires}
            onChange={(e) => setExpires(e.target.value)}
          />
        </label>
        <label className="field">
          Ghi chú
          <input className="input" maxLength={500} value={note} onChange={(e) => setNote(e.target.value)} />
        </label>
      </div>
      <div className="row" style={{ gap: 6, flexWrap: 'wrap' }}>
        <button className="btn sm ghost" type="button" onClick={() => extend(1)}>
          +1 tháng
        </button>
        <button className="btn sm ghost" type="button" onClick={() => extend(3)}>
          +3 tháng
        </button>
        <button className="btn sm ghost" type="button" onClick={() => setExpires('')}>
          Không hết hạn
        </button>
        <span className="spacer" />
        <button
          className="btn sm primary"
          disabled={planId === '' || assign.isPending}
          onClick={() =>
            planId !== '' && assign.mutate({ id: user.id, plan_id: planId, expires_at: endOfDay(expires), note })
          }
        >
          {assign.isPending ? <Spinner small /> : <Icon name="check" size={14} />}{' '}
          {user.access_status === 'pending' ? 'Duyệt với gói này' : 'Lưu gói'}
        </button>
        {sub?.status === 'active' && (
          <button
            className="btn sm danger"
            disabled={cancel.isPending}
            onClick={() => confirm(`Thu hồi gói của ${user.email}? Tài khoản sẽ về trạng thái chờ duyệt.`) && cancel.mutate(user.id)}
          >
            Thu hồi gói
          </button>
        )}
      </div>
      {(assign.error || cancel.error) && <ErrorBox error={assign.error ?? cancel.error} />}
    </div>
  )
}

// ---------- bonus allowance ----------
function GrantForm({ user, features }: { user: AdminUser; features: FeatureInfo[] }) {
  const { grant, removeGrant } = useUserPlanActions()
  const usable = features.filter((f) => user.features.includes(f.value))
  const [feature, setFeature] = useState<Feature>(usable[0]?.value ?? 'conversation')
  const [amount, setAmount] = useState(30)
  const [scope, setScope] = useState<'day' | 'month'>('month')
  const [note, setNote] = useState('')
  const label = (f: Feature) => features.find((x) => x.value === f)
  if (!usable.length) return null

  return (
    <div className="stack grant-form">
      <b className="small">Cộng thêm lượt</b>
      <div className="row" style={{ gap: 8, flexWrap: 'wrap', alignItems: 'flex-end' }}>
        <label className="field">
          Tính năng
          <select className="select" value={feature} onChange={(e) => setFeature(e.target.value as Feature)}>
            {usable.map((f) => (
              <option key={f.value} value={f.value}>
                {f.label}
              </option>
            ))}
          </select>
        </label>
        <label className="field grant-amount">
          Số {label(feature)?.unit}
          <input
            className="input"
            type="number"
            min={1}
            max={100000}
            value={amount}
            onChange={(e) => setAmount(Math.max(1, Math.floor(Number(e.target.value))))}
          />
        </label>
        <label className="field">
          Áp dụng
          <select className="select" value={scope} onChange={(e) => setScope(e.target.value as 'day' | 'month')}>
            <option value="month">Tháng này</option>
            <option value="day">Chỉ hôm nay</option>
          </select>
        </label>
        <label className="field spacer">
          Ghi chú
          <input className="input" maxLength={500} value={note} onChange={(e) => setNote(e.target.value)} />
        </label>
        <button
          className="btn sm"
          disabled={grant.isPending}
          onClick={() =>
            grant.mutate({ id: user.id, body: { feature, amount, scope, note } }, { onSuccess: () => setNote('') })
          }
        >
          <Icon name="plus" size={14} /> Cộng thêm
        </button>
      </div>
      <span className="small muted">
        "Tháng này" nâng giới hạn tháng; "Chỉ hôm nay" nâng giới hạn hôm nay. Tính năng không giới hạn theo tháng / ngày
        thì phần cộng tương ứng không có tác dụng.
      </span>
      {grant.error && <ErrorBox error={grant.error} />}
      {user.grants.length > 0 && (
        <ul className="grant-list small">
          {user.grants.map((g) => (
            <li key={g.id} className="row">
              <span className="spacer">
                +{g.amount} {label(g.feature)?.unit} {label(g.feature)?.label} ·{' '}
                {g.period.length > 7 ? `ngày ${formatDate(g.period)}` : 'tháng này'}
                {g.note && ` · ${g.note}`}
              </span>
              <button
                className="btn sm ghost"
                aria-label="Xoá lượt cộng thêm"
                disabled={removeGrant.isPending}
                onClick={() => removeGrant.mutate(g.id)}
              >
                <Icon name="trash" size={14} />
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
