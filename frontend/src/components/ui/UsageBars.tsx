import type { FeatureUsage } from '../../api/types'
import { ProgressBar } from './index'
import './usage.css'

/** Day / month usage of each feature against its limits (null limit = unlimited). */
export function UsageBars({ usage, compact }: { usage: FeatureUsage[]; compact?: boolean }) {
  if (!usage.length) return null
  return (
    <div className={`usage-grid ${compact ? 'compact' : ''}`}>
      {usage.map((u) => (
        <div key={u.feature} className="usage-item">
          <b className="small">{u.label}</b>
          <UsageLine label="Hôm nay" used={u.used} limit={u.limit} unit={u.unit} />
          <UsageLine label="Tháng này" used={u.used_month} limit={u.limit_month} unit={u.unit} />
        </div>
      ))}
    </div>
  )
}

function UsageLine({ label, used, limit, unit }: { label: string; used: number; limit: number | null; unit: string }) {
  const pct = limit ? Math.min(100, (used / limit) * 100) : 0
  return (
    <div className="usage-line">
      <div className="row small">
        <span className="spacer muted">{label}</span>
        <span className={limit != null && used >= limit ? 'tone-low' : ''}>
          {limit == null ? `${used} ${unit} · không giới hạn` : `${used}/${limit} ${unit}`}
        </span>
      </div>
      {limit != null && <ProgressBar value={pct} />}
    </div>
  )
}
