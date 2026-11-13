import type { TurnPronunciation } from '../../api/types'
import { SpeakButton } from '../../components/ui'
import { scoreTone } from '../../lib/format'

/** Pronunciation of one spoken turn, measured on the real audio (Azure, or the local model as an estimate). */
export function TurnPronunciationView({ result }: { result: TurnPronunciation }) {
  return (
    <div className="turn-pron">
      <span
        className={`turn-pron-score tone-${scoreTone(result.score)}`}
        title={result.engine === 'local' ? 'Ước lượng bằng model âm vị chạy trên máy chủ' : 'Điểm phát âm (Azure)'}
      >
        Phát âm {result.score}
        {result.engine === 'local' && ' · ước lượng'}
      </span>
      {result.weak_words.length === 0 ? (
        <span className="small muted">Các từ đều rõ</span>
      ) : (
        result.weak_words.map((w) => (
          <span key={w.word} className="turn-pron-word" title={`Độ chính xác ${w.score}/100`}>
            {w.word}
            <SpeakButton text={w.word} label={`Nghe mẫu “${w.word}”`} />
          </span>
        ))
      )}
    </div>
  )
}
