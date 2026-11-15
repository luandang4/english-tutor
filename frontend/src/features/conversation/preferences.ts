import type { Enhancement } from '../../lib/audio/live-session'
import { usePreference } from '../../lib/preferences'

export const CUSTOM = 'custom' // learner-defined scenario (title + wishes), see services/conversation/live.py

export type FontSize = 's' | 'm' | 'l'

export const ENHANCEMENT_OPTIONS: { value: Enhancement; label: string; title: string }[] = [
  { value: 'low', label: 'Ít', title: 'Khoảng 1 lần mỗi 5 lượt nói' },
  { value: 'medium', label: 'Vừa', title: 'Khoảng 1 lần mỗi 3 lượt nói (A1–A2 thưa hơn)' },
  { value: 'high', label: 'Nhiều', title: 'Hầu như mỗi câu còn đơn giản' },
]
export const FONT_SIZES: FontSize[] = ['s', 'm', 'l']
export const FONT_LABEL: Record<FontSize, string> = { s: 'Chữ nhỏ', m: 'Chữ vừa', l: 'Chữ lớn' }

/** Conversation settings remembered in this browser. */
export function useConvoPreferences() {
  const [scenario, setScenario] = usePreference('et.convo.scenario', 'free_talk')
  const [customTitle, setCustomTitle] = usePreference('et.convo.customTitle', '')
  const [customRequest, setCustomRequest] = usePreference('et.convo.customRequest', '')
  // Headphones on: the mic stays open while Emma talks (you can interrupt). Off: the mic is paused while she
  // speaks, so speaker sound is not picked up as the learner's voice.
  const [headphones, setHeadphones] = usePreference('et.convo.headphones', false)
  const [enhancement, setEnhancement] = usePreference<Enhancement>('et.convo.enhancement', 'medium')
  const [fontSize, setFontSize] = usePreference<FontSize>('et.convo.fontSize', 'm')
  return {
    scenario,
    setScenario,
    customTitle,
    setCustomTitle,
    customRequest,
    setCustomRequest,
    headphones,
    setHeadphones,
    enhancement,
    setEnhancement,
    fontSize,
    setFontSize,
  }
}

export type ConvoPreferences = ReturnType<typeof useConvoPreferences>
