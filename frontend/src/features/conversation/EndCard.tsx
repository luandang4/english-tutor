import { Link } from 'react-router-dom'

export type EndReason = 'stopped' | 'time_limit' | 'error'

const TITLE: Record<EndReason, string> = {
  stopped: 'Buổi học đã kết thúc',
  time_limit: 'Hết giờ rồi, bạn làm tốt lắm!',
  error: 'Buổi học bị gián đoạn',
}
const TEXT: Record<EndReason, string> = {
  stopped: 'Cảm ơn bạn đã luyện nói cùng Emma.',
  time_limit: 'Buổi học đã dùng hết thời gian cho phép.',
  error: 'Kết nối với Emma bị ngắt. Bạn có thể bắt đầu lại ngay.',
}

/** Friendly end of a session (never a red error for a time limit). */
export function EndCard(props: { reason: EndReason; sessionId: number | null; saved: boolean; onNew: () => void }) {
  const { reason, sessionId, saved, onNew } = props
  return (
    <div className={`end-card ${reason}`}>
      <div className="end-emoji" aria-hidden="true">
        {reason === 'error' ? '🔌' : '🎉'}
      </div>
      <h3>{TITLE[reason]}</h3>
      <p className="muted">
        {TEXT[reason]} {saved && 'Lời thoại đã được lưu để bạn xem lại.'}
      </p>
      <div className="row end-actions">
        <button type="button" className="btn primary" onClick={onNew}>
          Buổi học mới
        </button>
        {saved && (
          <Link className="btn" to={sessionId ? `/conversation/history/${sessionId}` : '/conversation/history'}>
            Xem lại buổi học
          </Link>
        )}
      </div>
    </div>
  )
}
