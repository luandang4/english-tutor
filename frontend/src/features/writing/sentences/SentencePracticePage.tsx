import { useEffect, useRef, useState, type KeyboardEvent } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'

import { useAnswerSentence, useRedoMissedSentences, useRetrySentenceSet, useSentenceSet } from '../../../api/hooks'
import type { SentenceAttempt, SentenceItem, SentenceSetDetail } from '../../../api/types'
import { ErrorBox, Icon, Loading, PageHeader, ProgressBar, SpeakButton } from '../../../components/ui'
import { playResult } from '../../../lib/audio/sfx'
import { scoreTone } from '../../../lib/format'
import {
  ERROR_KIND_LABEL,
  VERDICT_LABEL,
  VERDICT_TONE,
  firstOpen,
  markErrors,
  nextOpen,
} from './model'
import './sentences.css'

const BACK = { to: '/writing?mode=sentences', label: 'Dịch câu' }

export function SentencePracticePage() {
  const id = Number(useParams().id)
  const { data, error, refetch } = useSentenceSet(id)
  const retry = useRetrySentenceSet(id)

  if (error) return <ErrorBox error={error} onRetry={() => refetch()} />
  if (!data) return <Loading />
  return (
    <div className="page sp-page">
      <PageHeader title={data.title || 'Luyện viết câu'} back={BACK} />
      {data.status === 'generating' && <Loading label="AI đang soạn 10 câu cho bạn…" />}
      {data.status === 'failed' && (
        <ErrorBox error={data.error ?? 'Tạo câu bị lỗi.'} onRetry={() => retry.mutate()} />
      )}
      {(data.status === 'ready' || data.status === 'completed') && <Practice data={data} />}
    </div>
  )
}

function Practice({ data }: { data: SentenceSetDetail }) {
  const [index, setIndex] = useState(() => Math.max(0, firstOpen(data.items)))
  const [review, setReview] = useState(() => firstOpen(data.items) < 0)
  const finished = firstOpen(data.items) < 0

  if (review && finished) return <Summary data={data} onOpen={(i) => (setIndex(i), setReview(false))} />
  return (
    <div className="stack">
      <Strip items={data.items} index={index} onPick={setIndex} />
      <ItemCard
        key={index}
        setId={data.id}
        item={data.items[index]}
        total={data.items.length}
        onNext={() => {
          const next = nextOpen(data.items, index)
          if (next < 0) setReview(true)
          else setIndex(next)
        }}
        finished={finished}
        onSummary={() => setReview(true)}
      />
    </div>
  )
}

function Strip({ items, index, onPick }: { items: SentenceItem[]; index: number; onPick: (i: number) => void }) {
  const done = items.filter((i) => i.done).length
  return (
    <div className="stack" style={{ gap: 8 }}>
      <div className="sp-strip" role="tablist" aria-label="Các câu">
        {items.map((it) => (
          <button
            key={it.index}
            role="tab"
            aria-selected={it.index === index}
            className={`sp-dot ${it.index === index ? 'on' : ''} ${it.verdict ? `tone-${VERDICT_TONE[it.verdict]}` : ''} ${it.done ? 'done' : ''}`}
            onClick={() => onPick(it.index)}
            title={it.verdict ? VERDICT_LABEL[it.verdict] : 'Chưa làm'}
          >
            {it.index + 1}
          </button>
        ))}
      </div>
      <ProgressBar value={(done / items.length) * 100} />
    </div>
  )
}

function ItemCard(props: {
  setId: number
  item: SentenceItem
  total: number
  onNext: () => void
  finished: boolean
  onSummary: () => void
}) {
  const { item } = props
  const answer = useAnswerSentence(props.setId)
  const [text, setText] = useState('')
  const [hint, setHint] = useState(() => item.attempts.some((a) => a.hint_used))
  const input = useRef<HTMLTextAreaElement>(null)
  const last = item.attempts.at(-1)

  useEffect(() => {
    if (!item.done) input.current?.focus()
  }, [item.done])

  const submit = () => {
    const t = text.trim()
    if (!t || answer.isPending) return
    answer.mutate(
      { index: item.index, answer: t, hintUsed: hint },
      {
        onSuccess: (a) => {
          playResult(a.verdict !== 'wrong')
          if (a.verdict !== 'correct') setText(t)
        },
      },
    )
  }
  const onKey = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key !== 'Enter' || e.shiftKey || e.nativeEvent.isComposing) return
    e.preventDefault()
    submit()
  }

  return (
    <section className="card sp-card stack">
      <div className="row small muted">
        <span className="spacer">
          Câu {item.index + 1}/{props.total}
        </span>
        {!item.done && <span>Còn {item.tries_left} lần chấm bằng AI</span>}
      </div>

      <p className="sp-vi" lang="vi">
        {item.vi}
      </p>
      <div className="chips">
        {item.grammar_point && <span className="chip">{item.grammar_point}</span>}
        {item.target_words.map((w) => (
          <span key={w} className="chip sp-target">
            Dùng: {w}
          </span>
        ))}
      </div>

      {hint && (
        <div className="sp-hint small">
          <b>Gợi ý:</b> {item.hint_vi}
          {item.hint_words.length > 0 && <span className="muted"> · Từ khoá: {item.hint_words.join(', ')}</span>}
        </div>
      )}

      {!item.done && (
        <form
          className="stack"
          style={{ gap: 10 }}
          onSubmit={(e) => {
            e.preventDefault()
            submit()
          }}
        >
          <textarea
            ref={input}
            className="textarea sp-input"
            rows={2}
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={onKey}
            placeholder="Viết câu tiếng Anh…"
            lang="en"
            autoComplete="off"
            autoCorrect="off"
            spellCheck={false}
            enterKeyHint="send"
            aria-label="Câu tiếng Anh của bạn"
            maxLength={500}
          />
          <div className="row sp-actions">
            {!hint && (
              <button type="button" className="btn sm ghost" onClick={() => setHint(true)} title="Câu này bị trừ 20 điểm">
                <Icon name="sparkle" size={16} /> Gợi ý (−20)
              </button>
            )}
            <button
              type="button"
              className="btn sm ghost"
              disabled={answer.isPending}
              onClick={() => answer.mutate({ index: item.index, answer: null, hintUsed: hint })}
            >
              Xem đáp án
            </button>
            <span className="spacer" />
            <button className="btn primary" type="submit" disabled={!text.trim() || answer.isPending}>
              {answer.isPending ? 'Đang chấm…' : 'Chấm'}
            </button>
          </div>
        </form>
      )}
      {answer.error && <ErrorBox error={answer.error} />}

      {last && <AttemptView attempt={last} />}

      {item.done && (
        <>
          <Answers answers={item.answers} />
          <div className="row">
            <span className="spacer" />
            {props.finished ? (
              <button className="btn primary" onClick={props.onSummary}>
                Xem tổng kết <Icon name="arrowRight" size={16} />
              </button>
            ) : (
              <button className="btn primary" onClick={props.onNext} autoFocus>
                Câu tiếp theo <Icon name="arrowRight" size={16} />
              </button>
            )}
          </div>
        </>
      )}
    </section>
  )
}

function AttemptView({ attempt }: { attempt: SentenceAttempt }) {
  const r = attempt.result
  const tone = VERDICT_TONE[attempt.verdict]
  if (attempt.verdict === 'revealed') return null
  return (
    <div className={`sp-result tone-border-${tone} stack`}>
      <div className="row">
        <b className={`tone-${tone}`}>{VERDICT_LABEL[attempt.verdict]}</b>
        <span className={`score tone-${scoreTone(attempt.score)}`}>{attempt.score}</span>
        {attempt.hint_used && <span className="small muted">(đã dùng gợi ý)</span>}
      </div>
      <p className="sp-answer" lang="en">
        {markErrors(attempt.answer, r).map((s, i) =>
          s.error ? (
            <mark key={i} className="sp-wrong" title={`→ ${s.error}`}>
              {s.text}
            </mark>
          ) : (
            <span key={i}>{s.text}</span>
          ),
        )}
      </p>
      {r && r.errors.length > 0 && (
        <ul className="sp-errors">
          {r.errors.map((e, i) => (
            <li key={i}>
              <span className="badge">{ERROR_KIND_LABEL[e.kind] ?? e.kind}</span>{' '}
              {e.original && <s className="tone-low">{e.original}</s>} → <b className="tone-good">{e.fix}</b>
              <span className="muted"> · {e.explain_vi}</span>
            </li>
          ))}
        </ul>
      )}
      {r && attempt.verdict !== 'correct' && r.corrected && (
        <Line label="Câu của bạn, đã sửa" text={r.corrected} />
      )}
      {r && r.natural && r.natural !== r.corrected && <Line label="Người bản xứ hay nói" text={r.natural} />}
      {r && !r.target_words_used && <p className="small tone-ok">Bạn chưa dùng (đúng) từ cần luyện trong câu này.</p>}
      {r?.comment_vi && <p className="small muted">{r.comment_vi}</p>}
    </div>
  )
}

function Line({ label, text }: { label: string; text: string }) {
  return (
    <div className="sp-line">
      <span className="small muted">{label}</span>
      <div className="row" style={{ gap: 8 }}>
        <span lang="en">{text}</span>
        <SpeakButton text={text} />
      </div>
    </div>
  )
}

function Answers({ answers }: { answers: string[] }) {
  if (!answers.length) return null
  return (
    <div className="sp-line">
      <span className="small muted">Đáp án mẫu (cách khác đúng vẫn được tính)</span>
      {answers.map((a) => (
        <div key={a} className="row" style={{ gap: 8 }}>
          <span lang="en">{a}</span>
          <SpeakButton text={a} />
        </div>
      ))}
    </div>
  )
}

function Summary({ data, onOpen }: { data: SentenceSetDetail; onOpen: (index: number) => void }) {
  const s = data.stats
  const redo = useRedoMissedSentences()
  const navigate = useNavigate()
  const missed = data.items.filter((i) => i.verdict !== 'correct').length
  const kinds = Object.entries(s.error_kinds) as [keyof typeof ERROR_KIND_LABEL, number][]
  return (
    <div className="stack">
      <section className="card sp-summary">
        <div className={`sp-score tone-${scoreTone(s.score)}`}>{s.score ?? 0}</div>
        <div className="stack" style={{ gap: 6 }}>
          <b>Hoàn thành {s.total} câu</b>
          <span className="small">
            <span className="tone-good">{s.correct} đúng</span> · <span className="tone-ok">{s.almost} gần đúng</span> ·{' '}
            <span className="tone-low">{s.wrong} chưa đúng / xem đáp án</span>
          </span>
          {kinds.length > 0 && (
            <span className="small muted">
              Lỗi hay gặp: {kinds.map(([k, n]) => `${ERROR_KIND_LABEL[k] ?? k} (${n})`).join(', ')}
            </span>
          )}
          {s.weak_grammar.length > 0 && (
            <div className="chips">
              <span className="small muted">Nên ôn:</span>
              {s.weak_grammar.map((g) => (
                <span key={g} className="chip">
                  {g}
                </span>
              ))}
            </div>
          )}
        </div>
      </section>

      <div className="row" style={{ flexWrap: 'wrap', gap: 8 }}>
        {missed > 0 && (
          <button
            className="btn primary"
            disabled={redo.isPending}
            onClick={() => redo.mutate(data.id, { onSuccess: (row) => navigate(`/writing/sentences/${row.id}`) })}
          >
            Luyện lại {missed} câu chưa đúng
          </button>
        )}
        <Link className="btn ghost" to={BACK.to}>
          Tạo bộ câu mới
        </Link>
      </div>
      {redo.error && <ErrorBox error={redo.error} />}

      <div className="list">
        {data.items.map((it) => {
          const best = it.attempts.filter((a) => a.verdict !== 'revealed').at(-1)
          return (
            <button key={it.index} className="list-item sp-review" onClick={() => onOpen(it.index)}>
              <span className={`sp-dot done tone-${it.verdict ? VERDICT_TONE[it.verdict] : 'low'}`}>{it.index + 1}</span>
              <div className="body">
                <span>{it.vi}</span>
                <div className="meta">
                  <span lang="en">{best?.result?.natural || it.answers[0]}</span>
                </div>
              </div>
              {it.score != null && <span className={`score tone-${scoreTone(it.score)}`}>{it.score}</span>}
            </button>
          )
        })}
      </div>
    </div>
  )
}
