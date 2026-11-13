import { useMemo, useState } from 'react'

import type { Submission, WritingCorrection } from '../../api/types'
import { ProgressBar, ScoreRing } from '../../components/ui'
import { CORRECTION_LABEL, CRITERION_LABEL, scoreTone, timeAgo } from '../../lib/format'

interface Span {
  start: number
  end: number
  n: number
}

/** Locate each correction's `original` in the text (first free occurrence, no overlaps). */
function locate(text: string, corrections: WritingCorrection[]): Span[] {
  const spans: Span[] = []
  corrections.forEach((c, i) => {
    let from = 0
    while (from <= text.length) {
      const start = text.indexOf(c.original, from)
      if (start < 0) return
      const end = start + c.original.length
      if (!spans.some((s) => start < s.end && end > s.start)) {
        spans.push({ start, end, n: i + 1 })
        return
      }
      from = start + 1
    }
  })
  return spans.sort((a, b) => a.start - b.start)
}

export function WritingFeedbackView({ submission }: { submission: Submission }) {
  const fb = submission.result!
  const [active, setActive] = useState<number | null>(null)
  const spans = useMemo(() => locate(submission.text, fb.corrections), [submission.text, fb.corrections])

  const marked = useMemo(() => {
    const out: React.ReactNode[] = []
    let pos = 0
    for (const s of spans) {
      if (s.start > pos) out.push(submission.text.slice(pos, s.start))
      out.push(
        <mark
          key={s.n}
          className={active === s.n ? 'active' : ''}
          onClick={() => {
            setActive(s.n)
            document.getElementById(`corr-${submission.id}-${s.n}`)?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
          }}
        >
          {submission.text.slice(s.start, s.end)}
          <sup>{s.n}</sup>
        </mark>,
      )
      pos = s.end
    }
    out.push(submission.text.slice(pos))
    return out
  }, [spans, submission.text, submission.id, active])

  return (
    <div className="stack" style={{ gap: 16 }}>
      <div className="card row" style={{ gap: 20, alignItems: 'center' }}>
        <ScoreRing score={fb.overall_score} size={96} />
        <div className="stack spacer" style={{ gap: 6, minWidth: 220 }}>
          <div className="row">
            <span className="badge level">Ước tính {fb.cefr_estimate}</span>
            <span className="small muted">
              {submission.word_count} từ · nộp {timeAgo(submission.created_at)}
            </span>
          </div>
          <p>{fb.summary_vi}</p>
        </div>
      </div>

      <div className="grid cols-2">
        <div className="card criteria">
          <div className="card-title">
            <h3>Tiêu chí chấm</h3>
          </div>
          {fb.criteria.map((c) => (
            <div className="criterion" key={c.criterion}>
              <div className="row">
                <span>{CRITERION_LABEL[c.criterion] ?? c.criterion}</span>
                <span className={`tone-${scoreTone(c.score)}`}>{c.score}</span>
              </div>
              <ProgressBar value={c.score} />
              <p>{c.comment_vi}</p>
            </div>
          ))}
        </div>
        <div className="stack">
          <div className="card">
            <div className="card-title">
              <h3>✅ Điểm mạnh</h3>
            </div>
            <ul>
              {fb.strengths_vi.map((s) => (
                <li key={s}>{s}</li>
              ))}
            </ul>
          </div>
          <div className="card">
            <div className="card-title">
              <h3>🎯 Cần cải thiện</h3>
            </div>
            <ul>
              {fb.improvements_vi.map((s) => (
                <li key={s}>{s}</li>
              ))}
            </ul>
          </div>
        </div>
      </div>

      <div className="card stack">
        <div className="card-title" style={{ marginBottom: 0 }}>
          <h3>Bài của bạn · {fb.corrections.length} lỗi được đánh dấu</h3>
        </div>
        <div className="marked-text">{marked}</div>
        {fb.corrections.length > 0 && (
          <div className="stack" style={{ gap: 8 }}>
            {fb.corrections.map((c, i) => (
              <div
                key={i}
                id={`corr-${submission.id}-${i + 1}`}
                className={`correction ${active === i + 1 ? 'active' : ''}`}
                onMouseEnter={() => setActive(i + 1)}
              >
                <span className="n">{i + 1}</span>
                <span className="fix">
                  <s>{c.original}</s> → <ins>{c.corrected}</ins>{' '}
                  <span className="badge" style={{ marginLeft: 4 }}>
                    {CORRECTION_LABEL[c.category] ?? c.category}
                  </span>
                </span>
                <span className="why">{c.explanation_vi}</span>
              </div>
            ))}
          </div>
        )}
      </div>

      <details className="card collapse">
        <summary>✨ Bài viết gợi ý (đã sửa & nâng cấp)</summary>
        <div className="marked-text">{fb.improved_version}</div>
      </details>
    </div>
  )
}
