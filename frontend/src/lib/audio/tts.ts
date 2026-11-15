// Plays English audio from the backend (/api/tts — free sources, cached on the server).
// Falls back to the browser's built-in speech synthesis if the server can't produce audio.
import { getAudioSource } from '../preferences'

// Bump when the server-side voice choice changes, so browsers don't replay stale cached audio.
const AUDIO_VERSION = 3

let current: HTMLAudioElement | null = null

function browserSpeak(text: string): Promise<void> {
  return new Promise((resolve, reject) => {
    if (!('speechSynthesis' in window)) return reject(new Error('Trình duyệt không hỗ trợ đọc văn bản.'))
    speechSynthesis.cancel()
    const u = new SpeechSynthesisUtterance(text)
    u.lang = 'en-US'
    u.rate = 0.9
    const voice = speechSynthesis.getVoices().find((v) => v.lang === 'en-US')
    if (voice) u.voice = voice
    u.onend = () => resolve()
    u.onerror = () => reject(new Error('Không phát được âm thanh.'))
    speechSynthesis.speak(u)
  })
}

/** Play an audio URL; resolves when finished. Throws if it can't play. */
async function playUrl(url: string): Promise<boolean> {
  current?.pause()
  const audio = new Audio(url)
  current = audio
  try {
    await new Promise<void>((resolve, reject) => {
      audio.onended = () => resolve()
      audio.onerror = () => reject(new Error('audio unavailable'))
      audio.play().catch(reject)
    })
    return true
  } catch (e) {
    if (current !== audio) return true // superseded by a newer click
    if (e instanceof DOMException && e.name === 'NotAllowedError') throw e
    return false
  }
}

export async function playText(text: string): Promise<void> {
  const url = `/api/tts?text=${encodeURIComponent(text)}&source=${getAudioSource()}&v=${AUDIO_VERSION}`
  if (!(await playUrl(url))) await browserSpeak(text)
}

/** Play a word addressed by URL (listening questions: the page must not know the word itself). */
export async function playWordUrl(path: string): Promise<void> {
  const sep = path.includes('?') ? '&' : '?'
  if (!(await playUrl(`${path}${sep}source=${getAudioSource()}&v=${AUDIO_VERSION}`)))
    throw new Error('Không phát được âm thanh.')
}

const MAX_CHUNK = 280 // the server's TTS takes at most 300 characters per request
let generation = 0

/** Split text into sentence groups the server can synthesize; drops "…" placeholders of sentence frames. */
export function speechChunks(text: string): string[] {
  const clean = text.replace(/\s*(…|\.\.\.)\s*/g, ' ').replace(/\s+/g, ' ').trim()
  const sentences = clean.match(/[^.!?]+[.!?]*/g) ?? []
  const chunks: string[] = []
  for (const s of sentences.map((x) => x.trim()).filter(Boolean)) {
    const last = chunks.at(-1)
    if (last && last.length + s.length + 1 <= MAX_CHUNK) chunks[chunks.length - 1] = `${last} ${s}`
    else chunks.push(s.slice(0, MAX_CHUNK))
  }
  return chunks
}

/** Play text of any length, sentence group by group. A newer call stops an older one. */
export async function playLongText(text: string): Promise<void> {
  const mine = ++generation
  for (const chunk of speechChunks(text)) {
    if (mine !== generation) return
    await playText(chunk)
  }
}
