import { useRef, useState, type KeyboardEvent } from 'react'

import { Icon, ProgressBar } from '../../components/ui'
import { Segmented } from '../../components/ui/Segmented'
import { playText } from '../../lib/audio/tts'
import { usePreference } from '../../lib/preferences'
import { checkEnglish, checkMeaning, letterDiff, type DiffPart } from './check'
import { addCount, readCounts, wordKey } from './counts'
import { GOAL_OPTIONS, type DrillWord, type Goal, type Line } from './model'
import { ModelCard, Notebook, SpellingDiff, WordStrip } from './parts'
import './drill.css'

/** Result of the last line, shown under the inputs until the next one is written. */
type Feedback =
  | { ok: true; close: boolean }
  | { ok: false; en: DiffPart[] | null; meaning: string | null }

/**
 * Writing drill: copy each word and its Vietnamese meaning again and again, as in a notebook.
 * No limit on repetitions; the goal only marks when a word has been written enough times.
 */
export function WriteDrill({ words, startIndex = 0 }: { words: DrillWord[]; startIndex?: number }) {
  const [index, setIndex] = useState(() => Math.min(Math.max(startIndex, 0), words.length - 1))
  const [session, setSession] = useState<Record<string, Line[]>>({})
  const [totals, setTotals] = useState(readCounts)
  const [en, setEn] = useState('')
  const [vi, setVi] = useState('')
  const [feedback, setFeedback] = useState<Feedback | null>(null)
  const [goalText, setGoal] = usePreference<Goal>('et.drill.goal', '10')
  const goal = Number(goalText) || 10
  const [speak, setSpeak] = usePreference('et.drill.speak', true)
  const [hideModel, setHideModel] = usePreference('et.drill.hideModel', false)
  const enRef = useRef<HTMLInputElement>(null)
  const viRef = useRef<HTMLInputElement>(null)

  const w = words[index]
  const key = wordKey(w.word)
  const lines = session[key] ?? []
  const done = lines.filter((l) => l.ok).length
  const total = totals[key] ?? 0

  const go = (i: number) => {
    setIndex((i + words.length) % words.length)
    setEn('')
    setVi('')
    setFeedback(null)
    enRef.current?.focus()
  }

  const submit = () => {
    if (!en.trim() && !vi.trim()) return
    const enV = checkEnglish(en, w.word)
    const viV = checkMeaning(vi, w.meaning_vi)
    const ok = enV === 'right' && (viV === 'right' || viV === 'close')
    setSession((s) => ({ ...s, [key]: [...(s[key] ?? []), { en: en.trim(), vi: vi.trim(), ok }] }))
    if (ok) {
      setTotals(addCount(w.word))
      setFeedback({ ok: true, close: viV === 'close' })
      if (speak) playText(w.word).catch(() => {})
    } else {
      setFeedback({
        ok: false,
        en: enV === 'right' ? null : letterDiff(en, w.word),
        meaning: viV === 'right' || viV === 'close' ? null : w.meaning_vi,
      })
    }
    setEn('')
    setVi('')
    enRef.current?.focus()
  }

  const onEnKey = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key !== 'Enter' || e.nativeEvent.isComposing) return
    e.preventDefault()
    if (en.trim()) viRef.current?.focus()
  }
  const onViKey = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key !== 'Enter' || e.nativeEvent.isComposing) return
    e.preventDefault()
    submit()
  }

  return (
    <div className="drill stack">
      <WordStrip words={words} index={index} onPick={go} session={session} totals={totals} goal={goal} />

      <div className="drill-grid">
        <section className="card drill-main">
          <ModelCard w={w} hidden={hideModel} onToggle={() => setHideModel(!hideModel)} />

          <form
            className="drill-form"
            onSubmit={(e) => {
              e.preventDefault()
              submit()
            }}
          >
            <label className="drill-field">
              <span>Tiếng Anh</span>
              <input
                ref={enRef}
                className="input"
                value={en}
                onChange={(e) => setEn(e.target.value)}
                onKeyDown={onEnKey}
                autoComplete="off"
                autoCorrect="off"
                autoCapitalize="none"
                spellCheck={false}
                enterKeyHint="next"
                lang="en"
                aria-label="Viết từ tiếng Anh"
                autoFocus
              />
            </label>
            <label className="drill-field">
              <span>Nghĩa tiếng Việt</span>
              <input
                ref={viRef}
                className="input"
                value={vi}
                onChange={(e) => setVi(e.target.value)}
                onKeyDown={onViKey}
                autoComplete="off"
                autoCorrect="off"
                autoCapitalize="none"
                spellCheck={false}
                enterKeyHint="done"
                lang="vi"
                aria-label="Viết nghĩa tiếng Việt"
              />
            </label>
            <button className="btn primary drill-submit" type="submit" disabled={!en.trim() && !vi.trim()}>
              <Icon name="check" size={16} /> Viết
            </button>
          </form>

          <FeedbackLine feedback={feedback} />

          <div className="drill-progress">
            <div className="row small">
              <span className="spacer">
                Buổi này: <b>{done}</b>/{goal} lần {done >= goal && <span className="tone-good">· đạt mục tiêu ✓</span>}
              </span>
              <span className="muted">Tổng: {total} lần</span>
            </div>
            <ProgressBar value={Math.min(100, (done / goal) * 100)} />
          </div>

          <div className="row drill-nav">
            <button className="btn sm ghost" type="button" onClick={() => go(index - 1)} disabled={words.length < 2}>
              <Icon name="arrowLeft" size={16} /> Từ trước
            </button>
            <span className="small muted spacer drill-pos">
              {index + 1}/{words.length}
            </span>
            <button
              className={`btn sm ${done >= goal ? 'primary' : 'ghost'}`}
              type="button"
              onClick={() => go(index + 1)}
              disabled={words.length < 2}
            >
              Từ tiếp theo <Icon name="arrowRight" size={16} />
            </button>
          </div>
        </section>

        <aside className="card drill-side stack">
          <div className="stack" style={{ gap: 10 }}>
            <Segmented label="Mục tiêu mỗi từ" value={goalText} options={GOAL_OPTIONS} onChange={setGoal} />
            <label className="toggle">
              <input type="checkbox" checked={speak} onChange={(e) => setSpeak(e.target.checked)} />
              <span className="switch" aria-hidden="true" />
              <span>Đọc to từ mỗi khi viết đúng</span>
            </label>
          </div>
          <div className="stack" style={{ gap: 6 }}>
            <h3 className="drill-side-title">Vở tập viết · {w.word}</h3>
            <Notebook lines={lines} />
          </div>
        </aside>
      </div>
    </div>
  )
}

function FeedbackLine({ feedback }: { feedback: Feedback | null }) {
  if (!feedback) return null
  if (feedback.ok)
    return (
      <p className="small drill-feedback tone-good">
        ✓ Đúng{feedback.close && <span className="muted"> (nghĩa đúng nhưng khác dấu, xem lại cách bỏ dấu)</span>}
      </p>
    )
  return (
    <div className="small drill-feedback tone-low stack" style={{ gap: 4 }}>
      {feedback.en && (
        <span>
          ✗ Chính tả: <SpellingDiff parts={feedback.en} />
        </span>
      )}
      {feedback.meaning && (
        <span>
          ✗ Nghĩa đúng: <b>{feedback.meaning}</b>
        </span>
      )}
      <span className="muted">Dòng này không tính. Viết lại nhé.</span>
    </div>
  )
}
