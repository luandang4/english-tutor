import type { SentenceErrorKind, SentenceGradeResult, SentenceItem, SentenceVerdict } from '../../../api/types'

export const VERDICT_LABEL: Record<SentenceVerdict, string> = {
  correct: 'Đúng',
  almost: 'Gần đúng',
  wrong: 'Chưa đúng',
  revealed: 'Đã xem đáp án',
}

export const VERDICT_TONE: Record<SentenceVerdict, 'good' | 'ok' | 'low'> = {
  correct: 'good',
  almost: 'ok',
  wrong: 'low',
  revealed: 'low',
}

export const ERROR_KIND_LABEL: Record<SentenceErrorKind, string> = {
  grammar: 'Ngữ pháp',
  vocabulary: 'Từ vựng',
  word_order: 'Trật tự từ',
  spelling: 'Chính tả',
  missing: 'Thiếu từ',
  meaning: 'Sai nghĩa',
}

export const SOURCE_LABEL: Record<string, string> = {
  lesson: 'Từ bài học',
  deck: 'Ôn deck',
  topic: 'Chủ đề',
  retry: 'Luyện lại',
}

/** First sentence still to answer, or -1 when the set is finished. */
export const firstOpen = (items: SentenceItem[]) => items.findIndex((i) => !i.done)

/** The next unfinished sentence after `from` (wrapping), or -1. */
export function nextOpen(items: SentenceItem[], from: number): number {
  for (let step = 1; step <= items.length; step++) {
    const i = (from + step) % items.length
    if (!items[i].done) return i
  }
  return -1
}

export type Span = { text: string; error?: string }

/** The learner's sentence split so each wrong span (copied by the grader) can be marked. */
export function markErrors(answer: string, result: SentenceGradeResult | null): Span[] {
  const errors = (result?.errors ?? []).filter((e) => e.original.trim())
  const marks: { start: number; end: number; fix: string }[] = []
  const lower = answer.toLowerCase()
  for (const e of errors) {
    const start = lower.indexOf(e.original.toLowerCase())
    if (start < 0 || marks.some((m) => start < m.end && start + e.original.length > m.start)) continue
    marks.push({ start, end: start + e.original.length, fix: e.fix })
  }
  marks.sort((a, b) => a.start - b.start)
  const spans: Span[] = []
  let at = 0
  for (const m of marks) {
    if (m.start > at) spans.push({ text: answer.slice(at, m.start) })
    spans.push({ text: answer.slice(m.start, m.end), error: m.fix })
    at = m.end
  }
  if (at < answer.length) spans.push({ text: answer.slice(at) })
  return spans
}
