import type { FormRow, GrammarBlock } from '../../api/types'
import { SpeakButton } from '../../components/ui'
import { Markdown } from '../../components/ui/Markdown'
import { rowKind } from './grammarModel'
import './grammar.css'

type Palette = (title?: string) => number | undefined

const SIGN = { positive: '+', negative: '−', question: '?', other: '' }
const point = (slot: number | undefined) => (slot === undefined ? '' : ` point-${slot}`)

function Example({ text }: { text: string }) {
  if (!text) return null
  return (
    <span className="g-example">
      {text}
      <SpeakButton text={text} label="Nghe câu ví dụ" />
    </span>
  )
}

function FormRows({ rows }: { rows: FormRow[] }) {
  return (
    <div className="g-rows">
      {rows.map((r, i) => {
        const kind = rowKind(r.label_vi)
        return (
          <div key={i} className={`g-row kind-${kind}${r.label_vi ? '' : ' unlabelled'}`}>
            {r.label_vi && (
              <span className="g-label">
                {SIGN[kind] && <b aria-hidden="true">{SIGN[kind]}</b>}
                {r.label_vi}
              </span>
            )}
            <div className="g-row-body">
              <code className="g-pattern">{r.pattern}</code>
              <Example text={r.example_en} />
            </div>
          </div>
        )
      })}
    </div>
  )
}

function FormsCard({ block, palette }: { block: GrammarBlock; palette: Palette }) {
  return (
    <div className={`g-card${point(palette(block.title))}`}>
      {block.title && <h3 className="g-card-title">{block.title}</h3>}
      <FormRows rows={block.rows ?? []} />
    </div>
  )
}

function Compare({ block, palette }: { block: GrammarBlock; palette: Palette }) {
  return (
    <div className="g-grid">
      {block.columns?.map((c, i) => (
        <div key={i} className={`g-card${point(palette(c.title))}`}>
          <h3 className="g-card-title">{c.title}</h3>
          <ul className="g-points">
            {c.points_vi.map((p, j) => (
              <li key={j}>{p}</li>
            ))}
          </ul>
          <Example text={c.example_en} />
        </div>
      ))}
    </div>
  )
}

function Table({ block }: { block: GrammarBlock }) {
  return (
    <div className="g-table-wrap">
      <table className="g-table">
        {block.title && <caption>{block.title}</caption>}
        {!!block.headers?.length && (
          <thead>
            <tr>
              {block.headers.map((h, i) => (
                <th key={i}>{h}</th>
              ))}
            </tr>
          </thead>
        )}
        <tbody>
          {block.table_rows?.map((r, i) => (
            <tr key={i}>
              {r.cells.map((c, j) => (
                <td key={j}>{c}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function WordList({ block, palette }: { block: GrammarBlock; palette: Palette }) {
  return (
    <div className={`g-words${point(palette(block.title))}`}>
      {block.title && <span className="g-words-title">{block.title}</span>}
      <div className="g-chips">
        {block.words?.map((w) => (
          <span key={w} className="g-chip">
            {w}
          </span>
        ))}
      </div>
    </div>
  )
}

function Block({ block, palette }: { block: GrammarBlock; palette: Palette }) {
  switch (block.kind) {
    case 'text':
      return block.text_vi ? <Markdown>{block.text_vi}</Markdown> : null
    case 'tip':
      return (
        <div className="g-tip">
          <span aria-hidden="true">💡</span>
          <Markdown>{block.text_vi ?? ''}</Markdown>
        </div>
      )
    case 'compare':
      return <Compare block={block} palette={palette} />
    case 'table':
      return <Table block={block} />
    case 'word_list':
      return <WordList block={block} palette={palette} />
    case 'forms':
      return <FormsCard block={block} palette={palette} />
    default:
      return null
  }
}

/** Consecutive forms blocks (e.g. two tenses) sit side by side; every other block takes the full width. */
function groupForms(blocks: GrammarBlock[]): GrammarBlock[][] {
  return blocks.reduce<GrammarBlock[][]>((groups, b) => {
    const last = groups.at(-1)
    if (b.kind === 'forms' && last?.[0].kind === 'forms') last.push(b)
    else groups.push([b])
    return groups
  }, [])
}

export function SectionBlocks({ blocks, palette }: { blocks: GrammarBlock[]; palette: Palette }) {
  return (
    <>
      {groupForms(blocks).map((group, i) =>
        group.length > 1 ? (
          <div key={i} className="g-grid">
            {group.map((b, j) => (
              <FormsCard key={j} block={b} palette={palette} />
            ))}
          </div>
        ) : (
          <Block key={i} block={group[0]} palette={palette} />
        ),
      )}
    </>
  )
}
