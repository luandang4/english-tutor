import { useSyncExternalStore } from 'react'

/** Chrome / Edge / Android fire this before showing their own install UI; we keep it for our button. */
type InstallPromptEvent = Event & { prompt: () => Promise<void>; userChoice: Promise<{ outcome: string }> }

let deferred: InstallPromptEvent | null = null
const listeners = new Set<() => void>()
const notify = () => listeners.forEach((l) => l())

if (typeof window !== 'undefined') {
  window.addEventListener('beforeinstallprompt', (e) => {
    e.preventDefault()
    deferred = e as InstallPromptEvent
    notify()
  })
  window.addEventListener('appinstalled', () => {
    deferred = null
    notify()
  })
}

const subscribe = (l: () => void) => {
  listeners.add(l)
  return () => listeners.delete(l)
}

/** True when the app runs from the home screen / dock instead of a browser tab. */
export const isInstalled = () =>
  window.matchMedia('(display-mode: standalone)').matches ||
  (navigator as Navigator & { standalone?: boolean }).standalone === true

/** iPhone / iPad: no install prompt; the learner uses Share → Add to Home Screen. */
export const isIos = () =>
  /iphone|ipad|ipod/i.test(navigator.userAgent) || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1)

/** The browser's install prompt, if it offered one; `install()` shows it. */
export function useInstallPrompt() {
  const available = useSyncExternalStore(subscribe, () => deferred !== null)
  const install = async () => {
    if (!deferred) return
    const e = deferred
    deferred = null
    notify()
    await e.prompt()
  }
  return { available, install }
}
