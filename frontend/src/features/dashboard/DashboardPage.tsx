import { Link } from 'react-router-dom'

import { useMe, useProgress } from '../../api/hooks'
import type { Skill } from '../../api/types'
import { ErrorBox, Icon, Loading, type IconName } from '../../components/ui'
import { SKILL_LABEL, scoreTone, timeAgo } from '../../lib/format'

const QUICK: { to: string; icon: IconName; title: string; text: string; color: string }[] = [
  { to: '/conversation', icon: 'mic', title: 'Hội thoại', text: 'Nói chuyện với Emma bằng giọng nói', color: '#ff7ac8' },
  { to: '/vocabulary', icon: 'book', title: 'Từ vựng', text: 'Học 10 từ mới theo chủ đề', color: '#b794ff' },
  { to: '/grammar', icon: 'grammar', title: 'Ngữ pháp', text: 'Giải thích dễ hiểu + bài tập', color: '#5ef0ff' },
  { to: '/writing', icon: 'pen', title: 'Luyện viết', text: 'AI ra đề và chấm chi tiết', color: '#ff8fab' },
]

const KIND_ICON: Record<string, string> = { vocabulary: '📖', grammar: '🧩', writing: '✍️', conversation: '🎙️' }

function greeting(): string {
  const h = new Date().getHours()
  if (h < 11) return 'Chào buổi sáng'
  if (h < 14) return 'Chào buổi trưa'
  if (h < 18) return 'Chào buổi chiều'
  return 'Chào buổi tối'
}

export function DashboardPage() {
  const { data: p, error, isPending, refetch } = useProgress()
  const { data: me } = useMe()

  return (
    <div className="page">
      <section className="hero">
        {me && (
          <Link to="/account" className="mobile-account avatar" aria-label="Tài khoản" style={{ position: 'absolute', top: 14, right: 14 }}>
            {me.display_name.charAt(0).toUpperCase()}
          </Link>
        )}
        <div>
          <h1>
            {greeting()}
            {me ? `, ${me.display_name}` : ''}! <span className="gradient-text">Hôm nay học gì nhỉ?</span>
          </h1>
          <p>Mỗi ngày một chút: nói 10 phút, ôn từ, làm một bài ngữ pháp hoặc viết một đoạn ngắn.</p>
        </div>
        {p && (
          <div className="streak">
            <b className="gradient-text">{p.streak_days}</b>
            <span className="small muted">🔥 ngày liên tiếp</span>
          </div>
        )}
      </section>

      <div className="grid cols-4">
        {QUICK.map((q) => (
          <Link key={q.to} to={q.to} className="quick">
            <span className="q-icon" style={{ background: `${q.color}22`, color: q.color }}>
              <Icon name={q.icon} />
            </span>
            <h3>{q.title}</h3>
            <p>{q.text}</p>
          </Link>
        ))}
      </div>

      {isPending ? (
        <Loading />
      ) : error ? (
        <ErrorBox error={error} onRetry={() => refetch()} />
      ) : (
        <>
          {p.deck.due > 0 && (
            <Link to="/review" className="alert info row">
              <Icon name="cards" />
              <span className="spacer">
                Có <b>{p.deck.due}</b> từ cần ôn hôm nay — ôn ngay để không quên nhé.
              </span>
              <Icon name="arrowRight" />
            </Link>
          )}

          <div className="grid cols-4">
            <div className="card stat">
              <span className="label">Từ trong bộ ôn tập</span>
              <span className="value">{p.deck.total}</span>
              <span className="hint">
                {p.deck.mature} đã thuộc · {p.deck.reviewed_today} lượt ôn hôm nay
              </span>
            </div>
            <div className="card stat">
              <span className="label">Thời gian hội thoại</span>
              <span className="value">{p.conversation_minutes} phút</span>
              <span className="hint">{p.conversation_count} buổi</span>
            </div>
            <div className="card stat">
              <span className="label">Điểm viết trung bình</span>
              <span className={`value tone-${scoreTone(p.writing_average)}`}>{p.writing_average ?? '–'}</span>
              <span className="hint">thang 100</span>
            </div>
            <div className="card stat">
              <span className="label">Điểm phát âm TB</span>
              <span className={`value tone-${scoreTone(p.pronunciation_average)}`}>{p.pronunciation_average ?? '–'}</span>
              <span className="hint">Azure Speech</span>
            </div>
          </div>

          <div className="grid cols-2">
            <div className="card">
              <div className="card-title">
                <h2>Tiến độ theo kỹ năng</h2>
              </div>
              <div className="stack">
                {p.skills.map((s) => (
                  <Link key={s.skill} to={`/${s.skill}`} className="list-item">
                    <span className="icon">{KIND_ICON[s.skill]}</span>
                    <div className="body">
                      <b>{SKILL_LABEL[s.skill as Skill]}</b>
                      <div className="meta">
                        <span>{s.completed} hoàn thành</span>
                        <span>· {s.in_progress} đang học</span>
                      </div>
                    </div>
                    <span className={`score tone-${scoreTone(s.average_score)}`}>{s.average_score ?? '–'}</span>
                  </Link>
                ))}
              </div>
            </div>

            <div className="card">
              <div className="card-title">
                <h2>Hoạt động 4 tuần</h2>
                <span className="small muted">{p.active_days_30} ngày học / 30 ngày</span>
              </div>
              <div className="heatmap">
                {p.activity.map((d) => (
                  <span
                    key={d.date}
                    data-l={d.count === 0 ? 0 : d.count < 5 ? 1 : d.count < 15 ? 2 : d.count < 30 ? 3 : 4}
                    title={`${new Date(d.date).toLocaleDateString('vi-VN')}: ${d.count} hoạt động`}
                  />
                ))}
              </div>
              <div className="card-title" style={{ marginTop: 22 }}>
                <h2>Gần đây</h2>
              </div>
              {p.recent.length === 0 ? (
                <p className="muted small">Chưa có hoạt động. Bắt đầu với một bài học bất kỳ ở trên nhé!</p>
              ) : (
                <div className="list">
                  {p.recent.slice(0, 6).map((r, i) => (
                    <Link key={i} to={r.link} className="list-item" style={{ padding: '10px 12px' }}>
                      <span className="icon" style={{ width: 34, height: 34, fontSize: '1rem' }}>
                        {KIND_ICON[r.kind] ?? '•'}
                      </span>
                      <div className="body">
                        <b style={{ fontSize: '0.9rem' }}>{r.title}</b>
                        <div className="meta">{timeAgo(r.at)}</div>
                      </div>
                      {r.score != null && <span className={`score tone-${scoreTone(r.score)}`}>{Math.round(r.score)}</span>}
                    </Link>
                  ))}
                </div>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  )
}
