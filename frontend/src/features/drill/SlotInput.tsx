import type { KeyboardEvent, Ref } from 'react'

/** Characters of the answer grouped by word, keeping each character's position (spaces split the groups). */
function wordGroups(answer: string): { ch: string; i: number }[][] {
  const groups: { ch: string; i: number }[][] = [[]]
  ;[...answer].forEach((ch, i) => {
    if (ch === ' ') groups.push([])
    else groups[groups.length - 1].push({ ch, i })
  })
  return groups.filter((g) => g.length)
}

/**
 * Text box shown as one blank "_" per letter of the answer: each typed character appears on its blank.
 * A real (transparent) input sits on top, so IME (Vietnamese Telex) and mobile keyboards work as usual.
 */
export function SlotInput({ ref, ...props }: {
  answer: string
  value: string
  onChange: (v: string) => void
  onKeyDown: (e: KeyboardEvent<HTMLInputElement>) => void
  label: string
  ref?: Ref<HTMLInputElement>
  autoFocus?: boolean
  lang: 'en' | 'vi'
  enterKeyHint: 'next' | 'done'
}) {
  const typed = [...props.value]
  const length = [...props.answer].length
  const extra = typed.slice(length).join('')
  return (
    <div className={`slots slots-${props.lang}`}>
      <div className="slots-row" aria-hidden="true">
        {wordGroups(props.answer).map((g) => (
          <span className="slots-word" key={g[0].i}>
            {g.map(({ i }) => (
              <span key={i} className={`slot${i === typed.length ? ' cur' : ''}${typed[i] && typed[i] !== ' ' ? ' filled' : ''}`}>
                {typed[i] && typed[i] !== ' ' ? typed[i] : ''}
              </span>
            ))}
          </span>
        ))}
        {extra && <span className="slots-extra">{extra}</span>}
      </div>
      <input
        ref={ref}
        className="slots-input"
        value={props.value}
        onChange={(e) => props.onChange(e.target.value)}
        onKeyDown={props.onKeyDown}
        autoFocus={props.autoFocus}
        autoComplete="off"
        autoCorrect="off"
        autoCapitalize="none"
        spellCheck={false}
        enterKeyHint={props.enterKeyHint}
        lang={props.lang}
        aria-label={props.label}
      />
    </div>
  )
}
