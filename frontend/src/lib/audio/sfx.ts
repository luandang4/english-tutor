// Short "right" / "wrong" cues synthesised with Web Audio: no audio files, no licences, works offline.

let ctx: AudioContext | null = null

function context(): AudioContext | null {
  try {
    ctx ??= new AudioContext()
    if (ctx.state === 'suspended') void ctx.resume()
    return ctx
  } catch {
    return null // no Web Audio (very old browser): stay silent
  }
}

// Answers are graded after an await, outside the click; browsers only allow audio to start inside a user
// gesture, so the context is unlocked on the first tap / key press.
if (typeof window !== 'undefined') {
  const unlock = () => {
    context()
    window.removeEventListener('pointerdown', unlock)
    window.removeEventListener('keydown', unlock)
  }
  window.addEventListener('pointerdown', unlock)
  window.addEventListener('keydown', unlock)
}

type Note = { freq: number; at: number; length: number; type: OscillatorType; volume: number }

type Options = { lowpass?: number; echo?: number }

/** A short decaying echo (delay in seconds) adds a little shimmer. */
function addEcho(ac: AudioContext, from: AudioNode, delay: number): void {
  const d = ac.createDelay()
  const feedback = ac.createGain()
  const wet = ac.createGain()
  d.delayTime.value = delay
  feedback.gain.value = 0.3
  wet.gain.value = 0.35
  from.connect(d)
  d.connect(feedback).connect(d)
  d.connect(wet).connect(ac.destination)
}

function play(notes: Note[], { lowpass, echo }: Options = {}): void {
  const ac = context()
  if (!ac) return
  const out = ac.createGain()
  let tail: AudioNode = out
  if (lowpass) {
    const filter = ac.createBiquadFilter()
    filter.type = 'lowpass'
    filter.frequency.value = lowpass
    tail = out.connect(filter)
  }
  tail.connect(ac.destination)
  if (echo) addEcho(ac, tail, echo)
  const now = ac.currentTime + 0.01
  for (const n of notes) {
    const osc = ac.createOscillator()
    const env = ac.createGain()
    const start = now + n.at
    osc.type = n.type
    osc.frequency.value = n.freq
    // quick attack, exponential fade: a soft "ting" without clicks
    env.gain.setValueAtTime(0.0001, start)
    env.gain.exponentialRampToValueAtTime(n.volume, start + 0.008)
    env.gain.exponentialRampToValueAtTime(0.0001, start + n.length)
    osc.connect(env).connect(out)
    osc.start(start)
    osc.stop(start + n.length + 0.02)
  }
}

/** "Sparkle": four quick rising notes C6 E6 G6 C7 with a light echo. */
export function playCorrect(): void {
  play(
    [
      { freq: 1046.5, at: 0, length: 0.12, type: 'sine', volume: 0.09 },
      { freq: 1318.5, at: 0.05, length: 0.12, type: 'sine', volume: 0.09 },
      { freq: 1568, at: 0.1, length: 0.12, type: 'sine', volume: 0.09 },
      { freq: 2093, at: 0.15, length: 0.35, type: 'sine', volume: 0.1 },
    ],
    { echo: 0.09 },
  )
}

/** Soft low two-note fall (E4 -> C4), filtered so it is not harsh. */
export function playWrong(): void {
  play(
    [
      { freq: 329.6, at: 0, length: 0.16, type: 'triangle', volume: 0.2 },
      { freq: 261.6, at: 0.13, length: 0.28, type: 'triangle', volume: 0.2 },
    ],
    { lowpass: 1400 },
  )
}

export const playResult = (correct: boolean) => (correct ? playCorrect() : playWrong())
