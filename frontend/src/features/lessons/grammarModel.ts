import type { FormRow, GrammarBlock, GrammarSection } from '../../api/types'

export type RowKind = 'positive' | 'negative' | 'question' | 'other'

const LABEL_KIND: [RegExp, RowKind][] = [
  [/khẳng định|affirmative|positive/i, 'positive'],
  [/phủ định|negative/i, 'negative'],
  [/nghi vấn|câu hỏi|question/i, 'question'],
]
const KIND_LABEL = { positive: 'Khẳng định', negative: 'Phủ định', question: 'Nghi vấn' }

export function rowKind(label: string): RowKind {
  return LABEL_KIND.find(([re]) => re.test(label))?.[1] ?? 'other'
}

function patternKind(pattern: string): Exclude<RowKind, 'other'> {
  if (pattern.trim().endsWith('?')) return 'question'
  if (/\bnot\b|n't\b/i.test(pattern)) return 'negative'
  return 'positive'
}

/** Oldest lessons: every structure in one string joined by "|". */
function rowsFromString(formula: string): FormRow[] {
  const parts = formula.split(/\s+\|\s+/).map((p) => p.trim()).filter(Boolean)
  const looksLikeForms = parts.length > 1 && parts.some((p) => patternKind(p) !== 'positive')
  return parts.map((part) => {
    const labelled = /^([^:+?|]{1,40}):\s*(.+)$/.exec(part)
    if (labelled) return { label_vi: labelled[1], pattern: labelled[2], example_en: '' }
    return { label_vi: looksLikeForms ? KIND_LABEL[patternKind(part)] : '', pattern: part, example_en: '' }
  })
}

/** "Hiện tại đơn - Khẳng định" rows become one forms block per grammar point. */
function formsFromRows(rows: FormRow[]): GrammarBlock[] {
  const groups = new Map<string, FormRow[]>()
  for (const r of rows) {
    const m = /^(.+?)\s+[-–:]\s+(.+)$/.exec(r.label_vi)
    const [title, label] = m ? [m[1], m[2]] : ['', r.label_vi]
    groups.set(title, [...(groups.get(title) ?? []), { ...r, label_vi: label }])
  }
  return [...groups].map(([title, rows]) => ({ kind: 'forms', title, rows }))
}

/** The section as blocks; lessons made before blocks existed are converted on the fly. */
export function sectionBlocks(s: GrammarSection): GrammarBlock[] {
  if (s.blocks) return s.blocks
  const rows = s.formulas ?? (s.formula ? rowsFromString(s.formula) : [])
  const text: GrammarBlock[] = s.explanation_vi ? [{ kind: 'text', text_vi: s.explanation_vi }] : []
  return [...formsFromRows(rows), ...text]
}

const norm = (t: string) => t.trim().toLowerCase()

/** Colour slot (0-3) per grammar point, in order of first appearance, so a tense keeps its colour everywhere. */
export function pointPalette(sections: GrammarSection[]): (title?: string) => number | undefined {
  const keys: string[] = []
  const add = (t?: string) => {
    if (t && !keys.includes(norm(t))) keys.push(norm(t))
  }
  for (const b of sections.flatMap(sectionBlocks)) {
    if (b.kind === 'forms') add(b.title)
    if (b.kind === 'compare') b.columns?.forEach((c) => add(c.title))
  }
  return (title) => {
    if (!title) return undefined
    const t = norm(title)
    const i = keys.indexOf(t)
    if (i >= 0) return i % 4
    // "Dấu hiệu Hiện tại đơn" -> colour of "hiện tại đơn" (longest name contained in the title)
    const hit = keys.filter((k) => t.includes(k)).sort((a, b) => b.length - a.length)[0]
    return hit === undefined ? undefined : keys.indexOf(hit) % 4
  }
}
