import { useState } from 'react'

import { useSubmitAttempt } from '../../api/hooks'
import type { Exercise } from '../../api/types'
import { EXERCISE_LABEL } from '../../lib/format'
import { ErrorBox, Icon, Spinner } from '../ui'

const GAP = /_{2,}/

function Question({ text, fill }: { text: string; fill?: string }) {
  const parts = text.split(GAP)
  if (parts.length === 1) return <p className="question">{text}</p>
  return (
    <p className="question">
      {parts.map((p, i) => (
        <span key={i}>
          {p}
          {i < parts.length - 1 && <span className="gap">{fill || ' '}</span>}
        </span>
      ))}
    </p>
  )
}

export function ExerciseCard({ lessonId, exercise, index }: { lessonId: number; exercise: Exercise; index: number }) {
  const submit = useSubmitAttempt(lessonId)
  const [answer, setAnswer] = useState('')
  const [retrying, setRetrying] = useState(false)
  const result = retrying ? null : exercise.result
  const open = exercise.type === 'rewrite' || exercise.type === 'produce'
  const usesAI = open || exercise.type === 'fill_blank'

  const send = (value: string) => {
    if (!value.trim() || submit.isPending) return
    submit.mutate(
      { exerciseId: exercise.id, answer: value.trim() },
      {
        onSuccess: () => {
          setRetrying(false)
          setAnswer('')
        },
      },
    )
  }
  const onSubmit = (e: { preventDefault(): void }) => {
    e.preventDefault()
    send(answer)
  }

  const state = result ? (result.is_correct ? 'correct' : 'wrong') : ''
  return (
    <article className={`card exercise ${state}`}>
      <div className="exercise-head">
        <span className="exercise-num">{result ? <Icon name={result.is_correct ? 'check' : 'x'} size={15} /> : index + 1}</span>
        <span className="badge">{EXERCISE_LABEL[exercise.type]}</span>
        <span className="small muted">{exercise.instruction_vi}</span>
      </div>

      <Question text={exercise.question} fill={result && exercise.type === 'fill_blank' ? result.answer : answer} />

      {exercise.type === 'multiple_choice' ? (
        <div className="options">
          {exercise.options.map((o) => {
            let cls = ''
            if (result) {
              if (result.answers.includes(o)) cls = 'is-correct'
              else if (o === result.answer) cls = 'is-wrong'
            } else if (submit.isPending && submit.variables?.answer === o) cls = 'selected'
            return (
              <button key={o} type="button" className={`option ${cls}`} disabled={!!result || submit.isPending} onClick={() => send(o)}>
                {o}
              </button>
            )
          })}
        </div>
      ) : (
        !result && (
          <form onSubmit={onSubmit} className="stack">
            {open ? (
              <textarea
                className="textarea"
                rows={2}
                placeholder="Viết câu trả lời bằng tiếng Anh…"
                value={answer}
                onChange={(e) => setAnswer(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault()
                    send(answer)
                  }
                }}
                disabled={submit.isPending}
              />
            ) : (
              <input
                className="input"
                placeholder="Từ cần điền…"
                value={answer}
                onChange={(e) => setAnswer(e.target.value)}
                disabled={submit.isPending}
                autoComplete="off"
                spellCheck={false}
              />
            )}
            <div className="row">
              <button className="btn primary sm" type="submit" disabled={!answer.trim() || submit.isPending}>
                {submit.isPending ? <Spinner small /> : <Icon name="check" />}
                {submit.isPending && usesAI ? 'Gemini đang chấm…' : 'Kiểm tra'}
              </button>
              {open && <span className="small muted">Enter để gửi · Shift+Enter xuống dòng</span>}
            </div>
          </form>
        )
      )}

      {submit.error && <ErrorBox error={submit.error} />}

      {result && (
        <div className={`feedback ${result.is_correct ? 'good' : 'bad'}`}>
          <span className="title">
            {result.is_correct ? 'Chính xác!' : 'Chưa đúng'} · {result.score}/100
          </span>
          {open && (
            <span>
              Bạn trả lời: <i>{result.answer}</i>
            </span>
          )}
          {result.feedback_vi && result.feedback_vi !== 'Chính xác!' && result.feedback_vi !== 'Chưa đúng.' && (
            <span>{result.feedback_vi}</span>
          )}
          {!result.is_correct && result.answers.length > 0 && (
            <span>
              {open ? 'Gợi ý' : 'Đáp án'}: <b className="en">{result.answers.join(' / ')}</b>
            </span>
          )}
          {open && result.corrected_answer && result.corrected_answer !== result.answer && (
            <span>
              Câu sửa: <b className="en">{result.corrected_answer}</b>
            </span>
          )}
          {result.explanation_vi && <span className="muted">💡 {result.explanation_vi}</span>}
          <div className="row" style={{ marginTop: 4 }}>
            <button className="btn sm ghost" onClick={() => setRetrying(true)}>
              <Icon name="refresh" size={16} /> Làm lại
            </button>
            {result.attempts > 1 && <span className="small muted">Đã làm {result.attempts} lần</span>}
          </div>
        </div>
      )}
    </article>
  )
}
