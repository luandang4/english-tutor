// Live transcript lines. Mirrors services/conversation/transcript.py so the screen and the saved history show
// the same order: feedback cards go right under the learner's sentence, other cards at the end.
import { useState } from 'react'

import type { ConversationTurn, FeedbackTurn, HintTurn, TurnPronunciation } from '../../api/types'
import type { FeedbackCard, HintCard } from '../../lib/audio/live-session'

export interface Notice {
  role: 'notice'
  text: string
  tone: 'info' | 'error'
}

export type Line = (ConversationTurn | Notice) & { id: number; typed?: boolean }

const isSpeech = (l: Line) => l.role === 'user' || l.role === 'tutor'

/** Index right after the last learner line and any feedback cards already under it. */
function afterLastUser(lines: Line[]): number {
  const i = lines.findLastIndex((l) => l.role === 'user')
  if (i < 0) return lines.length
  let j = i + 1
  while (j < lines.length && lines[j].role === 'feedback') j++
  return j
}

const toFeedbackTurn = (c: FeedbackCard): FeedbackTurn => ({ role: 'feedback', text: c.better, ...c })
const toHintTurn = (c: HintCard): HintTurn => ({ role: 'hint', text: c.question_en, ...c })

function stripLine(line: Line & ConversationTurn): ConversationTurn {
  const turn: Partial<Line> = { ...line }
  delete turn.id
  delete turn.typed
  return turn as ConversationTurn
}

/** Spoken lines after this one (0 = the latest exchange); drives the fade of older lines. */
export function ages(lines: Line[]): number[] {
  const out = new Array<number>(lines.length)
  let seen = 0
  for (let i = lines.length - 1; i >= 0; i--) {
    out[i] = seen
    if (isSpeech(lines[i])) seen++
  }
  return out
}

/** Transcript operations. They only use closure state and React state setters, so one instance stays valid for
 * the component's lifetime (safe to call from audio callbacks and animation frames). */
function createActions(setLines: (l: Line[]) => void, setOpenId: (id: number | null) => void) {
  let lines: Line[] = []
  let open: 'user' | 'tutor' | null = null // role of the line still receiving fragments
  let nextId = 1

  const commit = (next: Line[]) => {
    lines = next
    setLines(next)
    const last = next.at(-1)
    setOpenId(open && last?.role === open ? last.id : null)
  }
  const make = (line: ConversationTurn | Notice, typed = false): Line => ({ ...line, id: nextId++, typed })
  const append = (line: ConversationTurn | Notice, typed = false) => {
    open = null
    commit([...lines, make(line, typed)])
  }

  return {
    /** Text of the latest spoken line if it is Emma's (used to detect a question). */
    lastTutorText: () => {
      const last = lines.findLast(isSpeech)
      return last?.role === 'tutor' ? last.text : ''
    },
    hasLearnerLine: () => lines.some((l) => l.role === 'user'),
    turns: (): ConversationTurn[] =>
      lines.filter((l): l is Line & ConversationTurn => l.role !== 'notice').map(stripLine),
    closeLine: () => {
      open = null
      setOpenId(null)
    },
    clear: () => {
      open = null
      commit([])
    },
    fragment: (role: 'user' | 'tutor', text: string) => {
      const last = lines.at(-1)
      if (open === role && last?.role === role) {
        commit([...lines.slice(0, -1), { ...last, text: last.text + text }])
      } else {
        open = role
        commit([...lines, make({ role, text })])
      }
    },
    typed: (text: string) => append({ role: 'user', text }, true),
    notice: (text: string, tone: Notice['tone']) => append({ role: 'notice', text, tone }),
    translation: (english: string, vietnamese: string) =>
      append({ role: 'translation', text: vietnamese, source: english }),
    hint: (card: HintCard) => append(toHintTurn(card)),
    feedback: (card: FeedbackCard) => {
      const at = afterLastUser(lines)
      commit([...lines.slice(0, at), make(toFeedbackTurn(card)), ...lines.slice(at)])
    },
    /** Azure scores a spoken turn shortly after Emma answered it: attach to the latest unscored spoken line. */
    pronunciation: (result: TurnPronunciation) => {
      const i = lines.findLastIndex((l) => l.role === 'user' && !l.typed && !l.pronunciation)
      if (i >= 0) commit(lines.map((l, j) => (j === i ? { ...l, pronunciation: result } : l)))
    },
  }
}

export type TranscriptActions = ReturnType<typeof createActions>

/** Live transcript: fragments merge into the open line until the speaker changes or the turn ends.
 * `openId` is the line still receiving fragments (Emma mid-sentence); `actions` never changes. */
export function useLiveTranscript() {
  const [lines, setLines] = useState<Line[]>([])
  const [openId, setOpenId] = useState<number | null>(null)
  const [actions] = useState(() => createActions(setLines, setOpenId))
  return { lines, openId, actions }
}
