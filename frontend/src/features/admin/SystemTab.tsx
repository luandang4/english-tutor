import { useState } from 'react'

import { useAdminSystem, useSaveSystem } from '../../api/hooks'
import type { FeatureInfo, SystemSettings } from '../../api/types'
import { ErrorBox, Icon, Loading, Spinner } from '../../components/ui'

/** Global switches (emergency brake, applies to admins too), sign-up, and the "contact to upgrade" text. */
export function SystemTab({ features }: { features: FeatureInfo[] }) {
  const { data, error, isPending, refetch } = useAdminSystem()
  const save = useSaveSystem()
  const [draft, setDraft] = useState<SystemSettings | null>(null)
  const current = draft ?? data

  if (isPending) return <Loading />
  if (error || !current) return <ErrorBox error={error} onRetry={() => refetch()} />

  const update = (patch: Partial<SystemSettings>) => setDraft({ ...current, ...patch })

  return (
    <section className="card stack admin-section">
      <div className="card-title">
        <h3>Công tắc tính năng</h3>
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
                <small>
                  {current.features_enabled[f.value] ? 'Bật theo gói của từng người' : 'Đã tắt với tất cả, kể cả admin'}
                </small>
              </span>
            </label>
          </div>
        ))}
      </div>
      <p className="small muted">Tắt ở đây là phanh khẩn cấp. Giới hạn lượt dùng nằm trong từng gói (tab Gói).</p>

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
            <small>Người mới phải chờ admin chọn gói (trừ khi có gói được đánh dấu mặc định cho tài khoản mới).</small>
          </span>
        </label>
      </div>

      <label className="field">
        Thông tin liên hệ nâng gói
        <input
          className="input"
          maxLength={300}
          placeholder="Ví dụ: Zalo 09xx xxx xxx hoặc email admin@…"
          value={current.upgrade_contact}
          onChange={(e) => update({ upgrade_contact: e.target.value })}
        />
        <span className="small muted">Hiện cho người dùng khi hết lượt, hết hạn hoặc đang chờ duyệt.</span>
      </label>

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
