import { useState } from 'react'

import type { HintTurn } from '../../api/types'
import { Icon, SpeakButton, Spinner } from '../../components/ui'
import { playLongText } from '../../lib/audio/tts'

/** A sentence frame the learner can tap to hear (the "…" gap is skipped when read aloud). */
function FrameButton({ frame }: { frame: string }) {
  const [playing, setPlaying] = useState(false)
  return (
    <button
      type="button"
      className="hint-frame"
      title="Bấm để nghe"
      onClick={() => {
        setPlaying(true)
        playLongText(frame)
          .catch(() => undefined)
          .finally(() => setPlaying(false))
      }}
    >
      {playing ? <Spinner small /> : <Icon name="volume" size={15} />}
      <span>{frame}</span>
    </button>
  )
}

/** "Gợi ý trả lời": Emma's question, sentence frames and keywords (Vietnamese only at A1–B1). */
export function HintCard({ card }: { card: HintTurn }) {
  const question = card.question_en || card.text
  return (
    <div className="note hint">
      <span className="note-label">💡 Gợi ý trả lời</span>
      {question && (
        <p className="hint-question">
          <b>{question}</b>
          {card.question_vi && <span className="muted"> · {card.question_vi}</span>}
        </p>
      )}
      {card.frames.length > 0 && (
        <div className="hint-frames">
          <span className="small muted">Bắt đầu câu bằng:</span>
          {card.frames.map((f) => (
            <FrameButton key={f} frame={f} />
          ))}
        </div>
      )}
      {card.keywords.length > 0 && (
        <div className="hint-keywords">
          {card.keywords.map((k) => (
            <span key={k.en} className="hint-keyword">
              <b>{k.en}</b>
              {k.vi && <span className="muted">{k.vi}</span>}
              <SpeakButton text={k.en} label={`Nghe “${k.en}”`} />
            </span>
          ))}
        </div>
      )}
    </div>
  )
}
