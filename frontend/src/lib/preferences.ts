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
