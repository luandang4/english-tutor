import { useEffect, useState, type ReactNode } from 'react'
import { Link } from 'react-router-dom'

import { useMeta } from '../../api/hooks'
import type { LessonStatus, Level } from '../../api/types'
import { playText } from '../../lib/audio/tts'
import { AUDIO_SOURCES, useAudioSource, type AudioSource } from '../../lib/preferences'
import { STATUS_LABEL, scoreTone } from '../../lib/format'
import { Icon } from './Icon'

export { Icon, type IconName } from './Icon'

export function PageHeader(props: {
  title: ReactNode
  subtitle?: ReactNode
  actions?: ReactNode
  back?: { to: string; label: string }
}) {
  return (
    <header className="page-header">
      <div>
        {props.back && (
          <Link className="back-link" to={props.back.to}>
            <Icon name="arrowLeft" size={16} /> {props.back.label}
          </Link>
        )}
        <h1>{props.title}</h1>
        {props.subtitle && <p>{props.subtitle}</p>}
      </div>
      {props.actions && <div className="actions">{props.actions}</div>}
    </header>
  )
}

export const Spinner = ({ small }: { small?: boolean }) => <span className={`spinner ${small ? 'sm' : ''}`} role="status" />

export function Loading({ label = 'Đang tải…' }: { label?: string }) {
  return (
    <div className="center-state">
      <Spinner />
      <span>{label}</span>
    </div>
  )
}

export function EmptyState(props: { emoji: string; title: string; text?: ReactNode; action?: ReactNode }) {
  return (
    <div className="center-state">
      <div className="emoji">{props.emoji}</div>
      <h3>{props.title}</h3>
      {props.text && <p>{props.text}</p>}
      {props.action}
    </div>
  )
}

export function ErrorBox({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const message = error instanceof Error ? error.message : String(error)
  return (
    <div className="alert error row">
      <span className="spacer">{message}</span>
      {onRetry && (
        <button className="btn sm" onClick={onRetry}>
          <Icon name="refresh" size={16} /> Thử lại
        </button>
      )}
    </div>
  )
}

export function StatusBadge({ status }: { status: LessonStatus }) {
  return <span className={`badge ${status}`}>{STATUS_LABEL[status]}</span>
}

export function ScoreRing({ score, size = 72, label }: { score: number | null; size?: number; label?: string }) {
  const stroke = Math.max(5, size / 11)
  const r = (size - stroke) / 2
  const c = 2 * Math.PI * r
  const value = score ?? 0
  const tone = scoreTone(score)
  const color = { good: 'var(--good)', ok: 'var(--ok)', low: 'var(--danger)', none: 'var(--muted)' }[tone]
  return (
    <div className="score-ring" style={{ width: size, height: size }} title={label}>
      <svg width={size} height={size}>
        <circle cx={size / 2} cy={size / 2} r={r} stroke="var(--panel-strong)" strokeWidth={stroke} fill="none" />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          stroke={color}
          strokeWidth={stroke}
          fill="none"
          strokeLinecap="round"
          strokeDasharray={c}
          strokeDashoffset={c * (1 - value / 100)}
          style={{ transition: 'stroke-dashoffset .8s ease', filter: `drop-shadow(0 0 6px ${color})` }}
        />
      </svg>
      <span className="value" style={{ fontSize: size * 0.28 }}>
        {score == null ? '–' : Math.round(score)}
      </span>
    </div>
  )
}

export const ProgressBar = ({ value }: { value: number }) => (
  <div className="progress" role="progressbar" aria-valuenow={Math.round(value)} aria-valuemin={0} aria-valuemax={100}>
    <span style={{ width: `${Math.max(0, Math.min(100, value))}%` }} />
  </div>
)

export function LevelSelect({ value, onChange }: { value: Level; onChange: (l: Level) => void }) {
  const { data } = useMeta()
  return (
    <label className="field">
      Trình độ
      <select className="select" value={value} onChange={(e) => onChange(e.target.value as Level)}>
        {(data?.levels ?? []).map((l) => (
          <option key={l.value} value={l.value}>
            {l.label}
          </option>
        ))}
      </select>
    </label>
  )
}

/** Choose where word / sentence audio comes from (saved in this browser). */
export function AudioSourceSelect() {
  const [source, setSource] = useAudioSource()
  const hint = AUDIO_SOURCES.find((s) => s.value === source)?.hint
  return (
    <label className="field audio-source" title={hint}>
      <span className="row" style={{ gap: 6 }}>
        <Icon name="volume" size={14} /> Nguồn âm thanh
      </span>
      <select className="select" value={source} onChange={(e) => setSource(e.target.value as AudioSource)}>
        {AUDIO_SOURCES.map((s) => (
          <option key={s.value} value={s.value}>
            {s.label}
          </option>
        ))}
      </select>
    </label>
  )
}

/** Play English audio (free TTS sources, see AudioSourceSelect). */
export function SpeakButton({ text, label = 'Nghe' }: { text: string; label?: string }) {
  const [state, setState] = useState<'idle' | 'loading' | 'error'>('idle')
  return (
    <button
      type="button"
      className="btn icon sm ghost"
      title={state === 'error' ? 'Không phát được âm thanh' : label}
      aria-label={label}
      onClick={() => {
        setState('loading')
        playText(text)
          .then(() => setState('idle'))
          .catch(() => setState('error'))
      }}
    >
      {state === 'loading' ? <Spinner small /> : <Icon name="volume" />}
    </button>
  )
}

const GENERATING_STEPS = [
  'Gemini đang phân tích chủ đề…',
  'Đang chọn nội dung phù hợp trình độ…',
  'Đang soạn ví dụ và giải thích…',
  'Đang tạo bài tập…',
  'Sắp xong rồi…',
]

export function GeneratingState({ title }: { title: string }) {
  const [step, setStep] = useState(0)
  useEffect(() => {
    const id = window.setInterval(() => setStep((s) => Math.min(s + 1, GENERATING_STEPS.length - 1)), 6000)
    return () => window.clearInterval(id)
  }, [])
  return (
    <div className="card generating">
      <div className="pulse-orb" />
      <h3>{title}</h3>
      <div className="steps">{GENERATING_STEPS[step]}</div>
      <p className="small muted">Thường mất 10–60 giây. Bạn có thể rời trang, bài sẽ tiếp tục được tạo.</p>
    </div>
  )
}
