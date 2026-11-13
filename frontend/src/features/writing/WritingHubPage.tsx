import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { useCreateWritingTask, useDeleteWritingTask, useTopics, useWritingTasks } from '../../api/hooks'
import type { Topic } from '../../api/types'
import { EmptyState, ErrorBox, Icon, LevelSelect, Loading, PageHeader, StatusBadge } from '../../components/ui'
import { scoreTone, timeAgo } from '../../lib/format'
import { useLevel } from '../../lib/preferences'
import { TopicGrid } from '../lessons/TopicGrid'

export function WritingHubPage() {
  const [tab, setTab] = useState<'topics' | 'mine'>('topics')
  const [level, setLevel] = useLevel()
  const topics = useTopics('writing')
  const tasks = useWritingTasks()
  const create = useCreateWritingTask()
  const del = useDeleteWritingTask()
  const [busyId, setBusyId] = useState<number | null>(null)
  const navigate = useNavigate()

  const pick = (topic: Topic) => {
    setBusyId(topic.id)
    create.mutate(
      { topic_id: topic.id, level },
      { onSuccess: (t) => navigate(`/writing/tasks/${t.id}`), onSettled: () => setBusyId(null) },
    )
  }

  return (
    <div className="page">
      <PageHeader
        title="Luyện viết"
        subtitle="Chọn dạng bài — AI ra đề, gợi ý dàn ý & cụm từ. Viết xong, Gemini chấm theo 4 tiêu chí và sửa từng lỗi."
        actions={
          <div style={{ minWidth: 200 }}>
            <LevelSelect value={level} onChange={setLevel} />
          </div>
        }
      />
      <div className="tabs">
        <button className={`tab ${tab === 'topics' ? 'active' : ''}`} onClick={() => setTab('topics')}>
          Dạng bài
        </button>
        <button className={`tab ${tab === 'mine' ? 'active' : ''}`} onClick={() => setTab('mine')}>
          Bài viết của tôi {tasks.data?.length ? `(${tasks.data.length})` : ''}
        </button>
      </div>
      {create.error && <ErrorBox error={create.error} />}

      {tab === 'topics' &&
        (topics.isPending ? (
          <Loading />
        ) : topics.error ? (
          <ErrorBox error={topics.error} onRetry={() => topics.refetch()} />
        ) : (
          <TopicGrid topics={topics.data} busyId={busyId} onPick={pick} />
        ))}

      {tab === 'mine' &&
        (tasks.isPending ? (
          <Loading />
        ) : tasks.error ? (
          <ErrorBox error={tasks.error} onRetry={() => tasks.refetch()} />
        ) : tasks.data.length === 0 ? (
          <EmptyState
            emoji="✍️"
            title="Chưa có bài viết nào"
            text="Chọn một dạng bài để AI ra đề cho bạn."
            action={
              <button className="btn primary" onClick={() => setTab('topics')}>
                Chọn dạng bài
              </button>
            }
          />
        ) : (
          <div className="list">
            {tasks.data.map((t) => (
              <Link key={t.id} to={`/writing/tasks/${t.id}`} className="list-item">
                <span className="icon">{t.topic.icon}</span>
                <div className="body">
                  <b>{t.title}</b>
                  <div className="meta">
                    <span className="badge level">{t.level}</span>
                    <StatusBadge status={t.status} />
                    <span>{t.topic.title_vi}</span>
                    <span>· {t.submission_count} lần nộp</span>
                    <span>· {timeAgo(t.created_at)}</span>
                  </div>
                </div>
                {t.best_score != null && <span className={`score tone-${scoreTone(t.best_score)}`}>{t.best_score}</span>}
                <button
                  className="btn icon sm ghost danger"
                  aria-label="Xoá bài viết"
                  onClick={(e) => {
                    e.preventDefault()
                    if (confirm(`Xoá "${t.title}" và các bài đã nộp?`)) del.mutate(t.id)
                  }}
                >
                  <Icon name="trash" />
                </button>
              </Link>
            ))}
          </div>
        ))}
    </div>
  )
}
