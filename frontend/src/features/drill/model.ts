/** Shared types and options of the writing drill. */

export interface DrillWord {
  word: string
  ipa: string
  part_of_speech: string
  meaning_vi: string
  example_en: string
  example_vi: string
}

/** What the model card shows: both sides, or one side covered so the learner writes it from memory. */
export type Cover = 'none' | 'english' | 'meaning'

export const COVER_OPTIONS: { value: Cover; label: string; title: string }[] = [
  { value: 'none', label: 'Xem mẫu', title: 'Hiện cả từ và nghĩa, chép lại' },
  { value: 'english', label: 'Che từ', title: 'Che từ tiếng Anh, chỉ hiện nghĩa: tự viết từ' },
  { value: 'meaning', label: 'Che nghĩa', title: 'Che nghĩa, chỉ hiện từ tiếng Anh: tự viết nghĩa' },
]

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
