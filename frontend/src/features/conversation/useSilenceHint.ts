import { useEffect, useState } from 'react'

export const SILENCE_HINT_MS = 6000

const endsWithQuestion = (text: string) => /\?["'”’)]*$/.test(text.trim())

/** Timer logic, independent of React so one instance can live for the component's lifetime. */
function createSilenceHint(fire: () => void) {
  let timer: number | null = null
  let firedSinceLearner = false
  const cancel = () => {
    if (timer !== null) window.clearTimeout(timer)
    timer = null
  }
  return {
    /** Emma finished speaking: start waiting if her last line was a question. */
    arm: (tutorText: string) => {
      cancel()
      if (firedSinceLearner || !endsWithQuestion(tutorText)) return
      timer = window.setTimeout(() => {
        timer = null
        firedSinceLearner = true
        fire()
      }, SILENCE_HINT_MS)
    },
    /** The learner spoke or typed. */
    learnerActive: () => {
      cancel()
      firedSinceLearner = false
    },
    /** The learner asked for help with a button: no automatic hint until they speak again. */
    helpRequested: () => {
      cancel()
      firedSinceLearner = true
    },
    cancel,
  }
}

/** After Emma asks a question, wait SILENCE_HINT_MS of learner silence, then call `fire` (once). It is not
 * re-armed until the learner has spoken, so Emma's "Do you need a hint?" does not loop. Stable identity:
 * the first `fire` is kept, so it must reach changing values through refs. */
export function useSilenceHint(fire: () => void) {
  const [hint] = useState(() => createSilenceHint(fire))
  useEffect(() => hint.cancel, [hint])
  return hint
}
