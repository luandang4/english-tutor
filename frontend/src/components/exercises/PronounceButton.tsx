import { useEffect, useRef, useState } from 'react'

import { useAssessPronunciation, useMeta } from '../../api/hooks'
import type { PronunciationResult } from '../../api/types'
import { PcmRecorder } from '../../lib/audio/recorder'
import { scoreTone } from '../../lib/format'
import { ErrorBox, Icon, Spinner } from '../ui'
import { useAccess } from '../../lib/access'

/** Record the learner saying `text` and score it with Azure Pronunciation Assessment. */
export function PronounceButton({ text, cardId, label = 'Luyện phát âm' }: { text: string; cardId?: number; label?: string }) {
  const { data: meta } = useMeta()
  const { can } = useAccess()
  const assess = useAssessPronunciation()
  const [recording, setRecording] = useState(false)
  const [level, setLevel] = useState(0)
  const [micError, setMicError] = useState<string | null>(null)
  const rec = useRef<PcmRecorder | null>(null)

  useEffect(() => () => void rec.current?.stop(), [])

  if ((meta && !meta.pronunciation_enabled) || !can('pronunciation')) return null

  const finish = () => {
    const r = rec.current
    if (!r) return
    rec.current = null
    setRecording(false)
    setLevel(0)
    assess.mutate({ pcm: r.stop(), text, cardId })
  }

  const start = async () => {
    setMicError(null)
    assess.reset()
    const r = new PcmRecorder((rms) => setLevel(rms), 15, finish)
    try {
      await r.start()
      rec.current = r
      setRecording(true)
    } catch (e) {
      setMicError(e instanceof Error ? `Không truy cập được micro: ${e.message}` : 'Không truy cập được micro.')
    }
  }

  return (
    <div className="stack" style={{ gap: 8 }}>
      <div className="row">
        <button
          type="button"
          className={`btn sm pron-btn ${recording ? 'recording' : ''}`}
          onClick={recording ? finish : start}
          disabled={assess.isPending}
          style={recording ? { boxShadow: `0 0 0 ${4 + Math.min(10, level * 80)}px rgba(255,95,210,.18)` } : undefined}
        >
          {assess.isPending ? <Spinner small /> : <Icon name={recording ? 'stop' : 'mic'} size={16} />}
          {assess.isPending ? 'Đang chấm…' : recording ? 'Dừng & chấm điểm' : label}
        </button>
        {recording && <span className="small muted">Hãy đọc: “{text}”</span>}
      </div>
      {micError && <div className="alert error">{micError}</div>}
      {assess.error && <ErrorBox error={assess.error} />}
      {assess.data && <PronunciationView result={assess.data} />}
    </div>
  )
}

export function PronunciationView({ result }: { result: PronunciationResult }) {
  const scores: [string, number | null][] = [
    ['Tổng', result.pron_score],
    ['Chính xác', result.accuracy],
    ['Trôi chảy', result.fluency],
    ['Đầy đủ', result.completeness],
    ['Ngữ điệu', result.prosody],
  ]
  return (
    <div className="pron-result">
      <div className="pron-scores">
        {scores
          .filter(([, v]) => v != null)
          .map(([k, v]) => (
            <span key={k}>
              {k} <b className={`tone-${scoreTone(v)}`}>{Math.round(v!)}</b>
            </span>
          ))}
      </div>
      <div className="pron-words">
        {result.words.map((w, i) => (
          <div className="pron-word" key={i} title={w.error_type !== 'None' ? w.error_type : undefined}>
            <span className={`bg-${scoreTone(w.score)}`}>{w.word}</span>
            <div className="phonemes">
              {w.phonemes.map((p, j) => (
                <i key={j} className={`bg-${scoreTone(p.score)}`} title={`/${p.phoneme}/ ${Math.round(p.score)}`}>
                  {p.phoneme}
                </i>
              ))}
            </div>
          </div>
        ))}
      </div>
      {result.engine === 'azure' && result.recognized_text && (
        <span className="small">
          Azure nghe được: <i>“{result.recognized_text}”</i>
        </span>
      )}
      {result.completeness < 50 && (
        <span className="small tone-low">Có vẻ bạn chưa đọc đúng nội dung “{result.reference_text}”. Hãy thử lại.</span>
      )}
      <span className="small muted">
        Âm vị màu đỏ/vàng là chỗ cần luyện thêm.{' '}
        {result.engine === 'local'
          ? 'Chấm ước lượng bằng model âm vị chạy trên máy chủ (miễn phí, kém chính xác hơn Azure).'
          : 'Chấm bởi Azure Speech.'}
      </span>
    </div>
  )
}
