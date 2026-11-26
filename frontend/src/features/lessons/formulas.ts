import type { GrammarFormula, GrammarSection } from '../../api/types'

export type FormulaKind = 'positive' | 'negative' | 'question' | 'other'
export type FormulaRow = GrammarFormula & { kind: FormulaKind }

const LABEL_KIND: [RegExp, FormulaKind][] = [
  [/khẳng định|affirmative|positive/i, 'positive'],
  [/phủ định|negative/i, 'negative'],
  [/nghi vấn|câu hỏi|question/i, 'question'],
]

const KIND_LABEL: Record<Exclude<FormulaKind, 'other'>, string> = {
  positive: 'Khẳng định',
  negative: 'Phủ định',
  question: 'Nghi vấn',
}

function kindOfLabel(label: string): FormulaKind {
  return LABEL_KIND.find(([re]) => re.test(label))?.[1] ?? 'other'
}

function kindOfPattern(pattern: string): FormulaKind {
  if (pattern.trim().endsWith('?')) return 'question'
  if (/\bnot\b|n't\b/i.test(pattern)) return 'negative'
  return 'positive'
}

/** Old lessons store every structure in one string joined by "|"; split it into labelled rows. */
function fromLegacy(formula: string): FormulaRow[] {
  const parts = formula.split(/\s+\|\s+/).map((p) => p.trim()).filter(Boolean)
  const looksLikeForms = parts.length > 1 && parts.some((p) => kindOfPattern(p) !== 'positive')
  return parts.map((part) => {
    const labelled = /^([^:+?|]{1,40}):\s*(.+)$/.exec(part)
    if (labelled) return { label_vi: labelled[1], pattern: labelled[2], example_en: '', kind: kindOfLabel(labelled[1]) }
    if (!looksLikeForms) return { label_vi: '', pattern: part, example_en: '', kind: 'other' }
    const kind = kindOfPattern(part)
    return { label_vi: KIND_LABEL[kind as keyof typeof KIND_LABEL], pattern: part, example_en: '', kind }
  })
}

/** The section's structures, one row each (affirmative / negative / question ...). */
export function formulaRows(section: GrammarSection): FormulaRow[] {
  if (section.formulas) return section.formulas.map((f) => ({ ...f, kind: kindOfLabel(f.label_vi) }))
  return section.formula ? fromLegacy(section.formula) : []
}
