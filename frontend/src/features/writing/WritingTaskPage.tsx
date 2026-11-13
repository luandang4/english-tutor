import { useState } from 'react'
import { useParams } from 'react-router-dom'

import { useRegradeSubmission, useRetryWritingTask, useSubmitWriting, useWritingTask } from '../../api/hooks'
import type { Submission, WritingPrompt } from '../../api/types'
import {
  ErrorBox,
  GeneratingState,
  Icon,
  Loading,
  PageHeader,
  Spinner,
  StatusBadge,
} from '../../components/ui'
import { countWords, scoreTone, timeAgo } from '../../lib/format'
import { usePreference } from '../../lib/preferences'
import { WritingFeedbackView } from './WritingFeedbackView'

const back = { to: '/writing', label: 'Luyện viết' }

export function WritingTaskPage() {
  const id = Number(useParams().id)
  const { data: task, error, isPending, refetch } = useWritingTask(id)
  const retry = useRetryWritingTask(id)

  if (isPending) return <div className="page"><Loading /></div>
  if (error || !task)
    return (
      <div className="page">
        <PageHeader title="Bài viết" back={back} />
        <ErrorBox error={error} onRetry={() => refetch()} />
      </div>
    )
  if (task.status === 'generating')
    return (
      <div className="page">
        <PageHeader title={task.topic.title_vi} back={back} />
        <GeneratingState title="Gemini đang ra đề cho bạn" />
      </div>
    )
  if (task.status === 'failed' || !task.prompt)
    return (
      <div className="page">
        <PageHeader title={task.topic.title_vi} back={back} />
        <div className="card stack">
          <div className="alert error">{task.error ?? 'Không tạo được đề bài.'}</div>
          <div>
            <button className="btn primary" onClick={() => retry.mutate()} disabled={retry.isPending}>
              <Icon name="refresh" /> Tạo lại đề
            </button>
          </div>
        </div>
      </div>
    )

  return (
    <div className="page">
      <PageHeader
        back={back}
        title={task.title}
        subtitle={
          <span className="row">
            <span className="badge level">{task.level}</span>
            <StatusBadge status={task.status} />
            <span>
              {task.topic.icon} {task.topic.title_vi} · {task.prompt.task_type}
            </span>
          </span>
        }
      />
      <div className="writing-layout">
        <PromptPanel prompt={task.prompt} />
        <Workspace key={task.id} taskId={task.id} prompt={task.prompt} submissions={task.submissions} />
      </div>
    </div>
  )
}

function PromptPanel({ prompt }: { prompt: WritingPrompt }) {
  return (
    <div className="stack" style={{ position: 'sticky', top: 16 }}>
      <div className="card stack">
        <div className="card-title" style={{ marginBottom: 0 }}>
          <h3>📝 Đề bài</h3>
          <span className="badge">
            {prompt.min_words}–{prompt.max_words} từ
          </span>
        </div>
        <div className="prompt-box en">{prompt.prompt_en}</div>
        <p className="small muted">{prompt.prompt_vi}</p>
        <div>
          <b className="small">Yêu cầu:</b>
          <ul className="checklist" style={{ marginTop: 6 }}>
            {prompt.requirements.map((r) => (
              <li key={r}>{r}</li>
            ))}
          </ul>
        </div>
      </div>
      <details className="card collapse">
        <summary>🧭 Dàn ý gợi ý</summary>
        <div>
          <ol>
            {prompt.outline_vi.map((o) => (
              <li key={o} style={{ marginBottom: 4 }}>
                {o}
              </li>
            ))}
          </ol>
        </div>
      </details>
      <details className="card collapse">
        <summary>💬 Cụm từ hữu ích ({prompt.useful_phrases.length})</summary>
        <div className="phrase-list">
          {prompt.useful_phrases.map((p) => (
            <div className="phrase" key={p.phrase}>
              <b>{p.phrase}</b>
              <span className="muted">{p.meaning_vi}</span>
            </div>
          ))}
        </div>
      </details>
    </div>
  )
}

function Workspace({ taskId, prompt, submissions }: { taskId: number; prompt: WritingPrompt; submissions: Submission[] }) {
  const [draft, setDraft] = usePreference(`et.writing.draft.${taskId}`, '')
  const submit = useSubmitWriting(taskId)
  const regrade = useRegradeSubmission(taskId)
  const latest = submissions.at(-1)
  const [viewId, setViewId] = useState<number | null>(null)
  const viewing = submissions.find((s) => s.id === viewId) ?? latest

  const words = countWords(draft)
  const range = words < prompt.min_words ? 'low' : words > prompt.max_words ? 'ok' : 'good'
  const grading = submissions.some((s) => s.status === 'grading')

  return (
    <div className="stack" style={{ gap: 16 }}>
      <div className="card stack">
        <div className="card-title" style={{ marginBottom: 0 }}>
          <h3>{submissions.length ? '✏️ Viết lại / bản nháp mới' : '✏️ Bài viết của bạn'}</h3>
        </div>
        <textarea
          className="textarea"
          rows={12}
          placeholder="Start writing here…"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          spellCheck={false}
          disabled={submit.isPending}
        />
        <div className="editor-foot">
          <span className={`word-count tone-${range}`}>
            {words} / {prompt.min_words}–{prompt.max_words} từ
          </span>
          <span className="spacer" />
          {latest?.result && (
            <button className="btn sm ghost" onClick={() => setDraft(latest.result!.improved_version)} title="Chép bài gợi ý vào ô viết">
              Dùng bài gợi ý
            </button>
          )}
          <button
            className="btn primary"
            disabled={words < 5 || draft.trim().length < 20 || submit.isPending || grading}
            onClick={() => submit.mutate(draft, { onSuccess: () => setViewId(null) })}
          >
            {submit.isPending || grading ? <Spinner small /> : <Icon name="sparkle" />}
            {grading ? 'Gemini đang chấm…' : 'Nộp bài & chấm điểm'}
          </button>
        </div>
        {submit.error && <ErrorBox error={submit.error} />}
      </div>

      {submissions.length > 1 && (
        <div className="row">
          <span className="small muted">Các lần nộp:</span>
          {submissions.map((s, i) => (
            <button
              key={s.id}
              className={`btn sm ${viewing?.id === s.id ? 'primary' : ''}`}
              onClick={() => setViewId(s.id)}
              title={timeAgo(s.created_at)}
            >
              #{i + 1}
              {s.overall_score != null && <b className={viewing?.id === s.id ? '' : `tone-${scoreTone(s.overall_score)}`}>{s.overall_score}</b>}
            </button>
          ))}
        </div>
      )}

      {viewing?.status === 'grading' && (
        <div className="card generating" style={{ padding: 36 }}>
          <div className="pulse-orb" style={{ width: 60, height: 60 }} />
          <h3>Gemini đang chấm bài…</h3>
          <p className="small muted">Thường mất 10–30 giây.</p>
        </div>
      )}
      {viewing?.status === 'failed' && (
        <div className="card stack">
          <div className="alert error">{viewing.error ?? 'Chấm bài thất bại.'}</div>
          <div>
            <button className="btn" onClick={() => regrade.mutate(viewing.id)} disabled={regrade.isPending}>
              <Icon name="refresh" size={16} /> Chấm lại
            </button>
          </div>
        </div>
      )}
      {viewing?.status === 'graded' && viewing.result && <WritingFeedbackView submission={viewing} />}
    </div>
  )
}
