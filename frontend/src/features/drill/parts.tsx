import { useEffect, useRef } from 'react'

import { Icon, SpeakButton } from '../../components/ui'
import type { DiffPart } from './check'
import { wordKey } from './counts'
import type { DrillWord, Line } from './model'

/** The word to copy: spelling, sound, meaning and an example. The eye button hides all text (sound stays). */
export function ModelCard({ w, hidden, onToggle }: { w: DrillWord; hidden: boolean; onToggle: () => void }) {
  return (
    <div className={`drill-model${hidden ? ' masked' : ''}`}>
      <div className="drill-model-en">
        {hidden ? <span className="drill-mask">• • •</span> : <span className="drill-word">{w.word}</span>}
        <SpeakButton text={w.word} label="Nghe từ" />
        {!hidden && w.ipa && <span className="ipa">{w.ipa}</span>}
        {!hidden && w.part_of_speech && <span className="pos">{w.part_of_speech}</span>}
        <button
          type="button"
          className="btn icon sm ghost drill-eye"
          onClick={onToggle}
          title={hidden ? 'Hiện từ và nghĩa' : 'Ẩn từ và nghĩa (tự nhớ để viết)'}
          aria-label={hidden ? 'Hiện từ và nghĩa' : 'Ẩn từ và nghĩa'}
          aria-pressed={hidden}
        >
          <Icon name={hidden ? 'eyeOff' : 'eye'} />
        </button>
      </div>
      <div className="drill-model-vi">{hidden ? <span className="drill-mask">• • •</span> : w.meaning_vi}</div>
      {!hidden && w.example_en && (
        <div className="drill-example">
          <span>{w.example_en}</span>
          {w.example_vi && <span className="muted">{w.example_vi}</span>}
        </div>
      )}
    </div>
  )
}

/** Wrong letters of the last English attempt: green = right, struck red = typed by mistake, underlined = missing. */
export function SpellingDiff({ parts }: { parts: DiffPart[] }) {
  return (
    <span className="drill-diff">
      {parts.map((p, i) => (
        <span key={i} className={`diff-${p.kind}`}>
          {p.text}
        </span>
      ))}
    </span>
  )
}

/** Lines written in this session for the current word, like a notebook page; keeps the newest line in view. */
export function Notebook({ lines }: { lines: Line[] }) {
  const list = useRef<HTMLOListElement>(null)
  // scroll the notebook itself, never the page (the inputs must stay in view)
  useEffect(() => {
    if (list.current) list.current.scrollTop = list.current.scrollHeight
  }, [lines.length])
  if (!lines.length) return <p className="small muted drill-notebook-empty">Các dòng bạn viết sẽ hiện ở đây.</p>
  const numbers = lines.reduce<number[]>((acc, l) => [...acc, (acc.at(-1) ?? 0) + (l.ok ? 1 : 0)], [])
  return (
    <ol className="drill-notebook" ref={list}>
      {lines.map((l, i) => (
        <li key={i} className={l.ok ? 'ok' : 'bad'}>
          <span className="drill-line-no">{l.ok ? numbers[i] : '✗'}</span>
          <span className="drill-line-en">{l.en || '—'}</span>
          <span className="drill-line-vi">{l.vi || '—'}</span>
        </li>
      ))}
    </ol>
  )
}

/** All words of the drill with how many correct lines each has (this session / all time). */
export function WordStrip(props: {
  words: DrillWord[]
  index: number
  onPick: (i: number) => void
  session: Record<string, Line[]>
  totals: Record<string, number>
  goal: number
}) {
  const strip = useRef<HTMLDivElement>(null)
  const active = useRef<HTMLButtonElement>(null)
  // bring the current word into view by scrolling the strip sideways only
  useEffect(() => {
    const box = strip.current
    const chip = active.current
    if (!box || !chip) return
    const left = chip.offsetLeft // the strip is position: relative
    if (left < box.scrollLeft) box.scrollLeft = left - 8
    else if (left + chip.offsetWidth > box.scrollLeft + box.clientWidth) box.scrollLeft = left + chip.offsetWidth - box.clientWidth + 8
  }, [props.index])
  return (
    <div className="drill-strip" ref={strip} role="tablist" aria-label="Danh sách từ">
      {props.words.map((w, i) => {
        const done = (props.session[wordKey(w.word)] ?? []).filter((l) => l.ok).length
        const total = props.totals[wordKey(w.word)] ?? 0
        return (
          <button
            key={w.word + i}
            type="button"
            role="tab"
            aria-selected={i === props.index}
            ref={i === props.index ? active : undefined}
            className={`drill-chip${i === props.index ? ' on' : ''}${done >= props.goal ? ' done' : ''}`}
            onClick={() => props.onPick(i)}
            title={`Buổi này ${done} lần · tổng ${total} lần`}
          >
            <span>{w.word}</span>
            <b>{done}</b>
          </button>
        )
      })}
    </div>
  )
}
