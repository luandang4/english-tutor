import { useState } from 'react'

import { useTranslate } from '../../api/hooks'
import { Icon, SpeakButton, Spinner } from '../../components/ui'

export interface LookedUpWord {
  word: string
  meaning_vi: string
  ipa: string
  part_of_speech: string
  context: string // the sentence Emma said
}

export type AddWord = (word: LookedUpWord) => void

/** Meaning of one word Emma said, in the context of her sentence. */
export function WordPopover(props: { word: string; context: string; onClose: () => void; onAddWord?: AddWord }) {
  const { word, context, onClose, onAddWord } = props
  const { data, error, isPending } = useTranslate(word, 'word', context)
  const [added, setAdded] = useState(false)
  return (
    <div className="word-pop" role="dialog" aria-label={`Nghĩa của “${word}”`}>
      <div className="word-pop-head">
        <b className="word-pop-word">{word}</b>
        {data?.ipa && <span className="muted small">{data.ipa}</span>}
        {data?.part_of_speech && <span className="chip">{data.part_of_speech}</span>}
        <SpeakButton text={word} label={`Nghe “${word}”`} />
        <button type="button" className="btn icon sm ghost word-pop-close" onClick={onClose} aria-label="Đóng">
          <Icon name="x" />
        </button>
      </div>
      {isPending ? (
        <Spinner small />
      ) : error ? (
        <p className="small fb-error">{error instanceof Error ? error.message : 'Không tra được từ này.'}</p>
      ) : (
        <p>{data.vietnamese}</p>
      )}
      {onAddWord && data && (
        <button
          type="button"
          className="btn sm"
          disabled={added}
          onClick={() => {
            onAddWord({ word, meaning_vi: data.vietnamese, ipa: data.ipa, part_of_speech: data.part_of_speech, context })
            setAdded(true)
          }}
        >
          <Icon name="plus" size={14} /> {added ? 'Đã thêm' : 'Thêm vào bộ ôn'}
        </button>
      )}
    </div>
  )
}
