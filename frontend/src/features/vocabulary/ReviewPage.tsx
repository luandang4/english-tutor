import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'

import { useCards, useDeckStats, useDeleteCard, useReviewCard } from '../../api/hooks'
import type { Card } from '../../api/types'
import { PronounceButton } from '../../components/exercises/PronounceButton'
import { AudioSourceSelect, EmptyState, ErrorBox, Icon, Loading, PageHeader, ProgressBar, SpeakButton } from '../../components/ui'
import { timeAgo } from '../../lib/format'
import { playText } from '../../lib/audio/tts'

const RATINGS = [
  { value: 1, label: 'Quên', cls: 'again', key: '1' },
  { value: 2, label: 'Khó', cls: 'hard', key: '2' },
  { value: 3, label: 'Nhớ', cls: 'good', key: '3' },
  { value: 4, label: 'Dễ', cls: 'easy', key: '4' },
] as const

export function ReviewPage() {
  const [tab, setTab] = useState<'review' | 'deck'>('review')
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
      <div className="tabs">
        <button className={`tab ${tab === 'review' ? 'active' : ''}`} onClick={() => setTab('review')}>
          Ôn tập
        </button>
        <button className={`tab ${tab === 'deck' ? 'active' : ''}`} onClick={() => setTab('deck')}>
          Bộ từ {stats ? `(${stats.total})` : ''}
        </button>
      </div>
      {tab === 'review' ? <ReviewSession /> : <DeckList />}
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

function ReviewSession() {
  const due = useCards(true)
  const review = useReviewCard()
  // Reviews don't invalidate the due list, so it stays a stable queue for the whole session.
  const queue: Card[] | null = due.data ?? null
  const [index, setIndex] = useState(0)
  const [flipped, setFlipped] = useState(false)
  const [done, setDone] = useState(0)

  const card = queue?.[index]

  const rate = (rating: 1 | 2 | 3 | 4) => {
    if (!card || review.isPending) return
    review.mutate(
      { id: card.id, rating },
      {
        onSuccess: () => {
          setFlipped(false)
          setDone((d) => d + 1)
          setIndex((i) => i + 1)
        },
      },
    )
  }

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (!card || (e.target as HTMLElement).closest('input, textarea')) return
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

  if (due.isPending || queue === null) return <Loading />
  if (due.error) return <ErrorBox error={due.error} onRetry={() => due.refetch()} />

  if (!card) {
    return (
      <div className="card">
        <EmptyState
          emoji={done ? '🎉' : '🌙'}
          title={done ? `Xong! Bạn vừa ôn ${done} từ.` : 'Không có từ nào cần ôn lúc này'}
          text={
            done
              ? 'Các từ bấm “Quên” sẽ quay lại sau vài phút.'
              : 'Học thêm bài từ vựng để có từ mới, hoặc quay lại sau.'
          }
          action={
            <div className="row" style={{ justifyContent: 'center' }}>
              <button
                className="btn"
                disabled={due.isFetching}
                onClick={() =>
                  void due.refetch().then(() => {
                    setIndex(0)
                    setDone(0)
                  })
                }
              >
                <Icon name="refresh" size={16} /> Kiểm tra lại
              </button>
              <Link className="btn primary" to="/vocabulary">
                <Icon name="book" size={16} /> Học từ mới
              </Link>
            </div>
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
            Thẻ {index + 1}/{queue.length}
          </span>
          <span>Space: lật thẻ · 1–4: chấm</span>
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
              <small>{card.intervals[r.key]}</small>
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

function DeckList() {
  const cards = useCards(false)
  const del = useDeleteCard()
  const [q, setQ] = useState('')
  const filtered = useMemo(() => {
    const s = q.trim().toLowerCase()
    return (cards.data ?? []).filter((c) => !s || c.word.toLowerCase().includes(s) || c.meaning_vi.toLowerCase().includes(s))
  }, [cards.data, q])

  if (cards.isPending) return <Loading />
  if (cards.error) return <ErrorBox error={cards.error} onRetry={() => cards.refetch()} />
  if (!cards.data.length)
    return (
      <EmptyState
        emoji="🗂️"
        title="Bộ từ đang trống"
        text="Hoàn thành một bài từ vựng để thêm từ vào đây."
        action={
          <Link className="btn primary" to="/vocabulary">
            Học từ vựng
          </Link>
        }
      />
    )

  return (
    <div className="stack">
      <input className="input" placeholder="Tìm từ hoặc nghĩa…" value={q} onChange={(e) => setQ(e.target.value)} />
      <div className="list">
        {filtered.map((c) => (
          <div key={c.id} className="list-item">
            <SpeakButton text={c.word} />
            <div className="body">
              <b>
                {c.word} <span className="small muted">{c.ipa}</span>
              </b>
              <div className="meta">
                <span>{c.meaning_vi}</span>
                <span>· ôn {c.reps} lần</span>
                <span>· {new Date(c.due_at).getTime() <= cards.dataUpdatedAt ? 'cần ôn' : `ôn lại ${timeAgo(c.due_at)}`}</span>
              </div>
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
    </div>
  )
}
