import { useAdminUsage } from '../../api/hooks'
import { ErrorBox, Loading, ProgressBar } from '../../components/ui'

/** System totals of the current month, and Azure pronunciation use against its free tier. */
export function UsageTab() {
  const { data: r, error, isPending, refetch } = useAdminUsage()
  if (isPending) return <Loading />
  if (error || !r) return <ErrorBox error={error} onRetry={() => refetch()} />

  const [year, month] = r.month.split('-')
  const azurePct = (r.estimated_pronunciation_hours / r.azure_free_hours) * 100
  return (
    <div className="stack admin-section">
      <section className="card stack">
        <div className="card-title">
          <h3>
            Chấm phát âm (Azure) · tháng {Number(month)}/{year}
          </h3>
        </div>
        <div className="grid cols-2">
          <div className="stat">
            <span className="label">Lượt chấm phát âm</span>
            <span className="value">{r.pronunciation_assessments}</span>
            <span className="hint">Gồm trang phát âm và từng lượt nói trong hội thoại</span>
          </div>
          <div className="stat">
            <span className="label">Giờ âm thanh (ước tính)</span>
            <span className={`value ${azurePct >= 80 ? 'tone-low' : ''}`}>
              {r.estimated_pronunciation_hours} / {r.azure_free_hours} giờ
            </span>
            <span className="hint">Mức miễn phí Azure Speech (F0)</span>
          </div>
        </div>
        <ProgressBar value={azurePct} />
        <p className="small muted">
          Ứng dụng chưa đo độ dài âm thanh thật, nên số giờ là ước tính: số lượt × ~{r.seconds_per_assessment_estimate}{' '}
          giây. Xem số chính xác trong Azure Portal (Metrics của tài nguyên Speech). Vượt mức miễn phí thì Azure sẽ
          từ chối (gói F0) hoặc tính tiền (gói S0).
        </p>
      </section>

      <section className="card stack">
        <div className="card-title">
          <h3>Hội thoại (Gemini Live)</h3>
        </div>
        <div className="stat">
          <span className="label">Tổng phút hội thoại tháng này</span>
          <span className="value">{r.conversation_minutes} phút</span>
          <span className="hint">Không tính vào Azure; phần chấm phát âm trong hội thoại đã tính ở trên</span>
        </div>
      </section>

      <section className="card stack">
        <div className="card-title">
          <h3>Theo tính năng</h3>
        </div>
        <div className="admin-table-wrap">
          <table className="admin-table">
            <thead>
              <tr>
                <th>Tính năng</th>
                <th>Đã dùng</th>
                <th>Số request</th>
                <th>Người dùng</th>
              </tr>
            </thead>
            <tbody>
              {r.features.map((f) => (
                <tr key={f.feature}>
                  <td>{f.label}</td>
                  <td>
                    {f.units} {f.unit}
                  </td>
                  <td>{f.events}</td>
                  <td>{f.users}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  )
}
