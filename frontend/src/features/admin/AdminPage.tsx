import { useMemo, useState } from 'react'

import { useAdminSystem, useAdminUsers, useMe, useMeta, useSaveSystem, useUpdateUser } from '../../api/hooks'
import type { AdminUser, Feature, FeatureInfo, SystemSettings } from '../../api/types'
import { EmptyState, ErrorBox, Icon, Loading, PageHeader, Spinner } from '../../components/ui'
import { timeAgo } from '../../lib/format'
import './admin.css'

export function AdminPage() {
  const { data: meta } = useMeta()
  const features = meta?.features ?? []
  return (
    <div className="page">
      <PageHeader
        title="Quản trị"
        subtitle="Bật / tắt tính năng toàn hệ thống, giới hạn mỗi ngày và cấp quyền cho từng tài khoản. Máy chủ kiểm tra lại mọi quyền này ở từng request."
      />
      <SystemPanel features={features} />
      <UsersPanel features={features} />
    </div>
  )
}

// ---------- system-wide switches ----------
function SystemPanel({ features }: { features: FeatureInfo[] }) {
  const { data, error, isPending, refetch } = useAdminSystem()
  const save = useSaveSystem()
  const [draft, setDraft] = useState<SystemSettings | null>(null)
  const current = draft ?? data

  if (isPending) return <Loading />
  if (error || !current) return <ErrorBox error={error} onRetry={() => refetch()} />

  const update = (patch: Partial<SystemSettings>) => setDraft({ ...current, ...patch })
  const toggleDefault = (f: Feature) =>
    update({
      default_features: current.default_features.includes(f)
        ? current.default_features.filter((x) => x !== f)
        : [...current.default_features, f],
    })

  return (
    <section className="card stack admin-section">
      <div className="card-title">
        <h3>Hệ thống</h3>
      </div>

      <div className="admin-grid">
        {features.map((f) => (
          <div key={f.value} className={`feature-row ${current.features_enabled[f.value] ? '' : 'off'}`}>
            <label className="toggle">
              <input
                type="checkbox"
                checked={current.features_enabled[f.value]}
                onChange={(e) =>
                  update({ features_enabled: { ...current.features_enabled, [f.value]: e.target.checked } })
                }
              />
              <span className="switch" aria-hidden="true" />
              <span>
                {f.label}
                <small>{current.features_enabled[f.value] ? 'Đang bật cho mọi người' : 'Đã tắt với tất cả, kể cả admin'}</small>
              </span>
            </label>
            <label className="field limit">
              Giới hạn / người / ngày
              <span className="limit-input">
                <input
                  className="input"
                  type="number"
                  min={0}
                  max={100000}
                  value={current.daily_limits[f.value] ?? 0}
                  onChange={(e) =>
                    update({ daily_limits: { ...current.daily_limits, [f.value]: Math.max(0, Number(e.target.value)) } })
                  }
                />
                <span className="small muted">{f.unit}</span>
              </span>
            </label>
          </div>
        ))}
      </div>
      <p className="small muted">Giới hạn 0 = không giới hạn. Admin không bị giới hạn theo ngày.</p>

      <div className="admin-row">
        <label className="toggle">
          <input
            type="checkbox"
            checked={current.registration_open}
            onChange={(e) => update({ registration_open: e.target.checked })}
          />
          <span className="switch" aria-hidden="true" />
          <span>
            Cho phép đăng ký tài khoản mới
            <small>
              Người mới chỉ dùng được các tính năng mặc định bên dưới.
            </small>
          </span>
        </label>
      </div>

      <div className="stack" style={{ gap: 8 }}>
        <b className="small">Tính năng mặc định cho tài khoản mới</b>
        <FeatureChips features={features} selected={current.default_features} onToggle={toggleDefault} />
        <span className="small muted">
          {current.default_features.length ? '' : 'Không chọn gì = tài khoản mới phải chờ admin duyệt (khuyên dùng).'}
        </span>
      </div>

      {save.error && <ErrorBox error={save.error} />}
      <div className="row">
        <button
          className="btn primary"
          disabled={!draft || save.isPending}
          onClick={() => save.mutate(current, { onSuccess: () => setDraft(null) })}
        >
          {save.isPending ? <Spinner small /> : <Icon name="check" size={16} />} Lưu cài đặt
        </button>
        {draft && (
          <button className="btn ghost" onClick={() => setDraft(null)}>
            Huỷ thay đổi
          </button>
        )}
        {save.isSuccess && !draft && <span className="small tone-good">Đã lưu</span>}
      </div>
    </section>
  )
}

// ---------- users ----------
type Filter = 'all' | 'pending' | 'locked'

function UsersPanel({ features }: { features: FeatureInfo[] }) {
  const { data: users, error, isPending, refetch } = useAdminUsers()
  const [filter, setFilter] = useState<Filter>('all')
  const [query, setQuery] = useState('')
  const shown = useMemo(
    () =>
      (users ?? []).filter((u) => {
        if (filter === 'pending' && (u.is_admin || u.features.length || !u.is_active)) return false
        if (filter === 'locked' && u.is_active) return false
        const q = query.trim().toLowerCase()
        return !q || u.email.includes(q) || u.display_name.toLowerCase().includes(q)
      }),
    [users, filter, query],
  )
  const pendingCount = (users ?? []).filter((u) => u.is_active && !u.is_admin && !u.features.length).length

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
        {(
          [
            ['all', 'Tất cả'],
            ['pending', `Chờ duyệt${pendingCount ? ` (${pendingCount})` : ''}`],
            ['locked', 'Bị khoá'],
          ] as const
        ).map(([value, label]) => (
          <button key={value} className={`tab ${filter === value ? 'active' : ''}`} onClick={() => setFilter(value)}>
            {label}
          </button>
        ))}
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
            <UserRow key={u.id} user={u} features={features} />
          ))}
        </div>
      )}
    </section>
  )
}

function UserRow({ user, features }: { user: AdminUser; features: FeatureInfo[] }) {
  const { data: me } = useMe()
  const update = useUpdateUser()
  const isSelf = me?.id === user.id
  const patch = (p: Parameters<typeof update.mutate>[0]['patch']) => update.mutate({ id: user.id, patch: p })
  const toggleFeature = (f: Feature) =>
    patch({ features: user.features.includes(f) ? user.features.filter((x) => x !== f) : [...user.features, f] })

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
          {!user.is_active && <span className="badge failed">Bị khoá</span>}
          {user.is_active && !user.is_admin && !user.features.length && <span className="badge pending">Chờ duyệt</span>}
        </div>
      </div>

      <div className="small muted">
        Tạo {timeAgo(user.created_at)} · {user.last_login_at ? `đăng nhập ${timeAgo(user.last_login_at)}` : 'chưa đăng nhập'}
        {Object.keys(user.usage_today).length > 0 &&
          ' · Hôm nay: ' +
            features
              .filter((f) => user.usage_today[f.value])
              .map((f) => `${f.label} ${user.usage_today[f.value]} ${f.unit}`)
              .join(', ')}
      </div>

      {user.is_admin ? (
        <span className="small muted">Admin dùng được mọi tính năng đang bật.</span>
      ) : (
        <FeatureChips
          features={features}
          selected={user.features}
          onToggle={toggleFeature}
          disabled={update.isPending || !user.is_active}
        />
      )}

      {update.error && <ErrorBox error={update.error} />}
      <div className="row" style={{ gap: 8, flexWrap: 'wrap' }}>
        {!user.is_admin && (
          <>
            <button
              className="btn sm"
              disabled={update.isPending || !user.is_active}
              onClick={() => patch({ features: features.map((f) => f.value) })}
            >
              Cấp tất cả
            </button>
            <button
              className="btn sm ghost"
              disabled={update.isPending || !user.is_active || !user.features.length}
              onClick={() => patch({ features: [] })}
            >
              Thu hồi tất cả
            </button>
          </>
        )}
        {!isSelf && (
          <>
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
          </>
        )}
      </div>
    </div>
  )
}

function FeatureChips(props: {
  features: FeatureInfo[]
  selected: Feature[]
  onToggle: (f: Feature) => void
  disabled?: boolean
}) {
  return (
    <div className="feature-chips">
      {props.features.map((f) => {
        const on = props.selected.includes(f.value)
        return (
          <button
            key={f.value}
            type="button"
            className={`feature-chip ${on ? 'on' : ''}`}
            aria-pressed={on}
            disabled={props.disabled}
            onClick={() => props.onToggle(f.value)}
          >
            <Icon name={on ? 'check' : 'plus'} size={14} /> {f.label}
          </button>
        )
      })}
    </div>
  )
}
