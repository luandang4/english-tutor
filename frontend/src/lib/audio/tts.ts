// Plays English audio from the backend (/api/tts — local Kokoro TTS, cached).
// Falls back to the browser's built-in speech synthesis if the server can't produce audio.

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

export async function playText(text: string): Promise<void> {
  current?.pause()
  const audio = new Audio(`/api/tts?text=${encodeURIComponent(text)}&v=${AUDIO_VERSION}`)
  current = audio
  try {
    await new Promise<void>((resolve, reject) => {
      audio.onended = () => resolve()
      audio.onerror = () => reject(new Error('tts unavailable'))
      audio.play().catch(reject)
    })
  } catch (e) {
    if (current !== audio) return // superseded by a newer click
    if (e instanceof DOMException && e.name === 'NotAllowedError') throw e
    await browserSpeak(text)
  }
}
