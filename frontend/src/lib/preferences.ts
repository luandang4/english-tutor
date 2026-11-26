import { useCallback, useState } from 'react'

import type { Level } from '../api/types'

// Per-browser conveniences only (real data lives in the backend DB).
function read<T>(key: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(key)
    return raw ? (JSON.parse(raw) as T) : fallback
  } catch {
    return fallback
  }
}

function write(key: string, value: unknown): void {
  try {
    localStorage.setItem(key, JSON.stringify(value))
  } catch {
    /* storage unavailable (private mode) */
  }
}

export function usePreference<T>(key: string, fallback: T): [T, (v: T) => void] {
  const [value, setValue] = useState<T>(() => read(key, fallback))
  const set = useCallback(
    (v: T) => {
      setValue(v)
      write(key, v)
    },
    [key],
  )
  return [value, set]
}

export const useLevel = () => usePreference<Level>('et.level', 'B1')

export type AudioSource = 'auto' | 'google' | 'kokoro'
export const AUDIO_SOURCE_KEY = 'et.audio.source'
export const AUDIO_SOURCES: { value: AudioSource; label: string; hint: string }[] = [
  { value: 'auto', label: 'Tự động', hint: 'Từ đơn: Google Dịch · Câu: Kokoro (khuyên dùng)' },
  { value: 'google', label: 'Google Dịch', hint: 'Giọng Google Translate, cần có mạng' },
  { value: 'kokoro', label: 'Kokoro (AI cục bộ)', hint: 'Chạy trên máy chủ, hợp với câu dài' },
]
// A source saved before it was removed (e.g. the old "dictionary" recordings) falls back to auto.
const known = (v: string): AudioSource => (AUDIO_SOURCES.some((o) => o.value === v) ? (v as AudioSource) : 'auto')
export function useAudioSource(): [AudioSource, (v: AudioSource) => void] {
  const [value, set] = usePreference<AudioSource>(AUDIO_SOURCE_KEY, 'auto')
  return [known(value), set]
}
export const getAudioSource = () => known(read<AudioSource>(AUDIO_SOURCE_KEY, 'auto'))
