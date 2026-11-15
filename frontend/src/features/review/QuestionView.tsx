import { useCallback, useEffect, useRef, useState } from 'react'

import type { AnswerOut, QuestionKind, QuizQuestion } from '../../api/types'
import { PronounceButton } from '../../components/exercises/PronounceButton'
import { Icon, SpeakButton, Spinner } from '../../components/ui'
import { reviewDay } from '../../lib/format'
import { playWordUrl } from '../../lib/audio/tts'

const KIND_LABEL: Record<QuestionKind, { badge: string; ask: string }> = {
  choose_meaning: { badge: 'Chọn nghĩa', ask: 'Từ này nghĩa là gì?' },
  listen_choose: { badge: 'Nghe và chọn', ask: 'Nghe rồi chọn từ bạn nghe được' },
  listen_type: { badge: 'Nghe và gõ', ask: 'Nghe rồi gõ lại từ' },
  vi_to_en: { badge: 'Nhớ từ', ask: 'Gõ từ tiếng Anh có nghĩa' },
  fill_sentence: { badge: 'Điền vào câu', ask: 'Điền từ còn thiếu (đúng dạng trong câu)' },
  grammar_choice: { badge: 'Trắc nghiệm', ask: 'Chọn đáp án đúng' },
  grammar_fill: { badge: 'Điền từ', ask: 'Điền vào chỗ trống' },
}

const CHOICE: QuestionKind[] = ['choose_meaning', 'listen_choose', 'grammar_choice']
const RESULT_TITLE = { correct: 'Chính xác!', near: 'Gần đúng', wrong: 'Chưa đúng' } as const

export interface Submit {
  answer: string
  hinted: boolean
}

/** One question: prompt, answer input (options or typing), then the graded feedback. */
export function QuestionView({
  question,
  outcome,
  pending,
  onSubmit,
  onNext,
}: {
  question: QuizQuestion
  outcome: AnswerOut | null
  pending: boolean
  onSubmit: (s: Submit) => void
  onNext: () => void
}) {
  const [answer, setAnswer] = useState('')
  const [hinted, setHinted] = useState(false)
  const choice = CHOICE.includes(question.kind)
  const send = (value: string) => {
    if (!pending && !outcome) onSubmit({ answer: value.trim(), hinted })
  }

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (outcome || !choice || (e.target as HTMLElement).closest('input, textarea')) return
      const i = Number(e.key) - 1
      if (i >= 0 && i < question.options.length) send(question.options[i])
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  })

  const state = outcome?.result ?? ''
  return (
    <article className={`card quiz-card ${state}`}>
      <div className="quiz-kind">
        <span className="badge level">{KIND_LABEL[question.kind].badge}</span>
        <span className="small muted">{KIND_LABEL[question.kind].ask}</span>
      </div>

      <Prompt question={question} fill={outcome ? outcome.expected : answer} />

      {choice ? (
        <div className="options">
          {question.options.map((o, i) => {
            let cls = ''
            if (outcome) {
              if (o === outcome.expected) cls = 'is-correct'
              else if (o === answer) cls = 'is-wrong'
            } else if (pending && o === answer) cls = 'selected'
            return (
              <button
                key={o}
                type="button"
                className={`option ${cls}`}
                disabled={!!outcome || pending}
                onClick={() => {
                  setAnswer(o)
                  send(o)
                }}
              >
                <span className="small muted hide-sm">{i + 1}. </span>
                {o}
              </button>
            )
          })}
        </div>
      ) : (
        !outcome && (
          <form
            className="stack"
            onSubmit={(e) => {
              e.preventDefault()
              if (answer.trim()) send(answer)
            }}
          >
            <div className="quiz-answer">
              <input
                className="input"
                placeholder={question.kind.startsWith('grammar') ? 'Câu trả lời…' : 'Gõ từ tiếng Anh…'}
                value={answer}
                onChange={(e) => setAnswer(e.target.value)}
                disabled={pending}
                autoFocus
                autoComplete="off"
                autoCapitalize="off"
                spellCheck={false}
                aria-label="Câu trả lời"
              />
              <button className="btn primary" type="submit" disabled={!answer.trim() || pending}>
                {pending ? <Spinner small /> : <Icon name="check" />} Kiểm tra
              </button>
            </div>
            <div className="quiz-actions">
              {question.letters > 0 && (
                <button type="button" className="btn sm ghost" onClick={() => setHinted(true)} disabled={hinted || pending}>
                  <Icon name="eye" size={16} /> {hinted ? `Bắt đầu bằng “${question.first_letter}”` : 'Gợi ý'}
                </button>
              )}
              <button type="button" className="btn sm ghost" onClick={() => send('')} disabled={pending}>
                Không nhớ
              </button>
              {hinted && <span className="small muted">Trả lời đúng sau gợi ý được tính là “Khó”.</span>}
            </div>
          </form>
        )
      )}

      {outcome && <Feedback question={question} outcome={outcome} given={answer} onNext={onNext} />}
    </article>
  )
}

function Prompt({ question, fill }: { question: QuizQuestion; fill: string }) {
  const letters = question.letters > 0 && <span className="letter-hint">{'_ '.repeat(Math.min(question.letters, 24)).trim()} ({question.letters} ký tự)</span>
  switch (question.kind) {
    case 'choose_meaning':
      return (
        <div className="quiz-prompt">
          <div className="row" style={{ justifyContent: 'center' }}>
            <span className="quiz-word">{question.prompt}</span>
            <SpeakButton text={question.prompt} />
          </div>
          {question.part_of_speech && <span className="badge">{question.part_of_speech}</span>}
        </div>
      )
    case 'listen_choose':
    case 'listen_type':
      return (
        <div className="quiz-prompt">
          <ListenButton url={question.audio_url ?? ''} />
          {question.kind === 'listen_type' && letters}
        </div>
      )
    case 'vi_to_en':
      return (
        <div className="quiz-prompt">
          <span className="quiz-meaning">{question.prompt}</span>
          {question.part_of_speech && <span className="badge">{question.part_of_speech}</span>}
          {letters}
        </div>
      )
    default:
      return (
        <div className="quiz-prompt" style={{ alignItems: 'stretch', textAlign: 'left' }}>
          <Sentence text={question.prompt} fill={fill} />
          {question.hint_vi && <span className="small muted">{question.hint_vi}</span>}
          {question.kind === 'fill_sentence' && letters}
        </div>
      )
  }
}

function Sentence({ text, fill }: { text: string; fill: string }) {
  const parts = text.split(/_{2,}/)
  return (
    <p className="quiz-sentence">
      {parts.map((p, i) => (
        <span key={i}>
          {p}
          {i < parts.length - 1 && <span className="gap">{fill || ' '}</span>}
        </span>
      ))}
    </p>
  )
}

/** Plays the word once on mount, then on every click. */
function ListenButton({ url }: { url: string }) {
  const [state, setState] = useState<'idle' | 'loading' | 'error'>('idle')
  const played = useRef('')
  const play = useCallback(() => {
    setState('loading')
    playWordUrl(url)
      .then(() => setState('idle'))
      .catch(() => setState('error'))
  }, [url])
  useEffect(() => {
    if (played.current === url) return // StrictMode runs effects twice: play once
    played.current = url
    play()
  }, [url, play])
  return (
    <>
      <button type="button" className="listen-btn" onClick={play} disabled={state === 'loading'} aria-label="Nghe lại">
        {state === 'loading' ? <Spinner /> : <Icon name="volume" />}
      </button>
      <span className="small muted">{state === 'error' ? 'Không phát được âm thanh, bấm để thử lại.' : 'Bấm để nghe lại'}</span>
    </>
  )
}

function Feedback({
  question,
  outcome,
  given,
  onNext,
}: {
  question: QuizQuestion
  outcome: AnswerOut
  given: string
  onNext: () => void
}) {
  const w = outcome.word
  return (
    <div className={`quiz-feedback ${outcome.result}`}>
      <span className="title">{RESULT_TITLE[outcome.result]}</span>
      {outcome.result === 'near' && (
        <span>
          Bạn gõ <i>{given}</i>, viết đúng là <b className="en">{outcome.expected}</b>.
        </span>
      )}
      {outcome.result === 'wrong' && (
        <span>
          Đáp án: <b className="en">{outcome.expected}</b>
        </span>
      )}
      {w && (
        <div className="reveal">
          <div className="head">
            <b>{w.word}</b>
            <SpeakButton text={w.word} />
            {w.ipa && <span className="ipa">{w.ipa}</span>}
            {w.part_of_speech && <span className="badge">{w.part_of_speech}</span>}
          </div>
          {w.meaning_vi && <span>{w.meaning_vi}</span>}
          {w.example_en && question.kind !== 'fill_sentence' && (
            <div className="example">
              <div>{w.example_en}</div>
              {w.example_vi && <div className="vi">{w.example_vi}</div>}
            </div>
          )}
          <PronounceButton text={w.word} cardId={outcome.card_id ?? undefined} label="Nói thử từ này" />
        </div>
      )}
      {outcome.explanation_vi && <span className="muted">💡 {outcome.explanation_vi}</span>}
      {outcome.card_id != null && (
        <span className="small muted">
          {outcome.rating == null
            ? 'Từ chưa đến hạn ôn, lịch ôn giữ nguyên.'
            : `Lịch ôn đã cập nhật · ôn lại ${outcome.next_review_at ? reviewDay(outcome.next_review_at) : ''}.`}
        </span>
      )}
      <div className="quiz-actions">
        <span className="spacer" />
        <button className="btn primary" onClick={onNext} autoFocus>
          Tiếp <Icon name="arrowRight" size={16} />
        </button>
      </div>
    </div>
  )
}
