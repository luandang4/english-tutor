import { useEffect, useState } from 'react'
import type { LiveAction } from '../../lib/audio/live-session'

/** Learner silence before each nudge, counted from the end of Emma's audio (or the last mic sound). The last
 * step is not a nudge: Emma says goodbye and the session ends. */
export const SILENCE_NUDGE_MS = [8000, 8000, 8000, 8000]

/** Mic sound restarts the wait only before this many nudges have fired (i.e. for nudges 1 and 2). */
const SOUND_RESETS_UNTIL = 2

export type SilenceNudge = Extract<LiveAction, 'auto_hint' | 'check_in' | 'silent_end'>

const asksQuestion = (text: string) => text.includes('?')

/** First nudge after a question offers a hint; later ones check in and ask again; the last one ends the talk. */
const nudgeFor = (tutorText: string, count: number): SilenceNudge => {
  if (count === SILENCE_NUDGE_MS.length - 1) return 'silent_end'
  return count === 0 && asksQuestion(tutorText) ? 'auto_hint' : 'check_in'
}

/** Timer logic, independent of React so one instance can live for the component's lifetime. */
function createSilenceHint(fire: (nudge: SilenceNudge) => void) {
  let timer: number | null = null
  let deadline = 0
  let nudges = 0 // nudges since the learner last spoke

  const cancel = () => {
    if (timer !== null) window.clearTimeout(timer)
    timer = null
  }
  const wait = (nudge: SilenceNudge) => {
    timer = window.setTimeout(() => {
      timer = null
      const left = deadline - performance.now()
      if (left > 50) return wait(nudge) // a mic sound pushed the deadline back
      nudges += 1
      fire(nudge)
    }, deadline - performance.now())
  }

  return {
    /** Emma's audio ended: wait for the learner, unless the nudges are used up. */
    arm: (tutorText: string) => {
      cancel()
      if (nudges >= SILENCE_NUDGE_MS.length) return
      deadline = performance.now() + SILENCE_NUDGE_MS[nudges]
      wait(nudgeFor(tutorText, nudges))
    },
    /** The mic picked up sound (maybe noise): restart the silence count without using up a nudge. From the
     * third nudge on, only real speech (a transcript) or typing counts, so background noise cannot keep a
     * silent session open. */
    learnerSound: () => {
      if (timer !== null && nudges < SOUND_RESETS_UNTIL) deadline = performance.now() + SILENCE_NUDGE_MS[nudges]
    },
    /** The learner really spoke or typed. */
    learnerSpoke: () => {
      cancel()
      nudges = 0
    },
    /** The learner asked for help with a button: no automatic nudge until they speak again. */
    helpRequested: () => {
      cancel()
      nudges = SILENCE_NUDGE_MS.length
    },
    cancel,
  }
}

/** After Emma finishes, wait for learner silence, then call `fire` with the nudge to send. At most
 * SILENCE_NUDGE_MS.length nudges until the learner speaks, so Emma does not loop. Stable identity: the first
 * `fire` is kept, so it must reach changing values through refs. */
export function useSilenceHint(fire: (nudge: SilenceNudge) => void) {
  const [hint] = useState(() => createSilenceHint(fire))
  useEffect(() => hint.cancel, [hint])
  return hint
}
