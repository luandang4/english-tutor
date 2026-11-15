import { useState } from 'react'

import type { FeedbackTurn } from '../../api/types'
import { SpeakButton } from '../../components/ui'

export type SaveFeedback = (card: FeedbackTurn) => void

/** Correction ("Sửa lỗi") or upgrade ("Nói hay hơn") Emma shows under the learner's sentence. */
export function FeedbackCard({ card, onSave }: { card: FeedbackTurn; onSave?: SaveFeedback }) {
  const [saved, setSaved] = useState(false)
  const correction = card.kind === 'correction'
  return (
    <div className={`note fb-card fb-${card.kind}`}>
      <span className="note-label">{correction ? '✏️ Sửa lỗi' : '✨ Nói hay hơn'}</span>
      <div className="fb-line">
        {card.original && (
          <>
            {correction ? <s className="fb-original">{card.original}</s> : <span className="fb-original">{card.original}</span>}
            <span className="fb-arrow" aria-hidden="true">
              →
            </span>
          </>
        )}
        <b className="fb-better">{card.better}</b>
      </div>
      {card.explain_vi && <p className="fb-reason">{card.explain_vi}</p>}
      <div className="note-actions">
        <SpeakButton text={card.better} label={correction ? 'Nghe câu đúng' : 'Nghe câu hay hơn'} />
        {onSave && (
          <button
            type="button"
            className="btn sm ghost"
            disabled={saved}
            onClick={() => {
              onSave(card)
              setSaved(true)
            }}
          >
            {saved ? 'Đã lưu' : 'Lưu để ôn'}
          </button>
        )}
      </div>
    </div>
  )
}
