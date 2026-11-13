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

export type AudioSource = 'auto' | 'google' | 'dictionary' | 'kokoro'
export const AUDIO_SOURCE_KEY = 'et.audio.source'
export const AUDIO_SOURCES: { value: AudioSource; label: string; hint: string }[] = [
  { value: 'auto', label: 'Tự động', hint: 'Từ đơn: Google Dịch · Câu: Kokoro (khuyên dùng)' },
  { value: 'google', label: 'Google Dịch', hint: 'Giọng Google Translate, cần có mạng' },
  { value: 'dictionary', label: 'Người thật', hint: 'Bản ghi Wiktionary, chỉ có cho một số từ đơn' },
  { value: 'kokoro', label: 'Kokoro (AI cục bộ)', hint: 'Chạy trên máy chủ, hợp với câu dài' },
]
export const useAudioSource = () => usePreference<AudioSource>(AUDIO_SOURCE_KEY, 'auto')
export const getAudioSource = () => read<AudioSource>(AUDIO_SOURCE_KEY, 'auto')
