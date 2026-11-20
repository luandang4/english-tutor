import { useCallback, useSyncExternalStore } from 'react'

// Colour theme: follow the OS, or force light / dark. Stored per browser; index.html applies it before paint.
export type Theme = 'system' | 'light' | 'dark'
export const THEME_OPTIONS: { value: Theme; label: string }[] = [
  { value: 'system', label: 'Theo hệ thống' },
  { value: 'light', label: 'Sáng' },
  { value: 'dark', label: 'Tối' },
]

const KEY = 'et.theme'
const BG = { light: '#f7f2ff', dark: '#0e0a1a' }
const systemLight = matchMedia('(prefers-color-scheme: light)')
const listeners = new Set<() => void>()

function readTheme(): Theme {
  try {
    const v = JSON.parse(localStorage.getItem(KEY) ?? '"system"')
    return v === 'light' || v === 'dark' ? v : 'system'
  } catch {
    return 'system'
  }
}

function resolve(theme: Theme): 'light' | 'dark' {
  if (theme !== 'system') return theme
  return systemLight.matches ? 'light' : 'dark'
}

/** Sets data-theme on <html> (the CSS tokens key off it) and the browser chrome colour. */
function apply(): void {
  const mode = resolve(readTheme())
  document.documentElement.dataset.theme = mode
  document.querySelector('meta[name="theme-color"]')?.setAttribute('content', BG[mode])
  listeners.forEach((l) => l())
}

/** Applies the stored theme and follows OS changes while it is "system". Call once at startup. */
export function initTheme(): void {
  apply()
  systemLight.addEventListener('change', apply)
}

export function setTheme(theme: Theme): void {
  try {
    localStorage.setItem(KEY, JSON.stringify(theme))
  } catch {
    /* storage unavailable (private mode): still switch for this page */
  }
  apply()
}

/** The theme actually on screen right now. */
export function isDarkTheme(): boolean {
  return document.documentElement.dataset.theme !== 'light'
}

function subscribe(l: () => void) {
  listeners.add(l)
  return () => listeners.delete(l)
}

/** [chosen theme, resolved mode, setter]. */
export function useTheme(): [Theme, 'light' | 'dark', (t: Theme) => void] {
  const snapshot = useSyncExternalStore(subscribe, () => `${readTheme()}:${resolve(readTheme())}`)
  const [theme, mode] = snapshot.split(':') as [Theme, 'light' | 'dark']
  return [theme, mode, useCallback((t: Theme) => setTheme(t), [])]
}
