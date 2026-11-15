import { useState } from 'react'

import { useTranslate } from '../../api/hooks'
import { SpeakButton, Spinner } from '../../components/ui'
import { WordPopover, type AddWord } from './WordPopover'

const WORD = /([A-Za-z][A-Za-z'’-]*)/ // split keeps the words (odd indexes)

/** Vietnamese for the whole sentence, fetched when first shown. */
function SentenceTranslation({ text }: { text: string }) {
  const { data, error, isPending } = useTranslate(text, 'sentence')
  if (isPending) return <Spinner small />
  if (error) return <p className="small fb-error">{error instanceof Error ? error.message : 'Không dịch được.'}</p>
  return <p className="tutor-translation">{data.vietnamese}</p>
}

/** Emma's words are buttons: tap one to see its meaning. */
function ClickableText({ text, onWord }: { text: string; onWord: (word: string) => void }) {
  return (
    <span className="tutor-text">
      {text.split(WORD).map((part, i) =>
        i % 2 === 1 ? (
          <button key={i} type="button" className="word" onClick={() => onWord(part)}>
            {part}
          </button>
        ) : (
          part
        ),
      )}
    </span>
  )
}

/** One of Emma's messages with "Dịch", "Nghe lại" and word lookup. Tools appear once she finished the turn. */
export function TutorLine(props: { text: string; done: boolean; onAddWord?: AddWord }) {
  const { text, done, onAddWord } = props
  const [translated, setTranslated] = useState(false)
  const [word, setWord] = useState<string | null>(null)
  if (!done) return <span className="tutor-text">{text}</span>
  return (
    <>
      <ClickableText text={text} onWord={(w) => setWord((cur) => (cur === w ? null : w))} />
      {word && <WordPopover word={word} context={text} onClose={() => setWord(null)} onAddWord={onAddWord} />}
      {translated && <SentenceTranslation text={text} />}
      <div className="line-actions">
        <button
          type="button"
          className="btn sm ghost"
          onClick={() => setTranslated((t) => !t)}
          aria-pressed={translated}
        >
          🇻🇳 {translated ? 'Ẩn dịch' : 'Dịch'}
        </button>
        <SpeakButton text={text} label="Nghe lại câu của Emma">
          Nghe lại
        </SpeakButton>
      </div>
    </>
  )
}
