/** Checking one written line of the writing drill: the English word and its Vietnamese meaning. */

export type Verdict = 'right' | 'close' | 'wrong' | 'empty'

/** Lowercase, NFC, unified quotes / dashes, single spaces, no trailing punctuation. */
export function normalize(s: string): string {
  return s
    .normalize('NFC')
    .toLowerCase()
    .replace(/[’‘`´]/g, "'")
    .replace(/[‐‑–—]/g, '-')
    .replace(/\s+/g, ' ')
    .replace(/^[\s.,;:!?]+|[\s.,;:!?]+$/g, '')
}

/** Vietnamese text without tone / vowel marks ("hoà" and "hòa" both become "hoa"). */
function stripMarks(s: string): string {
  return s.normalize('NFD').replace(/[̀-ͯ]/g, '').replace(/đ/g, 'd')
}

/** Accepted spellings of an English headword: the word itself, and the part before "(...)" if any. */
function englishForms(word: string): string[] {
  const full = normalize(word)
  const bare = normalize(word.replace(/\([^)]*\)/g, ''))
  return [...new Set([full, bare].filter(Boolean))]
}

/**
 * Accepted Vietnamese meanings: the whole meaning, the meaning without "(...)" notes, and each
 * alternative split by , ; / (so "nhanh, mau" accepts "nhanh").
 */
export function meaningForms(meaning: string): string[] {
  const bare = meaning.replace(/\([^)]*\)/g, '')
  const parts = bare.split(/[,;/]/)
  return [...new Set([meaning, bare, ...parts].map(normalize).filter(Boolean))]
}

/** English must be spelled exactly (case and extra spaces ignored). */
export function checkEnglish(typed: string, word: string): Verdict {
  const t = normalize(typed)
  if (!t) return 'empty'
  return englishForms(word).includes(t) ? 'right' : 'wrong'
}

/** Vietnamese: exact (any accepted form) is right; same letters with different / missing marks is close. */
export function checkMeaning(typed: string, meaning: string): Verdict {
  const t = normalize(typed)
  if (!t) return 'empty'
  const forms = meaningForms(meaning)
  if (forms.includes(t)) return 'right'
  return forms.some((f) => stripMarks(f) === stripMarks(t)) ? 'close' : 'wrong'
}

export type DiffPart = { text: string; kind: 'same' | 'missing' | 'extra' }

/**
 * Letter diff of what was typed against the correct spelling (LCS), for showing the mistake:
 * "missing" letters belong to the answer, "extra" letters were typed but are not in it.
 */
export function letterDiff(typed: string, answer: string): DiffPart[] {
  const a = [...typed.trim()]
  const b = [...answer]
  const n = a.length
  const m = b.length
  const lcs = Array.from({ length: n + 1 }, () => new Array<number>(m + 1).fill(0))
  for (let i = n - 1; i >= 0; i--)
    for (let j = m - 1; j >= 0; j--)
      lcs[i][j] = a[i].toLowerCase() === b[j].toLowerCase() ? lcs[i + 1][j + 1] + 1 : Math.max(lcs[i + 1][j], lcs[i][j + 1])

  const parts: DiffPart[] = []
  const push = (text: string, kind: DiffPart['kind']) => {
    const last = parts.at(-1)
    if (last && last.kind === kind) last.text += text
    else parts.push({ text, kind })
  }
  let i = 0
  let j = 0
  while (i < n && j < m) {
    if (a[i].toLowerCase() === b[j].toLowerCase()) {
      push(b[j], 'same')
      i++
      j++
    } else if (lcs[i + 1][j] >= lcs[i][j + 1]) push(a[i++], 'extra')
    else push(b[j++], 'missing')
  }
  while (i < n) push(a[i++], 'extra')
  while (j < m) push(b[j++], 'missing')
  return parts
}
