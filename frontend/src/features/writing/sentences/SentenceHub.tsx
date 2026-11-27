import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import {
  useCreateSentenceSet,
  useDeleteSentenceSet,
  useDueCount,
  useLessons,
  useSentenceSets,
  useTopics,
} from '../../../api/hooks'
import type { CustomTopic, LessonStatus, Level, SentenceSetCreate, SentenceSource, Topic } from '../../../api/types'
import { EmptyState, ErrorBox, Icon, Loading, StatusBadge } from '../../../components/ui'
import { Segmented } from '../../../components/ui/Segmented'
import { scoreTone, timeAgo } from '../../../lib/format'
import { CustomTopicForm } from '../../lessons/CustomTopicForm'
import { TopicGrid } from '../../lessons/TopicGrid'
import { SOURCE_LABEL } from './model'
import './sentences.css'

const SOURCES: { value: SentenceSource; label: string; title: string }[] = [
  { value: 'lesson', label: 'Từ bài học', title: 'Câu dùng từ vựng / ngữ pháp của một bài đã học' },
  { value: 'deck', label: 'Ôn deck', title: 'Câu dùng các từ sắp đến hạn ôn' },
  { value: 'topic', label: 'Chủ đề', title: 'Câu theo một chủ đề có sẵn hoặc tự nhập' },
]

/** "Dịch câu" tab of Writing: start a set of 10 Vietnamese sentences to write in English, and past sets. */
export function SentenceHub({ level }: { level: Level }) {
  const [source, setSource] = useState<SentenceSource>('lesson')
  const create = useCreateSentenceSet()
  const sets = useSentenceSets()
  const navigate = useNavigate()

  const start = (body: SentenceSetCreate) =>
    create.mutate(body, { onSuccess: (row) => navigate(`/writing/sentences/${row.id}`) })

  return (
    <div className="stack">
      <section className="card sp-sources">
        <div>
          <h3>Luyện viết câu</h3>
          <p className="small muted">
            AI ra 10 câu tiếng Việt, bạn viết lại bằng tiếng Anh. Mỗi câu được chấm ngay: sửa lỗi, giải thích và cách
            nói tự nhiên hơn. Cách viết khác đáp án nhưng đúng vẫn được tính đúng.
          </p>
        </div>
        <Segmented label="Nguồn câu" value={source} options={SOURCES} onChange={setSource} />
        {source === 'lesson' && <LessonSource level={level} busy={create.isPending} onStart={start} />}
        {source === 'deck' && <DeckSource level={level} busy={create.isPending} onStart={start} />}
        {source === 'topic' && <TopicSource level={level} busy={create.isPending} onStart={start} />}
        {create.error && <ErrorBox error={create.error} />}
      </section>

      <h3>Bộ câu của tôi</h3>
      <SetList sets={sets} />
    </div>
  )
}

type SourceProps = { level: Level; busy: boolean; onStart: (body: SentenceSetCreate) => void }

function LessonSource({ level, busy, onStart }: SourceProps) {
  const vocab = useLessons('vocabulary')
  const grammar = useLessons('grammar')
  const ready = (s: LessonStatus) => s === 'ready' || s === 'completed'
  const groups = [
    { label: 'Từ vựng', lessons: (vocab.data ?? []).filter((l) => ready(l.status)) },
    { label: 'Ngữ pháp', lessons: (grammar.data ?? []).filter((l) => ready(l.status)) },
  ]
  const first = groups.flatMap((g) => g.lessons)[0]?.id
  const [picked, setPicked] = useState<number | null>(null)
  const lessonId = picked ?? first ?? null

  if (vocab.isPending || grammar.isPending) return <Loading />
  if (lessonId == null)
    return <p className="small muted">Bạn chưa có bài học nào. Hãy học một bài từ vựng hoặc ngữ pháp trước.</p>
  return (
    <div className="row" style={{ gap: 10, flexWrap: 'wrap', alignItems: 'flex-end' }}>
      <label className="field spacer" style={{ minWidth: 220 }}>
        <span>Bài học</span>
        <select className="select" value={lessonId} onChange={(e) => setPicked(Number(e.target.value))}>
          {groups.map(
            (g) =>
              g.lessons.length > 0 && (
                <optgroup key={g.label} label={g.label}>
                  {g.lessons.map((l) => (
                    <option key={l.id} value={l.id}>
                      {l.title} ({l.level})
                    </option>
                  ))}
                </optgroup>
              ),
          )}
        </select>
      </label>
      <button className="btn primary" disabled={busy} onClick={() => onStart({ source: 'lesson', lesson_id: lessonId, level })}>
        Tạo 10 câu
      </button>
    </div>
  )
}

function DeckSource({ level, busy, onStart }: SourceProps) {
  const due = useDueCount()
  return (
    <div className="row" style={{ gap: 10, flexWrap: 'wrap' }}>
      <p className="small muted spacer" style={{ margin: 0 }}>
        Câu dùng các từ sắp đến hạn ôn trong deck của bạn{due.data ? ` (${due.data.due} từ đến hạn hôm nay)` : ''}.
      </p>
      <button className="btn primary" disabled={busy} onClick={() => onStart({ source: 'deck', level })}>
        Tạo 10 câu
      </button>
    </div>
  )
}

function TopicSource({ level, busy, onStart }: SourceProps) {
  const topics = useTopics('writing')
  const [busyId, setBusyId] = useState<number | null>(null)
  const pick = (t: Topic) => {
    setBusyId(t.id)
    onStart({ source: 'topic', topic_id: t.id, level })
  }
  const custom = (c: CustomTopic) => {
    setBusyId(-1)
    onStart({ source: 'topic', custom: c, level })
  }
  if (topics.isPending) return <Loading />
  if (topics.error) return <ErrorBox error={topics.error} onRetry={() => topics.refetch()} />
  return (
    <>
      <CustomTopicForm skill="writing" busy={busy} onSubmit={custom} />
      <TopicGrid topics={topics.data} busyId={busy ? busyId : null} onPick={pick} />
    </>
  )
}

function SetList({ sets }: { sets: ReturnType<typeof useSentenceSets> }) {
  const del = useDeleteSentenceSet()
  if (sets.isPending) return <Loading />
  if (sets.error) return <ErrorBox error={sets.error} onRetry={() => sets.refetch()} />
  if (sets.data.length === 0)
    return <EmptyState emoji="📝" title="Chưa có bộ câu nào" text="Chọn nguồn câu ở trên để bắt đầu." />
  return (
    <div className="list">
      {sets.data.map((s) => (
        <Link key={s.id} to={`/writing/sentences/${s.id}`} className="list-item">
          <span className="icon">📝</span>
          <div className="body">
            <b>{s.title}</b>
            <div className="meta">
              <span className="badge level">{s.level}</span>
              <StatusBadge status={s.status as LessonStatus} />
              <span>{SOURCE_LABEL[s.source] ?? s.source}</span>
              <span>
                · {s.stats.done}/{s.stats.total} câu
              </span>
              <span>· {timeAgo(s.created_at)}</span>
            </div>
          </div>
          {s.stats.score != null && <span className={`score tone-${scoreTone(s.stats.score)}`}>{s.stats.score}</span>}
          <button
            className="btn icon sm ghost danger"
            aria-label="Xoá bộ câu"
            onClick={(e) => {
              e.preventDefault()
              if (confirm(`Xoá "${s.title}"?`)) del.mutate(s.id)
            }}
          >
            <Icon name="trash" />
          </button>
        </Link>
      ))}
    </div>
  )
}
