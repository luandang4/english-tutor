import { useState } from 'react'

import type { AnswerIn, AnswerOut, QuizQuestion } from '../../api/types'
import { ErrorBox, ProgressBar } from '../../components/ui'
import { QuestionView, type Submit } from './QuestionView'
import { requeue, type Entry, type FirstResults } from './queue'
import './review.css'

/**
 * Runs a list of auto-graded questions. With `retryWrong`, a missed question comes back after a few others
 * until it is answered correctly (retries never change the schedule: only the first answer counts).
 */
export function QuizRunner({
  questions,
  answer,
  retryWrong,
  onDone,
}: {
  questions: QuizQuestion[]
  answer: (body: AnswerIn) => Promise<AnswerOut>
  retryWrong: boolean
  onDone: (results: FirstResults) => void
}) {
  const [queue, setQueue] = useState<Entry[]>(() => questions.map((question) => ({ question, requeued: false })))
  const [index, setIndex] = useState(0)
  const [outcome, setOutcome] = useState<AnswerOut | null>(null)
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<unknown>(null)
  const [results, setResults] = useState<FirstResults>({})

  const entry = queue[index]
  if (!entry) return null
  const firstDone = Object.keys(results).length

  const submit = ({ answer: value, hinted }: Submit) => {
    setPending(true)
    setError(null)
    answer({ question_id: entry.question.id, answer: value, hinted, requeued: entry.requeued })
      .then((out) => {
        setOutcome(out)
        if (!(entry.question.id in results)) {
          const label = out.word?.word ?? entry.question.prompt
          setResults((r) => ({ ...r, [entry.question.id]: { result: out.result, label, expected: out.expected } }))
        }
      })
      .catch(setError)
      .finally(() => setPending(false))
  }

  const next = () => {
    const nextQueue = retryWrong && outcome?.result === 'wrong' ? requeue(queue, index, entry) : queue
    setQueue(nextQueue)
    setOutcome(null)
    if (index + 1 >= nextQueue.length) onDone(results)
    else setIndex(index + 1)
  }

  return (
    <div className="quiz-wrap">
      <div className="quiz-progress">
        <div className="row small muted">
          <span className="spacer">
            Câu {Math.min(firstDone + (outcome || entry.requeued ? 0 : 1), questions.length)}/{questions.length}
            {entry.requeued && ' · làm lại câu sai'}
          </span>
          <span className="hide-sm">Enter: kiểm tra / tiếp</span>
        </div>
        <ProgressBar value={(firstDone / questions.length) * 100} />
      </div>
      <QuestionView
        key={`${index}-${entry.question.id}`}
        question={entry.question}
        outcome={outcome}
        pending={pending}
        onSubmit={submit}
        onNext={next}
      />
      {!!error && <ErrorBox error={error} />}
    </div>
  )
}
