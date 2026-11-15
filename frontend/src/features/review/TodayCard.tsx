import { Link } from 'react-router-dom'

import { useForecast } from '../../api/hooks'
import { Icon } from '../../components/ui'
import './review.css'

const WEEKDAY = ['CN', 'T2', 'T3', 'T4', 'T5', 'T6', 'T7']

/** Dashboard "Hôm nay": cards due now, estimated time, 7-day forecast and grammar re-checks due. */
export function TodayCard() {
  const { data } = useForecast()
  if (!data) return null
  const upcoming = data.days.reduce((sum, d) => sum + d.count, 0)
  if (!upcoming && !data.grammar.length) return null
  const max = Math.max(1, ...data.days.map((d) => d.count))

  return (
    <section className="card stack">
      <div className="card-title" style={{ marginBottom: 0 }}>
        <h2>📅 Hôm nay</h2>
        <Link className="small" to="/review">
          Ôn tập <Icon name="arrowRight" size={14} />
        </Link>
      </div>
      <div className="today">
        <div className="stack" style={{ gap: 8 }}>
          {data.due > 0 ? (
            <>
              <span className="big">
                Ôn {data.due} từ, khoảng {data.minutes} phút
              </span>
              <div>
                <Link className="btn primary sm" to="/review">
                  <Icon name="cards" size={16} /> Ôn ngay
                </Link>
              </div>
            </>
          ) : (
            <>
              <span className="big">Không còn từ cần ôn 🎉</span>
              <span className="small muted">Muốn luyện thêm? Vào Ôn tập để ôn từ sắp đến hạn hoặc từ khó.</span>
            </>
          )}
        </div>
        <div className="forecast" aria-label="Số từ cần ôn 7 ngày tới">
          {data.days.map((d, i) => (
            <div key={d.date} className={`day ${i === 0 ? 'today' : ''}`} title={`${d.date}: ${d.count} từ`}>
              <span className="count">{d.count || ''}</span>
              <div className="bar-box">
                <div className={`bar ${d.count ? '' : 'empty'}`} style={{ height: `${(d.count / max) * 100}%` }} />
              </div>
              <span className="label">{i === 0 ? 'Nay' : WEEKDAY[new Date(`${d.date}T00:00:00`).getDay()]}</span>
            </div>
          ))}
        </div>
      </div>
      {data.grammar.length > 0 && (
        <div className="list">
          {data.grammar.map((g) => (
            <Link key={g.lesson_id} to={`/grammar/lessons/${g.lesson_id}/quiz`} className="list-item" style={{ padding: '10px 12px' }}>
              <span className="icon" style={{ width: 34, height: 34, fontSize: '1rem' }}>
                🧩
              </span>
              <div className="body">
                <b style={{ fontSize: '0.9rem' }}>Ôn ngữ pháp: {g.title}</b>
                <div className="meta">Kiểm tra lại lần {g.step + 1}/4</div>
              </div>
              <Icon name="arrowRight" size={16} />
            </Link>
          ))}
        </div>
      )}
    </section>
  )
}
