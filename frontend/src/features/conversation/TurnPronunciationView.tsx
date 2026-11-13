import { useState } from 'react'

import type { TurnPronunciation } from '../../api/types'
import { SpeakButton } from '../../components/ui'
import { scoreTone } from '../../lib/format'

/** Pronunciation of one spoken turn, measured on the real audio (Azure, or the local model as an estimate).
 * One line by default; tap to see the weak words. */
export function TurnPronunciationView({ result }: { result: TurnPronunciation }) {
  const [open, setOpen] = useState(false)
  const weak = result.weak_words.length
  return (
    <div className="turn-pron">
      <button
        type="button"
        className="turn-pron-summary"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={weak ? open : undefined}
        disabled={!weak}
        title={result.engine === 'local' ? 'Ước lượng bằng model âm vị chạy trên máy chủ' : 'Điểm phát âm (Azure)'}
      >
        <span className={`turn-pron-score tone-${scoreTone(result.score)}`}>Phát âm {result.score}
          {result.engine === 'local' && ' · ước lượng'}
        </span>
        <span className="small muted">{weak ? `${weak} từ cần luyện` : 'Các từ đều rõ'}</span>
        {weak > 0 && <span className="turn-pron-chev" aria-hidden="true">{open ? '▴' : '▾'}</span>}
      </button>
      {open && weak > 0 && (
        <div className="turn-pron-words">
          {result.weak_words.map((w) => (
            <span key={w.word} className="turn-pron-word" title={`Độ chính xác ${w.score}/100`}>
              {w.word}
              <SpeakButton text={w.word} label={`Nghe mẫu “${w.word}”`} />
            </span>
          ))}
        </div>
      )}
    </div>
  )
}
