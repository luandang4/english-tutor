/** Shared types and options of the writing drill. */

export interface DrillWord {
  word: string
  ipa: string
  part_of_speech: string
  meaning_vi: string
  example_en: string
  example_vi: string
}

export type Goal = '5' | '10' | '20'
export const GOAL_OPTIONS: { value: Goal; label: string; title: string }[] = (['5', '10', '20'] as const).map((g) => ({
  value: g,
  label: `${g} lần`,
  title: `Đánh dấu xong sau ${g} lần viết đúng`,
}))

export interface Line {
  en: string
  vi: string
  ok: boolean
}
