import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'

import { keys, useMeta } from '../../api/hooks'
import type { ConversationTurn } from '../../api/types'
import { Icon } from '../../components/ui'
import { LiveSession, type LiveAction, type LiveSettings } from '../../lib/audio/live-session'
import { useLevel } from '../../lib/preferences'
import { useWakeLock } from '../../lib/wakeLock'
import { Orb, type OrbMode } from '../../orb/orb'
import { EndCard, type EndReason } from './EndCard'
import { useDeckActions } from './useDeckActions'
import { ages, useLiveTranscript, type Line } from './liveTranscript'
import { CUSTOM, useConvoPreferences } from './preferences'
import { QuickHelp } from './QuickHelp'
import { PhraseSheet } from './ScenarioBrief'
import { SessionBar } from './SessionBar'
import { SetupPanel } from './SetupPanel'
import { TurnView, type TurnActions } from './TurnView'
import { useSilenceHint } from './useSilenceHint'
import { useStickToBottom } from './useStickToBottom'
import './conversation.css'

const SILENT_END_FALLBACK_MS = 20000 // stop even if Emma's goodbye never arrives
const USER_TALK_RMS = 0.025 // mic level that counts as "the learner is speaking"

export interface SessionEndInfo {
  sessionId: number | null
  reason: EndReason
  turns: ConversationTurn[]
}

export interface ConversationPageProps extends TurnActions {
  /** Called once when a session that had started ends (learner stopped, time limit, or error).
   * Hook point for the end-of-session summary screen. */
  onEnded?: (info: SessionEndInfo) => void
}

/** One transcript line, faded by age: the latest exchange is large, older lines get smaller and dimmer. */
function LineView(props: { line: Line; age: number; done: boolean } & TurnActions) {
  const { line, age, done, ...actions } = props
  if (line.role === 'notice') return <div className={`notice ${line.tone}`}>{line.text}</div>
  const fade = age === 0 ? 'current' : age <= 2 ? 'recent' : 'old'
  return (
    <div className={`line ${fade}`}>
      <TurnView turn={line} done={done} {...actions} />
    </div>
  )
}

export function ConversationPage(props: ConversationPageProps = {}) {
  const deck = useDeckActions()
  const { onEnded, onSaveFeedback = deck.onSaveFeedback, onAddWord = deck.onAddWord } = props
  const { data: meta } = useMeta()
  const qc = useQueryClient()
  const [level, setLevel] = useLevel()
  const prefs = useConvoPreferences()
  const isCustom = prefs.scenario === CUSTOM
  const customReady = !isCustom || prefs.customTitle.trim().length >= 2
  const preset = isCustom ? undefined : meta?.scenarios.find((s) => s.value === prefs.scenario)
  const halfDuplex = !prefs.headphones

  const [mode, setMode] = useState<OrbMode>('idle')
  const [running, setRunning] = useState(false)
  const [ended, setEnded] = useState<{ reason: EndReason; sessionId: number | null; saved: boolean } | null>(null)
  const [setupError, setSetupError] = useState<string | null>(null)
  const [endsAt, setEndsAt] = useState<number | null>(null)
  const [showPhrases, setShowPhrases] = useState(false)
  const [text, setText] = useState('')
  const { lines, openId, actions: transcript } = useLiveTranscript()

  const canvasRef = useRef<HTMLCanvasElement>(null)
  const ringRef = useRef<HTMLSpanElement>(null)
  const talkRef = useRef<HTMLDivElement>(null)
  const orbRef = useRef<Orb | null>(null)
  const sessionRef = useRef<LiveSession | null>(null)
  const sessionId = useRef<number | null>(null)
  const ready = useRef(false) // the server accepted the session (it may be saved)
  const endReason = useRef<EndReason>('stopped')
  const pendingHintArm = useRef(false) // Emma finished generating; start the silence timer once her audio ends
  const silentEnd = useRef<number | null>(null) // fallback timer while Emma says goodbye to a silent learner
  const unmounted = useRef(false)

  const live = running || mode === 'connecting'
  const view = live ? 'live' : ended ? 'ended' : 'setup'
  const silence = useSilenceHint((nudge) => {
    if (nudge === 'silent_end') {
      transcript.notice('Bạn im lặng khá lâu nên Emma sẽ kết thúc buổi nói chuyện.', 'info')
      silentEnd.current = window.setTimeout(() => sessionRef.current?.stop(), SILENT_END_FALLBACK_MS)
    }
    sessionRef.current?.sendAction(nudge)
  })
  const cancelSilentEnd = () => {
    if (silentEnd.current !== null) window.clearTimeout(silentEnd.current)
    silentEnd.current = null
  }
  const { pinned, scrollToBottom } = useStickToBottom(talkRef, view !== 'setup')
  useWakeLock(live)

  useEffect(() => {
    unmounted.current = false
    orbRef.current = new Orb(canvasRef.current!)
    return () => {
      unmounted.current = true
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

  // Full-screen session on phones: the bottom tab bar is hidden while talking.
  useEffect(() => {
    document.body.classList.toggle('convo-live', live)
    return () => document.body.classList.remove('convo-live')
  }, [live])

  // Per-frame: decide who is talking, point the orb at that audio, and track learner silence.
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
      if (m === 'user') silence.learnerSound()
      if (pendingHintArm.current && !s.tutorSpeaking()) {
        pendingHintArm.current = false
        if (silentEnd.current !== null) s.stop() // Emma's goodbye has finished playing
        else silence.arm(transcript.lastTutorText())
      }
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
  }, [running, silence, transcript])

  const finish = () => {
    sessionRef.current = null
    pendingHintArm.current = false
    cancelSilentEnd()
    silence.cancel()
    if (unmounted.current) return
    setRunning(false)
    setMode('idle')
    setEndsAt(null)
    setShowPhrases(false)
    orbRef.current?.setSource(null)
    if (ringRef.current) ringRef.current.style.opacity = '0'
    transcript.closeLine()
    void qc.invalidateQueries({ queryKey: keys.progress })
    void qc.invalidateQueries({ queryKey: keys.conversations })
    if (!ready.current) return // never started: stay on the setup screen (with the error, if any)
    const info: SessionEndInfo = { sessionId: sessionId.current, reason: endReason.current, turns: transcript.turns() }
    setEnded({ reason: info.reason, sessionId: info.sessionId, saved: transcript.hasLearnerLine() })
    onEnded?.(info)
  }

  const settings = (): LiveSettings => ({
    level,
    scenario: prefs.scenario,
    enhancement: prefs.enhancement,
    ...(isCustom ? { custom_title: prefs.customTitle.trim(), custom_request: prefs.customRequest.trim() } : {}),
  })

  const start = async () => {
    transcript.clear()
    setEnded(null)
    setSetupError(null)
    setEndsAt(null)
    ready.current = false
    sessionId.current = null
    endReason.current = 'stopped'
    setMode('connecting')
    const session = new LiveSession({
      onReady: (id) => {
        ready.current = true
        sessionId.current = id
        setRunning(true)
        setMode('listening')
      },
      onLimits: (seconds) => setEndsAt(Date.now() + seconds * 1000),
      onWrapUp: () => transcript.notice('Còn khoảng 2 phút. Emma sẽ tóm tắt 2 điều cần nhớ rồi chào bạn.', 'info'),
      onSessionEnd: (reason) => {
        endReason.current = reason === 'time_limit' ? 'time_limit' : 'stopped'
      },
      onTranscript: (role, fragment) => {
        if (role === 'user') {
          silence.learnerSpoke()
          cancelSilentEnd()
        } else silence.cancel()
        transcript.fragment(role, fragment)
      },
      onTurnEnd: () => {
        transcript.closeLine()
        pendingHintArm.current = true
      },
      onInterrupted: () => {
        transcript.closeLine()
        pendingHintArm.current = false
      },
      onPronunciation: transcript.pronunciation,
      onTranslation: transcript.translation,
      onFeedback: transcript.feedback,
      onHint: (card) => {
        silence.cancel()
        transcript.hint(card)
      },
      onError: (message) => {
        if (!ready.current) return setSetupError(message)
        endReason.current = 'error'
        transcript.notice(message, 'error')
      },
      onClosed: finish,
    })
    session.halfDuplex = halfDuplex
    sessionRef.current = session
    try {
      await session.start(settings())
    } catch (e) {
      setSetupError(`Không truy cập được micro: ${e instanceof Error ? e.message : e}`)
      session.stop()
    }
  }

  const stop = () => sessionRef.current?.stop()

  const send = (e: { preventDefault(): void }) => {
    e.preventDefault()
    const t = text.trim()
    if (!t || !sessionRef.current) return
    silence.learnerSpoke()
    transcript.typed(t)
    sessionRef.current.sendText(t)
    setText('')
  }

  const action = (a: LiveAction) => {
    silence.helpRequested()
    sessionRef.current?.sendAction(a)
  }

  const lineAges = ages(lines)

  return (
    <div className={`convo view-${view} font-${prefs.fontSize}`} data-mode={mode}>
      <div className="orb-wrap" aria-hidden="true">
        <canvas ref={canvasRef} />
      </div>

      {view === 'setup' ? (
        <>
          <header className="convo-head">
            <h1>Hội thoại với Emma</h1>
            <Link to="/conversation/history" className="btn sm ghost">
              <Icon name="history" size={16} /> Lịch sử
            </Link>
          </header>
          <div className="persona">
            <div className="name gradient-text">Emma</div>
            <div className="role">Giáo viên tiếng Anh của bạn</div>
          </div>
          {setupError && <div className="alert error setup-error">{setupError}</div>}
          <SetupPanel meta={meta} level={level} setLevel={setLevel} prefs={prefs} />
          <footer className="controls start">
            <button className="mic" onClick={start} disabled={!customReady} aria-label="Bắt đầu buổi học">
              <span className="mic-ring" ref={ringRef} />
              <Icon name="mic" size={28} />
            </button>
            <span className="mic-hint">
              {customReady ? 'Bấm để bắt đầu. Emma sẽ chào bạn trước.' : 'Nhập chủ đề để bắt đầu.'}
            </span>
          </footer>
        </>
      ) : (
        <>
          <SessionBar
            mode={mode}
            endsAt={endsAt}
            fontSize={prefs.fontSize}
            onFontSize={prefs.setFontSize}
            onPhrases={preset ? () => setShowPhrases((s) => !s) : undefined}
          />
          <div className="talk-wrap">
            <div className="talk" ref={talkRef} aria-live="polite">
              <div className="talk-col">
                {lines.length === 0 && !ended && (
                  <div className="talk-empty">
                    {mode === 'connecting' ? 'Đang kết nối với Emma…' : 'Emma sẽ chào bạn trước. Cứ nói tự nhiên nhé!'}
                  </div>
                )}
                {lines.map((l, i) => (
                  <LineView
                    key={l.id}
                    line={l}
                    age={lineAges[i]}
                    done={l.id !== openId}
                    onSaveFeedback={onSaveFeedback}
                    onAddWord={onAddWord}
                  />
                ))}
                {ended && (
                  <EndCard
                    reason={ended.reason}
                    sessionId={ended.sessionId}
                    saved={ended.saved}
                    onNew={() => {
                      setEnded(null)
                      transcript.clear()
                    }}
                  />
                )}
              </div>
            </div>
            {!pinned && (
              <button type="button" className="to-latest" onClick={scrollToBottom}>
                <Icon name="arrowDown" size={16} /> Về câu mới nhất
              </button>
            )}
          </div>

          {view === 'live' && (
            <footer className="controls">
              <div className="controls-inner">
                <QuickHelp onAction={action} disabled={!running} />
                <button
                  className="mic stop"
                  onClick={stop}
                  disabled={!running}
                  aria-label="Kết thúc buổi học"
                  title="Kết thúc buổi học"
                >
                  <span className="mic-ring" ref={ringRef} />
                  <Icon name="stop" size={26} />
                </button>
                <form className="text-form" onSubmit={send}>
                  <input
                    placeholder="Hoặc gõ tin nhắn…"
                    value={text}
                    onChange={(e) => setText(e.target.value)}
                    disabled={!running}
                    autoComplete="off"
                    enterKeyHint="send"
                  />
                  <button type="submit" aria-label="Gửi" disabled={!running || !text.trim()}>
                    <Icon name="send" size={18} />
                  </button>
                </form>
              </div>
            </footer>
          )}

          {showPhrases && preset && <PhraseSheet scenario={preset} level={level} onClose={() => setShowPhrases(false)} />}
        </>
      )}
    </div>
  )
}
