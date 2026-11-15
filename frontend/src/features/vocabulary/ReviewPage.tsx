import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'

import {
  useAddCard,
  useAnswerCard,
  useCards,
  useDeckStats,
  useDeleteCard,
  useLessonReviewStats,
  useLessons,
  useReviewCard,
  useReviewSession,
} from '../../api/hooks'
import type { Card, CardState, SessionMode } from '../../api/types'
import { PronounceButton } from '../../components/exercises/PronounceButton'
import { AudioSourceSelect, EmptyState, ErrorBox, Icon, Loading, PageHeader, ProgressBar, SpeakButton, Spinner } from '../../components/ui'
import { useAccess } from '../../lib/access'
import { playText } from '../../lib/audio/tts'
import { reviewDay } from '../../lib/format'
import { QuizRunner } from '../review/QuizRunner'
import { requeue, type FirstResults } from '../review/queue'
import '../review/review.css'

const RATINGS = [
  { value: 1, label: 'Quên', cls: 'again', key: '1' },
  { value: 2, label: 'Khó', cls: 'hard', key: '2' },
  { value: 3, label: 'Nhớ', cls: 'good', key: '3' },
  { value: 4, label: 'Dễ', cls: 'easy', key: '4' },
] as const

const STATE_LABEL: Record<CardState, string> = { new: 'Mới', learning: 'Đang học', mature: 'Đã thuộc' }

type Tab = 'review' | 'quick' | 'deck'

export function ReviewPage() {
  const [tab, setTab] = useState<Tab>('review')
  const { data: stats } = useDeckStats()
  return (
    <div className="page">
      <PageHeader
        title="Ôn tập từ vựng"
        subtitle="Lặp lại ngắt quãng (FSRS): từ bạn hay quên sẽ xuất hiện thường xuyên hơn, từ đã thuộc sẽ giãn dần."
        actions={<AudioSourceSelect />}
      />
      {stats && (
        <div className="grid cols-4">
          <Stat label="Cần ôn" value={stats.due} accent />
          <Stat label="Từ mới" value={stats.new} />
          <Stat label="Đang học" value={stats.learning} />
          <Stat label="Đã thuộc" value={stats.mature} />
        </div>
      )}
      <div className="tabs" role="tablist">
        <button className={`tab ${tab === 'review' ? 'active' : ''}`} onClick={() => setTab('review')}>
          Ôn tập
        </button>
        <button className={`tab ${tab === 'quick' ? 'active' : ''}`} onClick={() => setTab('quick')} title="Lật thẻ, tự chấm">
          Ôn nhanh
        </button>
        <button className={`tab ${tab === 'deck' ? 'active' : ''}`} onClick={() => setTab('deck')}>
          Bộ từ {stats ? `(${stats.total})` : ''}
        </button>
      </div>
      {tab === 'review' && <ReviewHome hasCards={!!stats?.total} hard={stats?.hard ?? 0} />}
      {tab === 'quick' && <FlipSession />}
      {tab === 'deck' && <DeckList />}
    </div>
  )
}

function Stat({ label, value, accent }: { label: string; value: number; accent?: boolean }) {
  return (
    <div className="card stat">
      <span className="label">{label}</span>
      <span className={`value ${accent ? 'gradient-text' : ''}`}>{value}</span>
    </div>
  )
}

// ---------- auto-graded review (default) ----------
type Practice = { mode: SessionMode; lessonId?: number }

function ReviewHome({ hasCards, hard }: { hasCards: boolean; hard: number }) {
  const [practice, setPractice] = useState<Practice | null>(null)
  const [stoppedDue, setStoppedDue] = useState(false)
  const due = useReviewSession('due', undefined, practice === null)

  if (practice) return <SessionRunner {...practice} onExit={() => setPractice(null)} />
  if (due.isPending) return <Loading />
  if (due.error) return <ErrorBox error={due.error} onRetry={() => due.refetch()} />
  const dueLeft = due.data.questions.length + due.data.remaining
  if (dueLeft && !stoppedDue)
    return (
      <SessionRunner
        mode="due"
        onExit={() => {
          setStoppedDue(true)
          void due.refetch()
        }}
      />
    )
  if (!hasCards)
    return (
      <div className="card">
        <EmptyState
          emoji="🗂️"
          title="Bộ từ đang trống"
          text="Học một bài từ vựng hoặc thêm từ ở tab “Bộ từ” để bắt đầu ôn tập."
          action={
            <Link className="btn primary" to="/vocabulary">
              <Icon name="book" size={16} /> Học từ mới
            </Link>
          }
        />
      </div>
    )
  return (
    <PracticeChooser
      hard={hard}
      dueLeft={dueLeft}
      onPick={setPractice}
      onResume={() => {
        setStoppedDue(false)
        void due.refetch()
      }}
    />
  )
}

/** Nothing due: practise anyway. Right answers on cards that are not due do not move their schedule. */
function PracticeChooser({
  hard,
  dueLeft,
  onPick,
  onResume,
}: {
  hard: number
  dueLeft: number
  onPick: (p: Practice) => void
  onResume: () => void
}) {
  const lessons = useLessons('vocabulary')
  const stats = useLessonReviewStats('vocabulary')
  const [lessonId, setLessonId] = useState('')
  const withCards = useMemo(() => {
    const counts = new Map((stats.data ?? []).map((s) => [s.lesson_id, s.cards]))
    return (lessons.data ?? []).filter((l) => (counts.get(l.id) ?? 0) > 0)
  }, [lessons.data, stats.data])

  return (
    <div className="card stack">
      {dueLeft > 0 && (
        <button className="alert info row" style={{ textAlign: 'left', cursor: 'pointer' }} onClick={onResume}>
          <Icon name="cards" />
          <span className="spacer">
            Còn <b>{dueLeft}</b> từ đến hạn — ôn tiếp
          </span>
          <Icon name="arrowRight" />
        </button>
      )}
      <div>
        <h3>{dueLeft > 0 ? 'Hoặc luyện theo cách khác' : '🌙 Hôm nay không còn từ nào đến hạn'}</h3>
        <p className="small muted">
          Bạn vẫn có thể luyện thêm. Trả lời đúng từ chưa đến hạn sẽ không dời lịch ôn; trả lời sai thì từ đó được đưa
          về ôn sớm.
        </p>
      </div>
      <div className="practice-grid">
        <button className="practice-option" onClick={() => onPick({ mode: 'soon' })}>
          <b>⏭️ Sắp đến hạn</b>
          <span>10 từ có lịch ôn gần nhất</span>
        </button>
        <button className="practice-option" onClick={() => onPick({ mode: 'hard' })} disabled={!hard}>
          <b>🔥 Từ khó</b>
          <span>{hard ? `${hard} từ hay quên` : 'Chưa có từ khó'} · cả từ vừa quên gần đây</span>
        </button>
        <button className="practice-option" onClick={() => onPick({ mode: 'random' })}>
          <b>🎲 Ngẫu nhiên</b>
          <span>10 từ bất kỳ trong bộ từ</span>
        </button>
        <div className="practice-option" style={{ cursor: 'default' }}>
          <b>📚 Theo bài</b>
          <div className="row" style={{ gap: 6, flexWrap: 'nowrap' }}>
            <select className="select" value={lessonId} onChange={(e) => setLessonId(e.target.value)} aria-label="Chọn bài">
              <option value="">Chọn bài…</option>
              {withCards.map((l) => (
                <option key={l.id} value={l.id}>
                  {l.title}
                </option>
              ))}
            </select>
            <button className="btn sm primary" disabled={!lessonId} onClick={() => onPick({ mode: 'lesson', lessonId: Number(lessonId) })}>
              Ôn
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

function SessionRunner({ mode, lessonId, onExit }: Practice & { onExit: () => void }) {
  const session = useReviewSession(mode, lessonId)
  const answer = useAnswerCard()
  const [results, setResults] = useState<FirstResults | null>(null)

  if (session.isPending || session.isFetching) return <Loading />
  if (session.error) return <ErrorBox error={session.error} onRetry={() => session.refetch()} />
  const { questions, remaining } = session.data
  if (!questions.length)
    return (
      <div className="card">
        <EmptyState
          emoji="🌙"
          title="Không có từ nào trong mục này"
          action={
            <button className="btn" onClick={onExit}>
              Quay lại
            </button>
          }
        />
      </div>
    )

  if (results) {
    const list = Object.values(results)
    const missed = list.filter((r) => r.result === 'wrong')
    const more = mode === 'due' ? remaining > 0 : true
    return (
      <div className="quiz-wrap">
        <div className="completion">
          <div className="stack" style={{ gap: 6, flex: 1 }}>
            <h3>🎉 Xong {list.length} từ!</h3>
            <p className="muted small">
              Đúng ngay lần đầu {list.length - missed.length}/{list.length}.
              {mode === 'due' && remaining > 0 && ` Còn ${remaining} từ đến hạn.`}
            </p>
          </div>
        </div>
        {missed.length > 0 && (
          <div className="result-list">
            {missed.map((r) => (
              <div key={r.label} className="result-row">
                <span className="result-mark wrong">✗</span>
                <span className="label">{r.label}</span>
                <span className="expected">{r.expected}</span>
              </div>
            ))}
          </div>
        )}
        <div className="row">
          {more && (
            <button
              className="btn primary"
              onClick={() => {
                setResults(null)
                void session.refetch()
              }}
            >
              <Icon name="refresh" size={16} /> {mode === 'due' ? 'Ôn tiếp?' : 'Luyện thêm'}
            </button>
          )}
          <button className="btn" onClick={onExit}>
            {mode === 'due' ? 'Xong' : 'Chọn cách ôn khác'}
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="stack">
      {mode !== 'due' && (
        <div className="row">
          <span className="small muted spacer">Luyện tự do · lịch ôn chỉ đổi khi bạn trả lời sai</span>
          <button className="btn sm ghost" onClick={onExit}>
            <Icon name="x" size={16} /> Thoát
          </button>
        </div>
      )}
      <QuizRunner
        key={session.dataUpdatedAt}
        questions={questions}
        answer={(b) => answer.mutateAsync(b)}
        retryWrong
        onDone={setResults}
      />
    </div>
  )
}

// ---------- "Ôn nhanh": flip card, self-rated ----------
function FlipSession() {
  const due = useCards(true)
  if (due.isPending) return <Loading />
  if (due.error) return <ErrorBox error={due.error} onRetry={() => due.refetch()} />
  return <FlipRunner key={due.dataUpdatedAt} cards={due.data} onReload={() => void due.refetch()} reloading={due.isFetching} />
}

interface FlipEntry {
  card: Card
  requeued: boolean // re-shown after "Quên": already rated, only the first rating counts
}

function FlipRunner({ cards, onReload, reloading }: { cards: Card[]; onReload: () => void; reloading: boolean }) {
  const review = useReviewCard()
  const [queue, setQueue] = useState<FlipEntry[]>(() => cards.map((card) => ({ card, requeued: false })))
  const [index, setIndex] = useState(0)
  const [flipped, setFlipped] = useState(false)
  const [done, setDone] = useState(0)
  const entry = queue[index]
  const card = entry?.card

  const advance = (rating: number) => {
    if (rating === 1) {
      setQueue((q) => requeue(q, index, entry)) // forgotten: show it again after 3–5 other cards
    } else setDone((d) => d + 1)
    setFlipped(false)
    setIndex((i) => i + 1)
  }

  const rate = (rating: 1 | 2 | 3 | 4) => {
    if (!entry || review.isPending) return
    if (entry.requeued) return advance(rating)
    review.mutate({ id: entry.card.id, rating }, { onSuccess: () => advance(rating) })
  }

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (!card || (e.target as HTMLElement).closest('input, textarea, select')) return
      if (e.key === ' ' || e.key === 'Enter') {
        e.preventDefault()
        setFlipped((f) => !f)
      } else if (flipped && ['1', '2', '3', '4'].includes(e.key)) {
        rate(Number(e.key) as 1 | 2 | 3 | 4)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  })

  if (!card) {
    return (
      <div className="card">
        <EmptyState
          emoji={done ? '🎉' : '🌙'}
          title={done ? `Xong! Bạn vừa ôn ${done} từ.` : 'Không có từ nào cần ôn lúc này'}
          text={done ? 'Các từ bấm “Quên” đã được ôn lại ngay trong phiên.' : 'Thử tab “Ôn tập” để luyện tự do.'}
          action={
            <button className="btn" disabled={reloading} onClick={onReload}>
              <Icon name="refresh" size={16} /> Kiểm tra lại
            </button>
          }
        />
      </div>
    )
  }

  return (
    <div className="stack" style={{ gap: 18, alignItems: 'center' }}>
      <div style={{ width: '100%', maxWidth: 560 }}>
        <div className="row small muted" style={{ marginBottom: 6 }}>
          <span className="spacer">
            Thẻ {Math.min(index + 1, queue.length)}/{queue.length}
            {entry.requeued && ' · ôn lại từ vừa quên'}
          </span>
          <span className="hide-sm">Space: lật thẻ · 1–4: chấm</span>
        </div>
        <ProgressBar value={(index / queue.length) * 100} />
      </div>

      <div className="flashcard-wrap">
        <div
          className={`flashcard ${flipped ? 'flipped' : ''}`}
          onClick={() => {
            if (!flipped) void playText(card.word).catch(() => {})
            setFlipped((f) => !f)
          }}
          role="button"
          tabIndex={0}
          aria-label="Lật thẻ"
        >
          <div className="face front">
            <span className="badge">{card.part_of_speech}</span>
            <span className="big-word">{card.word}</span>
            <span className="small muted">Bạn còn nhớ nghĩa của từ này? Chạm để lật thẻ</span>
          </div>
          <div className="face back" onClick={(e) => e.target !== e.currentTarget && e.stopPropagation()}>
            <div className="row" style={{ justifyContent: 'center' }}>
              <span className="big-word" style={{ fontSize: '1.7rem' }}>
                {card.word}
              </span>
              <SpeakButton text={card.word} />
            </div>
            <span className="ipa" style={{ color: 'var(--primary-soft)' }}>
              {card.ipa}
            </span>
            <b style={{ fontSize: '1.15rem' }}>{card.meaning_vi}</b>
            <span className="small muted">{card.definition_en}</span>
            <div className="example" style={{ textAlign: 'left', width: '100%' }}>
              <div>{card.example_en}</div>
              <div className="vi">{card.example_vi}</div>
            </div>
            <PronounceButton text={card.word} cardId={card.id} />
          </div>
        </div>
      </div>

      {flipped ? (
        <div className="rating">
          {RATINGS.map((r) => (
            <button key={r.value} className={`btn ${r.cls}`} onClick={() => rate(r.value)} disabled={review.isPending}>
              {r.label}
              {!entry.requeued && <small>{card.intervals[r.key]}</small>}
            </button>
          ))}
        </div>
      ) : (
        <button className="btn primary" onClick={() => setFlipped(true)}>
          <Icon name="eye" /> Xem nghĩa
        </button>
      )}
      {review.error && <ErrorBox error={review.error} />}
    </div>
  )
}

// ---------- deck ----------
type StateFilter = 'all' | CardState | 'hard'
type Sort = 'new' | 'due'

function DeckList() {
  const cards = useCards(false)
  const del = useDeleteCard()
  const [q, setQ] = useState('')
  const [lesson, setLesson] = useState('all')
  const [state, setState] = useState<StateFilter>('all')
  const [sort, setSort] = useState<Sort>('new')

  const lessonOptions = useMemo(() => {
    const m = new Map<string, string>()
    for (const c of cards.data ?? []) m.set(c.lesson_id ? String(c.lesson_id) : 'none', c.lesson_title ?? 'Thêm tay / khác')
    return [...m.entries()]
  }, [cards.data])

  const filtered = useMemo(() => {
    const s = q.trim().toLowerCase()
    const list = (cards.data ?? []).filter(
      (c) =>
        (!s || c.word.toLowerCase().includes(s) || c.meaning_vi.toLowerCase().includes(s)) &&
        (lesson === 'all' || (c.lesson_id ? String(c.lesson_id) : 'none') === lesson) &&
        (state === 'all' || (state === 'hard' ? c.is_hard : c.state === state)),
    )
    return sort === 'due' ? [...list].sort((a, b) => a.due_at.localeCompare(b.due_at)) : list
  }, [cards.data, q, lesson, state, sort])

  if (cards.isPending) return <Loading />
  if (cards.error) return <ErrorBox error={cards.error} onRetry={() => cards.refetch()} />

  return (
    <div className="stack">
      <AddWord />
      {!cards.data.length ? (
        <EmptyState
          emoji="🗂️"
          title="Bộ từ đang trống"
          text="Hoàn thành một bài từ vựng hoặc thêm từ ở ô trên."
          action={
            <Link className="btn primary" to="/vocabulary">
              Học từ vựng
            </Link>
          }
        />
      ) : (
        <>
          <div className="deck-filters">
            <input className="input search" placeholder="Tìm từ hoặc nghĩa…" value={q} onChange={(e) => setQ(e.target.value)} />
            <select className="select" value={lesson} onChange={(e) => setLesson(e.target.value)} aria-label="Lọc theo bài">
              <option value="all">Mọi bài</option>
              {lessonOptions.map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
            <select className="select" value={state} onChange={(e) => setState(e.target.value as StateFilter)} aria-label="Lọc theo trạng thái">
              <option value="all">Mọi trạng thái</option>
              <option value="new">Mới</option>
              <option value="learning">Đang học</option>
              <option value="mature">Đã thuộc</option>
              <option value="hard">Từ khó</option>
            </select>
            <select className="select" value={sort} onChange={(e) => setSort(e.target.value as Sort)} aria-label="Sắp xếp">
              <option value="new">Mới thêm trước</option>
              <option value="due">Theo hạn ôn</option>
            </select>
          </div>
          <span className="small muted">{filtered.length} từ</span>
          <div className="list">
            {filtered.map((c) => (
              <div key={c.id} className="list-item">
                <SpeakButton text={c.word} />
                <div className="body">
                  <b>
                    {c.word} <span className="small muted">{c.ipa}</span>
                  </b>
                  <div className="meta">
                    <span className={`badge state-${c.state}`}>{STATE_LABEL[c.state]}</span>
                    {c.is_hard && <span className="badge hard">Từ khó</span>}
                    <span>{c.meaning_vi}</span>
                    <span>
                      · {new Date(c.due_at).getTime() <= cards.dataUpdatedAt ? 'cần ôn' : `ôn ${reviewDay(c.due_at)}`}
                    </span>
                  </div>
                  {c.is_hard && (
                    <details className="tips">
                      <summary>Mẹo nhớ</summary>
                      {c.example_en && <p>Ví dụ: {c.example_en}</p>}
                      {c.tips_vi.length > 0 && (
                        <ul>
                          {c.tips_vi.map((t) => (
                            <li key={t}>{t}</li>
                          ))}
                        </ul>
                      )}
                    </details>
                  )}
                </div>
                <button
                  className="btn icon sm ghost danger"
                  aria-label={`Xoá ${c.word}`}
                  onClick={() => confirm(`Xoá “${c.word}” khỏi bộ từ?`) && del.mutate(c.id)}
                >
                  <Icon name="trash" />
                </button>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  )
}

/** Add a word by hand; Gemini fills meaning, IPA and an example (one "Từ vựng" request). */
function AddWord() {
  const { can } = useAccess()
  const add = useAddCard()
  const [word, setWord] = useState('')
  if (!can('vocabulary')) return null
  return (
    <form
      className="card stack"
      style={{ gap: 8 }}
      onSubmit={(e) => {
        e.preventDefault()
        if (word.trim()) add.mutate({ word: word.trim() }, { onSuccess: () => setWord('') })
      }}
    >
      <div className="add-word">
        <input
          className="input"
          placeholder="Thêm từ mới vào bộ ôn, ví dụ: serendipity"
          value={word}
          onChange={(e) => setWord(e.target.value)}
          maxLength={120}
          autoCapitalize="off"
          aria-label="Từ cần thêm"
        />
        <button className="btn primary" type="submit" disabled={!word.trim() || add.isPending}>
          {add.isPending ? <Spinner small /> : <Icon name="plus" size={16} />} Thêm từ
        </button>
      </div>
      <span className="small muted">AI điền nghĩa, phiên âm và câu ví dụ (tính 1 lượt Từ vựng). Từ đã có thì không thêm lại.</span>
      {add.error && <ErrorBox error={add.error} />}
      {add.data && (
        <div className={`alert ${add.data.created ? 'success' : 'info'}`}>
          {add.data.created ? 'Đã thêm' : 'Đã có sẵn trong bộ từ'}: <b>{add.data.card.word}</b> — {add.data.card.meaning_vi}
          {add.data.created && ` · ôn lần đầu ${reviewDay(add.data.card.due_at)}`}
        </div>
      )}
    </form>
  )
}
