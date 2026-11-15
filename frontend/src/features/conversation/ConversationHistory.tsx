import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'

import { useConversation, useConversations, useDeleteConversation, useMeta } from '../../api/hooks'
import type { ConversationSummary } from '../../api/types'
import { EmptyState, ErrorBox, Icon, Loading, PageHeader } from '../../components/ui'
import { formatDuration, timeAgo } from '../../lib/format'
import { RecapPanel, RecapView } from './RecapPanel'
import { TurnView } from './TurnView'
import { useDeckActions } from './useDeckActions'
import './conversation.css'

const ALL = '' // filter value: every scenario

function useScenarioLabel() {
  const { data } = useMeta()
  return (c: { scenario: string; topic: string | null }) =>
    c.scenario === 'custom' && c.topic ? `✨ ${c.topic}` : (data?.scenarios.find((s) => s.value === c.scenario)?.label ?? c.scenario)
}

/** Scenarios that appear in the learner's history, in first-seen order ("custom" grouped as one). */
function scenarioChoices(list: ConversationSummary[], label: (c: ConversationSummary) => string) {
  const seen = new Map<string, string>()
  for (const c of list) {
    if (!seen.has(c.scenario)) seen.set(c.scenario, c.scenario === 'custom' ? '✨ Tình huống của bạn' : label(c))
  }
  return [...seen]
}

export function ConversationHistoryPage() {
  const { data, error, isPending, refetch } = useConversations()
  const label = useScenarioLabel()
  const [filter, setFilter] = useState(ALL)
  const shown = data?.filter((c) => filter === ALL || c.scenario === filter) ?? []
  const choices = data ? scenarioChoices(data, label) : []
  return (
    <div className="page">
      <PageHeader
        title="Lịch sử hội thoại"
        subtitle="Xem lại transcript các buổi nói chuyện với Emma."
        back={{ to: '/conversation', label: 'Hội thoại' }}
        actions={
          choices.length > 1 && (
            <label className="field history-filter">
              Tình huống
              <select className="select" value={filter} onChange={(e) => setFilter(e.target.value)}>
                <option value={ALL}>Tất cả</option>
                {choices.map(([value, text]) => (
                  <option key={value} value={value}>
                    {text}
                  </option>
                ))}
              </select>
            </label>
          )
        }
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
          {shown.map((c) => (
            <Link key={c.id} to={`/conversation/history/${c.id}`} className="list-item">
              <span className="icon">🎙️</span>
              <div className="body">
                <b>{label(c)}</b>
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
  const deck = useDeckActions()
  const [wantRecap, setWantRecap] = useState(false)
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
        title={label(data)}
        subtitle={`${data.level} · ${formatDuration(data.duration_seconds)} · ${new Date(data.created_at).toLocaleString('vi-VN')}`}
        actions={
          <button
            className="btn sm danger"
            onClick={() => confirm('Xoá buổi hội thoại này?') && del.mutate(id, { onSuccess: () => navigate(back.to) })}
          >
            <Icon name="trash" size={16} /> Xoá
          </button>
        }
      />
      {data.summary ? (
        <RecapView recap={data.summary} />
      ) : wantRecap ? (
        <RecapPanel sessionId={id} />
      ) : (
        <div>
          <button className="btn sm primary" onClick={() => setWantRecap(true)}>
            <Icon name="sparkle" size={16} /> Xem tổng kết buổi học
          </button>
        </div>
      )}
      <div className="card chat history-chat">
        {data.transcript.map((t, i) => (
          <TurnView key={i} turn={t} onSaveFeedback={deck.onSaveFeedback} onAddWord={deck.onAddWord} />
        ))}
      </div>
    </div>
  )
}
