import { Link, useNavigate, useParams } from 'react-router-dom'

import { useConversation, useConversations, useDeleteConversation, useMeta } from '../../api/hooks'
import { EmptyState, ErrorBox, Icon, Loading, PageHeader } from '../../components/ui'
import { formatDuration, timeAgo } from '../../lib/format'
import './conversation.css'

function useScenarioLabel() {
  const { data } = useMeta()
  return (key: string) => data?.scenarios.find((s) => s.value === key)?.label ?? key
}

export function ConversationHistoryPage() {
  const { data, error, isPending, refetch } = useConversations()
  const label = useScenarioLabel()
  return (
    <div className="page">
      <PageHeader
        title="Lịch sử hội thoại"
        subtitle="Xem lại transcript các buổi nói chuyện với Emma."
        back={{ to: '/conversation', label: 'Hội thoại' }}
      />
      {isPending ? (
        <Loading />
      ) : error ? (
        <ErrorBox error={error} onRetry={() => refetch()} />
      ) : data.length === 0 ? (
        <EmptyState
          emoji="🎙️"
          title="Chưa có buổi hội thoại nào"
          action={
            <Link className="btn primary" to="/conversation">
              Bắt đầu nói chuyện
            </Link>
          }
        />
      ) : (
        <div className="list">
          {data.map((c) => (
            <Link key={c.id} to={`/conversation/history/${c.id}`} className="list-item">
              <span className="icon">🎙️</span>
              <div className="body">
                <b>{label(c.scenario)}</b>
                <div className="meta">
                  <span className="badge level">{c.level}</span>
                  <span>{formatDuration(c.duration_seconds)}</span>
                  <span>· {c.turns} lượt nói</span>
                  <span>· {timeAgo(c.created_at)}</span>
                </div>
              </div>
              <Icon name="arrowRight" />
            </Link>
          ))}
        </div>
      )}
    </div>
  )
}

export function ConversationDetailPage() {
  const id = Number(useParams().id)
  const { data, error, isPending } = useConversation(id)
  const del = useDeleteConversation()
  const navigate = useNavigate()
  const label = useScenarioLabel()
  const back = { to: '/conversation/history', label: 'Lịch sử hội thoại' }

  if (isPending) return <div className="page"><Loading /></div>
  if (error || !data)
    return (
      <div className="page">
        <PageHeader title="Buổi hội thoại" back={back} />
        <ErrorBox error={error} />
      </div>
    )
  return (
    <div className="page">
      <PageHeader
        back={back}
        title={label(data.scenario)}
        subtitle={`${data.level} · giọng ${data.voice} · ${formatDuration(data.duration_seconds)} · ${new Date(data.created_at).toLocaleString('vi-VN')}`}
        actions={
          <button
            className="btn sm danger"
            onClick={() => confirm('Xoá buổi hội thoại này?') && del.mutate(id, { onSuccess: () => navigate(back.to) })}
          >
            <Icon name="trash" size={16} /> Xoá
          </button>
        }
      />
      <div className="card chat" style={{ maxWidth: 760 }}>
        {data.transcript.map((t, i) => (
          <div key={i} className={`msg ${t.role}`}>
            <span className="who">{t.role === 'tutor' ? 'Emma' : 'Bạn'}</span>
            {t.text}
          </div>
        ))}
      </div>
    </div>
  )
}
