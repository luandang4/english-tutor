import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'

import { keys, useMeta } from '../../api/hooks'
import type { TurnPronunciation } from '../../api/types'
import { Icon } from '../../components/ui'
import { LiveSession } from '../../lib/audio/live-session'
import { useLevel, usePreference } from '../../lib/preferences'
import { Orb, type OrbMode } from '../../orb/orb'
import { TranslationBubble } from './TranslationBubble'
import { TurnPronunciationView } from './TurnPronunciationView'
import './conversation.css'

const CUSTOM = 'custom' // learner-defined scenario (title + wishes), see services/conversation/live.py
const USER_TALK_RMS = 0.025 // mic level that counts as "the learner is speaking"

const ROLE_TEXT: Record<OrbMode, string> = {
  idle: 'Giáo viên tiếng Anh của bạn',
  connecting: 'Đang kết nối…',
  listening: 'Đang lắng nghe…',
  tutor: 'Đang nói…',
  user: 'Đang nghe bạn nói…',
}
const STATUS_TEXT: Record<OrbMode, string> = {
  idle: 'Sẵn sàng',
  connecting: 'Đang kết nối…',
  listening: 'Đang nghe',
  tutor: 'Emma đang nói',
  user: 'Đang nghe',
}

interface Message {
  id: number
  role: 'user' | 'tutor' | 'translation' | 'error'
  text: string
  source?: string // translation: the English it translates
  pronunciation?: TurnPronunciation
}

export function ConversationPage() {
  const { data: meta } = useMeta()
  const qc = useQueryClient()
  const [level, setLevel] = useLevel()
  const [scenario, setScenario] = usePreference('et.convo.scenario', 'free_talk')
  const [customTitle, setCustomTitle] = usePreference('et.convo.customTitle', '')
  const [customRequest, setCustomRequest] = usePreference('et.convo.customRequest', '')
  const isCustom = scenario === CUSTOM
  const customReady = !isCustom || customTitle.trim().length >= 2
  // Headphones on: the mic stays open while Emma talks (you can interrupt). Off: the mic is paused while she
  // speaks, so speaker sound is not picked up as the learner's voice.
  const [headphones, setHeadphones] = usePreference('et.convo.headphones', false)
  const halfDuplex = !headphones

  const [mode, setMode] = useState<OrbMode>('idle')
  const [running, setRunning] = useState(false)
  const [messages, setMessages] = useState<Message[]>([])
  const [caption, setCaption] = useState<{ role: 'user' | 'tutor'; text: string } | null>(null)
  const [text, setText] = useState('')
  const [chatOpen, setChatOpen] = useState(true)

  const canvasRef = useRef<HTMLCanvasElement>(null)
  const ringRef = useRef<HTMLSpanElement>(null)
  const chatRef = useRef<HTMLDivElement>(null)
  const orbRef = useRef<Orb | null>(null)
  const sessionRef = useRef<LiveSession | null>(null)
  const bubbleOpen = useRef(false) // is the last message still receiving fragments?
  const nextId = useRef(1)
  const typed = useRef(new Set<number>()) // typed messages have no audio to score

  useEffect(() => {
    orbRef.current = new Orb(canvasRef.current!)
    return () => {
      orbRef.current?.destroy()
      sessionRef.current?.stop()
    }
  }, [])

  useEffect(() => {
    orbRef.current?.setMode(mode)
  }, [mode])

  useEffect(() => {
    if (sessionRef.current) sessionRef.current.halfDuplex = halfDuplex
  }, [halfDuplex])

  useEffect(() => {
    chatRef.current?.scrollTo({ top: chatRef.current.scrollHeight })
  }, [messages])

  // Per-frame: decide who is talking and point the orb at that audio.
  useEffect(() => {
    if (!running) return
    let raf = 0
    let lastUserTalk = 0
    const tick = () => {
      const s = sessionRef.current
      if (!s) return
      const now = performance.now()
      const muted = s.halfDuplex && s.tutorSpeaking()
      if (s.micLevel > USER_TALK_RMS && !muted) lastUserTalk = now
      const m: OrbMode = s.tutorSpeaking() ? 'tutor' : now - lastUserTalk < 350 ? 'user' : 'listening'
      setMode((prev) => (prev === m ? prev : m))
      orbRef.current?.setSource(m === 'tutor' ? s.outAnalyser : muted ? null : s.inAnalyser)
      const lvl = muted ? 0 : Math.min(1, s.micLevel * 12)
      if (ringRef.current) {
        ringRef.current.style.opacity = String(lvl * 0.9)
        ringRef.current.style.transform = `scale(${1 + lvl * 0.25})`
      }
      raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [running])

  const push = (role: Message['role'], text: string, source?: string) => {
    bubbleOpen.current = false
    setMessages((ms) => [...ms, { id: nextId.current++, role, text, source }])
  }

  const appendTranscript = (role: 'user' | 'tutor', fragment: string) => {
    setMessages((ms) => {
      const last = ms.at(-1)
      if (bubbleOpen.current && last?.role === role) {
        const updated = { ...last, text: last.text + fragment }
        setCaption({ role, text: updated.text })
        return [...ms.slice(0, -1), updated]
      }
      bubbleOpen.current = true
      setCaption({ role, text: fragment })
      return [...ms, { id: nextId.current++, role, text: fragment }]
    })
  }

  // Azure scores a spoken turn shortly after Emma answered it: attach to the latest spoken turn without a score.
  const attachPronunciation = (result: TurnPronunciation) => {
    setMessages((ms) => {
      const i = ms.findLastIndex((m) => m.role === 'user' && !m.pronunciation && !typed.current.has(m.id))
      if (i < 0) return ms
      return ms.map((m, j) => (j === i ? { ...m, pronunciation: result } : m))
    })
  }

  const start = async () => {
    setMode('connecting')
    setCaption(null)
    const session = new LiveSession({
      onReady: () => {
        setRunning(true)
        setMode('listening')
      },
      onTranscript: appendTranscript,
      onTurnEnd: () => (bubbleOpen.current = false),
      onPronunciation: attachPronunciation,
      onTranslation: (english, vietnamese) => push('translation', vietnamese, english),
      onInterrupted: () => (bubbleOpen.current = false),
      onError: (m) => push('error', m),
      onClosed: () => {
        sessionRef.current = null
        setRunning(false)
        setMode('idle')
        orbRef.current?.setSource(null)
        if (ringRef.current) ringRef.current.style.opacity = '0'
        bubbleOpen.current = false
        void qc.invalidateQueries({ queryKey: keys.progress })
        void qc.invalidateQueries({ queryKey: keys.conversations })
      },
    })
    session.halfDuplex = halfDuplex
    sessionRef.current = session
    try {
      await session.start(
        isCustom
          ? { level, scenario, custom_title: customTitle.trim(), custom_request: customRequest.trim() }
          : { level, scenario },
      )
    } catch (e) {
      push('error', `Không truy cập được micro: ${e instanceof Error ? e.message : e}`)
      session.stop()
    }
  }

  const stop = () => sessionRef.current?.stop()

  const send = (e: { preventDefault(): void }) => {
    e.preventDefault()
    const t = text.trim()
    if (!t || !sessionRef.current) return
    typed.current.add(nextId.current)
    push('user', t)
    setCaption({ role: 'user', text: t })
    sessionRef.current.sendText(t)
    setText('')
  }

  const captionText = caption && (caption.text.length > 200 ? '…' + caption.text.slice(-200) : caption.text).trim()

  return (
    <div className={`convo ${running ? 'running' : ''}`}>
      <div className="convo-head">
        <div>
          <h1>Hội thoại với Emma</h1>
        </div>
        <div className="row">
          <Link to="/conversation/history" className="btn sm ghost">
            <Icon name="history" size={16} /> Lịch sử
          </Link>
          <div className="live-status" data-state={mode}>
            <span className="dot" />
            {STATUS_TEXT[mode]}
          </div>
        </div>
      </div>

      <section className="stage" data-mode={mode}>
        <div className="orb-wrap">
          <canvas ref={canvasRef} aria-hidden="true" />
        </div>
        <div className="persona">
          <div className="name gradient-text">Emma</div>
          <div className="role">{ROLE_TEXT[mode]}</div>
        </div>

        {running || mode === 'connecting' ? (
          <div className={`caption ${caption?.role ?? ''}`} aria-live="polite">
            {captionText}
          </div>
        ) : (
          <div className="setup">
            <label className="field">
              Trình độ
              <select className="select" value={level} onChange={(e) => setLevel(e.target.value as typeof level)}>
                {meta?.levels.map((l) => (
                  <option key={l.value} value={l.value}>
                    {l.label}
                  </option>
                ))}
              </select>
            </label>
            <label className="field">
              Tình huống
              <select className="select" value={scenario} onChange={(e) => setScenario(e.target.value)}>
                {meta?.scenarios.map((s) => (
                  <option key={s.value} value={s.value}>
                    {s.label}
                  </option>
                ))}
                <option value={CUSTOM}>✨ Tình huống của bạn…</option>
              </select>
            </label>
            {isCustom && (
              <div className="custom-scenario">
                <label className="field">
                  Chủ đề / tình huống
                  <input
                    className="input"
                    value={customTitle}
                    onChange={(e) => setCustomTitle(e.target.value)}
                    maxLength={120}
                    placeholder="VD: Phỏng vấn xin việc vị trí kế toán"
                  />
                </label>
                <label className="field">
                  Yêu cầu thêm (tuỳ chọn)
                  <textarea
                    className="textarea"
                    rows={2}
                    value={customRequest}
                    onChange={(e) => setCustomRequest(e.target.value)}
                    maxLength={1000}
                    placeholder="VD: Emma đóng vai nhà tuyển dụng khó tính, hỏi về kinh nghiệm làm việc với Excel"
                  />
                </label>
              </div>
            )}
            <label className="toggle">
              <input type="checkbox" checked={headphones} onChange={(e) => setHeadphones(e.target.checked)} />
              <span className="switch" aria-hidden="true" />
              <span>
                Đeo tai nghe{' '}
                <small>Bật nếu đang đeo tai nghe để có thể ngắt lời Emma. Tắt thì mic tự tạm ngắt khi Emma nói.</small>
              </span>
            </label>
          </div>
        )}
      </section>

      <aside className={`transcript ${messages.length ? '' : 'empty-chat'}`}>
        <div className="transcript-head">
          <span>Hội thoại</span>
          <button type="button" className="btn sm ghost" onClick={() => setChatOpen((o) => !o)} aria-expanded={chatOpen}>
            {chatOpen ? 'Ẩn' : 'Hiện'}
          </button>
        </div>
        {chatOpen && (
          <div className="chat" ref={chatRef} aria-live="polite">
            {messages.length === 0 && (
              <div className="empty">Chọn trình độ và tình huống, rồi bấm nút micro. Emma sẽ chào bạn trước.</div>
            )}
            {messages.map((m) =>
              m.role === 'translation' ? (
                <TranslationBubble key={m.id} vietnamese={m.text} english={m.source} />
              ) : (
              <div key={m.id} className={`msg ${m.role}`}>
                {m.role !== 'error' && <span className="who">{m.role === 'tutor' ? 'Emma' : 'Bạn'}</span>}
                {m.text}
                {m.pronunciation && <TurnPronunciationView result={m.pronunciation} />}
              </div>
              ),
            )}
          </div>
        )}
      </aside>

      <footer className="controls">
        <button
          className={`mic ${running ? 'stop' : ''}`}
          onClick={running ? stop : start}
          disabled={mode === 'connecting' || (!running && !customReady)}
          aria-label={running ? 'Kết thúc buổi học' : 'Bắt đầu buổi học'}
        >
          <span className="mic-ring" ref={ringRef} />
          <Icon name={running ? 'stop' : 'mic'} size={28} />
        </button>
        <span className="mic-hint">{running ? 'Bấm để kết thúc' : 'Bấm để bắt đầu'}</span>
        <form className="text-form" onSubmit={send}>
          <input
            placeholder="Hoặc gõ tin nhắn…"
            value={text}
            onChange={(e) => setText(e.target.value)}
            disabled={!running}
            autoComplete="off"
          />
          <button type="submit" aria-label="Gửi" disabled={!running || !text.trim()}>
            <Icon name="send" size={18} />
          </button>
        </form>
      </footer>
    </div>
  )
}
