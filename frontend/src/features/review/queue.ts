import type { AnswerResult, QuizQuestion } from '../../api/types'

export interface Entry {
  question: QuizQuestion
  /** A retry of a question missed earlier in this session: graded, but never changes the schedule. */
  requeued: boolean
}

/** First answer per question (what counts for the score and for FSRS). */
export type FirstResults = Record<string, { result: AnswerResult; label: string; expected: string }>

/** Put a missed question back 3–5 places later (or at the end), so it returns within the session. */
export function requeue<T extends { requeued: boolean }>(queue: T[], index: number, item: T): T[] {
  const at = Math.min(queue.length, index + 4 + Math.floor(Math.random() * 3))
  return [...queue.slice(0, at), { ...item, requeued: true }, ...queue.slice(at)]
}
