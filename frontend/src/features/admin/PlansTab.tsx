import { useState } from 'react'

import { useAdminPlans, useSavePlan } from '../../api/hooks'
import type { BillingCycle, Feature, FeatureInfo, Plan, PlanInput, PlanLimit } from '../../api/types'
import { EmptyState, ErrorBox, Icon, Loading, Spinner } from '../../components/ui'

const CYCLE_LABEL: Record<BillingCycle, string> = { monthly: 'Hằng tháng', quarterly: 'Hằng quý', yearly: 'Hằng năm' }
const MAX_LIMIT = 100000

const EMPTY_PLAN: PlanInput = {
  code: '',
  name: '',
  description: '',
  features: [],
  limits: {},
  max_session_minutes: null,
  duration_days: 30,
  is_default_for_new: false,
  is_active: true,
  sort_order: 10,
  price_label: '',
  billing_cycle: null,
}

/** Create / edit / deactivate plans; how many users are on each. */
export function PlansTab({ features }: { features: FeatureInfo[] }) {
  const { data: plans, error, isPending, refetch } = useAdminPlans()
  const [editing, setEditing] = useState<number | 'new' | null>(null)

  if (isPending) return <Loading />
  if (error || !plans) return <ErrorBox error={error} onRetry={() => refetch()} />

  return (
    <div className="stack admin-section">
      <div className="row">
        <p className="small muted spacer">
          Sửa gói áp dụng ngay cho mọi người đang dùng gói đó. Ngừng gói = không gán cho ai mới nữa, người đang dùng vẫn
          giữ tới khi hết hạn. 0 = không giới hạn.
        </p>
        {editing !== 'new' && (
          <button className="btn primary sm" onClick={() => setEditing('new')}>
            <Icon name="plus" size={14} /> Tạo gói mới
          </button>
        )}
      </div>
      {editing === 'new' && <PlanForm features={features} plan={null} onDone={() => setEditing(null)} />}
      {plans.length === 0 && <EmptyState emoji="📦" title="Chưa có gói nào" />}
      {plans.map((p) =>
        editing === p.id ? (
          <PlanForm key={p.id} features={features} plan={p} onDone={() => setEditing(null)} />
        ) : (
          <PlanCard key={p.id} plan={p} features={features} onEdit={() => setEditing(p.id)} />
        ),
      )}
    </div>
  )
}

function limitText(limit: PlanLimit | undefined, unit: string): string {
  const parts = []
  if (limit?.daily) parts.push(`${limit.daily} ${unit}/ngày`)
  if (limit?.monthly) parts.push(`${limit.monthly} ${unit}/tháng`)
  return parts.length ? parts.join(', ') : 'không giới hạn'
}

function PlanCard({ plan, features, onEdit }: { plan: Plan; features: FeatureInfo[]; onEdit: () => void }) {
  return (
    <section className={`card stack plan-card ${plan.is_active ? '' : 'inactive'}`}>
      <div className="row" style={{ flexWrap: 'wrap', gap: 8 }}>
        <h3 className="spacer">
          {plan.name} <span className="small muted">({plan.code})</span>
        </h3>
        {!plan.is_active && <span className="badge failed">Đã ngừng</span>}
        {plan.is_default_for_new && <span className="badge ready">Mặc định cho tài khoản mới</span>}
        <span className="badge level">{plan.active_users} người đang dùng</span>
        <button className="btn sm ghost" onClick={onEdit}>
          Sửa
        </button>
      </div>
      {plan.description && <p className="small muted">{plan.description}</p>}
      <div className="small muted">
        {plan.duration_days ? `Hạn mặc định ${plan.duration_days} ngày` : 'Không hết hạn'}
        {plan.max_session_minutes ? ` · tối đa ${plan.max_session_minutes} phút / buổi hội thoại` : ''}
        {plan.price_label ? ` · ${plan.price_label}` : ''}
        {plan.billing_cycle ? ` · ${CYCLE_LABEL[plan.billing_cycle]}` : ''}
      </div>
      <ul className="plan-limits">
        {features.map((f) => (
          <li key={f.value} className={plan.features.includes(f.value) ? '' : 'off'}>
            <b>{f.label}</b>
            <span>{plan.features.includes(f.value) ? limitText(plan.limits[f.value], f.unit) : 'không có'}</span>
          </li>
        ))}
      </ul>
    </section>
  )
}

function numberOrNull(value: string): number | null {
  return value.trim() === '' ? null : Math.max(0, Math.floor(Number(value)))
}

function PlanForm({ features, plan, onDone }: { features: FeatureInfo[]; plan: Plan | null; onDone: () => void }) {
  const save = useSavePlan()
  const [draft, setDraft] = useState<PlanInput>(() => (plan ? toInput(plan) : EMPTY_PLAN))
  const update = (patch: Partial<PlanInput>) => setDraft((d) => ({ ...d, ...patch }))
  const toggleFeature = (f: Feature, on: boolean) =>
    update({ features: on ? [...draft.features, f] : draft.features.filter((x) => x !== f) })
  const setLimit = (f: Feature, key: keyof PlanLimit, value: number) =>
    update({
      limits: {
        ...draft.limits,
        [f]: { daily: 0, monthly: 0, ...draft.limits[f], [key]: Math.min(MAX_LIMIT, Math.max(0, value)) },
      },
    })

  return (
    <form
      className="card stack plan-form"
      onSubmit={(e) => {
        e.preventDefault()
        save.mutate({ id: plan?.id ?? null, plan: draft }, { onSuccess: onDone })
      }}
    >
      <h3>{plan ? `Sửa gói ${plan.name}` : 'Gói mới'}</h3>
      <div className="plan-form-grid">
        <label className="field">
          Tên gói
          <input className="input" required maxLength={80} value={draft.name} onChange={(e) => update({ name: e.target.value })} />
        </label>
        <label className="field">
          Mã (chữ thường, số, gạch ngang)
          <input
            className="input"
            required
            pattern="[a-z0-9][a-z0-9\-]{1,39}"
            value={draft.code}
            onChange={(e) => update({ code: e.target.value.toLowerCase() })}
          />
        </label>
        <label className="field">
          Hạn mặc định (ngày, trống = không hết hạn)
          <input
            className="input"
            type="number"
            min={1}
            max={3650}
            value={draft.duration_days ?? ''}
            onChange={(e) => update({ duration_days: numberOrNull(e.target.value) })}
          />
        </label>
        <label className="field">
          Phút tối đa mỗi buổi hội thoại (trống = mặc định máy chủ)
          <input
            className="input"
            type="number"
            min={1}
            max={180}
            value={draft.max_session_minutes ?? ''}
            onChange={(e) => update({ max_session_minutes: numberOrNull(e.target.value) })}
          />
        </label>
        <label className="field">
          Nhãn giá (chỉ hiển thị)
          <input
            className="input"
            maxLength={80}
            placeholder="Miễn phí, 99.000đ / tháng…"
            value={draft.price_label}
            onChange={(e) => update({ price_label: e.target.value })}
          />
        </label>
        <label className="field">
          Chu kỳ
          <select
            className="select"
            value={draft.billing_cycle ?? ''}
            onChange={(e) => update({ billing_cycle: (e.target.value || null) as BillingCycle | null })}
          >
            <option value="">Không</option>
            {Object.entries(CYCLE_LABEL).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          Thứ tự hiển thị
          <input
            className="input"
            type="number"
            min={0}
            max={1000}
            value={draft.sort_order}
            onChange={(e) => update({ sort_order: Math.max(0, Number(e.target.value)) })}
          />
        </label>
      </div>
      <label className="field">
        Mô tả
        <input
          className="input"
          maxLength={500}
          value={draft.description}
          onChange={(e) => update({ description: e.target.value })}
        />
      </label>

      <div className="stack" style={{ gap: 8 }}>
        <b className="small">Tính năng và giới hạn (0 = không giới hạn)</b>
        {features.map((f) => {
          const on = draft.features.includes(f.value)
          const limit = draft.limits[f.value]
          return (
            <div key={f.value} className={`plan-feature-row ${on ? '' : 'off'}`}>
              <label className="toggle">
                <input type="checkbox" checked={on} onChange={(e) => toggleFeature(f.value, e.target.checked)} />
                <span className="switch" aria-hidden="true" />
                <span>{f.label}</span>
              </label>
              <label className="field">
                {f.unit} / ngày
                <input
                  className="input"
                  type="number"
                  min={0}
                  max={MAX_LIMIT}
                  disabled={!on}
                  value={limit?.daily ?? 0}
                  onChange={(e) => setLimit(f.value, 'daily', Number(e.target.value))}
                />
              </label>
              <label className="field">
                {f.unit} / tháng
                <input
                  className="input"
                  type="number"
                  min={0}
                  max={MAX_LIMIT}
                  disabled={!on}
                  value={limit?.monthly ?? 0}
                  onChange={(e) => setLimit(f.value, 'monthly', Number(e.target.value))}
                />
              </label>
            </div>
          )
        })}
      </div>

      <label className="toggle">
        <input type="checkbox" checked={draft.is_active} onChange={(e) => update({ is_active: e.target.checked })} />
        <span className="switch" aria-hidden="true" />
        <span>
          Đang dùng
          <small>Tắt = ngừng gói: không gán cho người mới, người đang dùng vẫn giữ.</small>
        </span>
      </label>
      <label className="toggle">
        <input
          type="checkbox"
          checked={draft.is_default_for_new}
          onChange={(e) => update({ is_default_for_new: e.target.checked })}
        />
        <span className="switch" aria-hidden="true" />
        <span>
          Mặc định cho tài khoản mới
          <small>Người tự đăng ký được dùng gói này ngay, không cần chờ duyệt. Để tắt nếu muốn duyệt từng người.</small>
        </span>
      </label>

      {save.error && <ErrorBox error={save.error} />}
      <div className="row">
        <button className="btn primary" type="submit" disabled={save.isPending}>
          {save.isPending ? <Spinner small /> : <Icon name="check" size={16} />} {plan ? 'Lưu gói' : 'Tạo gói'}
        </button>
        <button className="btn ghost" type="button" onClick={onDone}>
          Huỷ
        </button>
      </div>
    </form>
  )
}

function toInput(plan: Plan): PlanInput {
  const { id: _id, active_users: _users, ...input } = plan
  return input
}
