import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { useCreateLesson, useDeleteLesson, useLessons, useTopics } from '../../api/hooks'
import type { LessonSummary, Skill, Topic } from '../../api/types'
import {
  EmptyState,
  ErrorBox,
  Icon,
  LevelSelect,
  Loading,
  PageHeader,
  ProgressBar,
  StatusBadge,
} from '../../components/ui'
import { scoreTone, timeAgo } from '../../lib/format'
import { useLevel } from '../../lib/preferences'
import { TopicGrid } from './TopicGrid'

const COPY: Record<Exclude<Skill, 'writing'>, { title: string; subtitle: string; empty: string }> = {
  vocabulary: {
    title: 'Từ vựng',
    subtitle: 'Chọn chủ đề — AI soạn 10 từ mới kèm phát âm, ví dụ và bài tập. Từ đã học sẽ vào bộ ôn tập.',
    empty: 'Chưa có bài từ vựng nào',
  },
  grammar: {
    title: 'Ngữ pháp',
    subtitle: 'Chọn điểm ngữ pháp — AI giải thích bằng tiếng Việt, chỉ lỗi hay gặp và cho bài tập có chấm điểm.',
    empty: 'Chưa có bài ngữ pháp nào',
  },
}

export function LessonHubPage({ skill }: { skill: 'vocabulary' | 'grammar' }) {
  const copy = COPY[skill]
  const [tab, setTab] = useState<'topics' | 'mine'>('topics')
  const [level, setLevel] = useLevel()
  const topics = useTopics(skill)
  const lessons = useLessons(skill)
  const create = useCreateLesson()
  const [busyId, setBusyId] = useState<number | null>(null)
  const navigate = useNavigate()

  const pick = (topic: Topic) => {
    setBusyId(topic.id)
    create.mutate(
      { topic_id: topic.id, level },
      {
        onSuccess: (lesson) => navigate(`/${skill}/lessons/${lesson.id}`),
        onSettled: () => setBusyId(null),
      },
    )
  }

  return (
    <div className="page">
      <PageHeader
        title={copy.title}
        subtitle={copy.subtitle}
        actions={
          <div style={{ minWidth: 200 }}>
            <LevelSelect value={level} onChange={setLevel} />
          </div>
        }
      />
      <div className="row">
        <div className="tabs" role="tablist">
          <button className={`tab ${tab === 'topics' ? 'active' : ''}`} onClick={() => setTab('topics')}>
            Chủ đề
          </button>
          <button className={`tab ${tab === 'mine' ? 'active' : ''}`} onClick={() => setTab('mine')}>
            Bài học của tôi {lessons.data?.length ? `(${lessons.data.length})` : ''}
          </button>
        </div>
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
        (lessons.isPending ? (
          <Loading />
        ) : lessons.error ? (
          <ErrorBox error={lessons.error} onRetry={() => lessons.refetch()} />
        ) : lessons.data.length === 0 ? (
          <EmptyState
            emoji="📚"
            title={copy.empty}
            text="Chọn một chủ đề để AI tạo bài học đầu tiên cho bạn."
            action={
              <button className="btn primary" onClick={() => setTab('topics')}>
                Chọn chủ đề
              </button>
            }
          />
        ) : (
          <LessonList skill={skill} lessons={lessons.data} />
        ))}
    </div>
  )
}

function LessonList({ skill, lessons }: { skill: Skill; lessons: LessonSummary[] }) {
  const del = useDeleteLesson(skill)
  return (
    <div className="list">
      {lessons.map((l) => {
        const pct = l.exercise_count ? (l.answered_count / l.exercise_count) * 100 : 0
        return (
          <Link key={l.id} to={`/${skill}/lessons/${l.id}`} className="list-item">
            <span className="icon">{l.topic.icon}</span>
            <div className="body">
              <b>{l.title}</b>
              <div className="meta">
                <span className="badge level">{l.level}</span>
                <StatusBadge status={l.status} />
                <span>{l.topic.title_vi}</span>
                <span>· {timeAgo(l.created_at)}</span>
              </div>
              {l.status === 'ready' && (
                <div style={{ marginTop: 8, maxWidth: 260 }}>
                  <ProgressBar value={pct} />
                </div>
              )}
            </div>
            {l.score != null && <span className={`score tone-${scoreTone(l.score)}`}>{Math.round(l.score)}</span>}
            <button
              className="btn icon sm ghost danger"
              aria-label="Xoá bài học"
              title="Xoá bài học"
              onClick={(e) => {
                e.preventDefault()
                if (confirm(`Xoá bài "${l.title}"?`)) del.mutate(l.id)
              }}
            >
              <Icon name="trash" />
            </button>
          </Link>
        )
      })}
    </div>
  )
}
