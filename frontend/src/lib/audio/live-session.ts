// Voice conversation client: mic (AudioWorklet, PCM16 16 kHz) -> /ws/conversation -> Gemini Live
// -> PCM16 24 kHz -> speakers. Both directions also feed AnalyserNodes for the orb visualizer.

import type { TurnPronunciation } from '../../api/types'

const OUT_RATE = 24_000

export interface LiveSettings {
  level: string
  scenario: string
  custom_title?: string
  custom_request?: string
}

export interface LiveCallbacks {
  onReady?: (sessionId: number) => void
  onTranscript?: (role: 'user' | 'tutor', text: string) => void
  onTurnEnd?: () => void
  onPronunciation?: (result: TurnPronunciation) => void
  onInterrupted?: () => void
  onError?: (message: string) => void
  onClosed?: () => void
}

function makeAnalyser(ctx: AudioContext): AnalyserNode {
  const a = ctx.createAnalyser()
  a.fftSize = 1024
  a.smoothingTimeConstant = 0.78
  return a
}

export class LiveSession {
  halfDuplex = true
  micLevel = 0
  outAnalyser: AnalyserNode | null = null
  inAnalyser: AnalyserNode | null = null

  private ws: WebSocket | null = null
  private ctx: AudioContext | null = null
  private stream: MediaStream | null = null
  private worklet: AudioWorkletNode | null = null
  private outGain: GainNode | null = null
  private playTime = 0
  private readonly sources = new Set<AudioBufferSourceNode>()
  private running = false
  private closed = false

  private readonly cb: LiveCallbacks

  constructor(cb: LiveCallbacks) {
    this.cb = cb
  }

  async start(settings: LiveSettings): Promise<void> {
    const ctx = new AudioContext()
    this.ctx = ctx
    await ctx.audioWorklet.addModule('/pcm-worklet.js')
    this.stream = await navigator.mediaDevices.getUserMedia({
      audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true, channelCount: 1 },
    })
    if (this.closed) return this.stop()

    this.outGain = ctx.createGain()
    this.outAnalyser = makeAnalyser(ctx)
    this.outGain.connect(this.outAnalyser).connect(ctx.destination)

    const proto = location.protocol === 'https:' ? 'wss' : 'ws'
    const ws = new WebSocket(`${proto}://${location.host}/ws/conversation`)
    ws.binaryType = 'arraybuffer'
    this.ws = ws
    ws.onopen = () => ws.send(JSON.stringify({ type: 'start', ...settings }))
    ws.onmessage = (ev) => this.onMessage(ev)
    ws.onclose = () => {
      if (!this.closed) {
        if (!this.running) this.cb.onError?.('Không kết nối được máy chủ hội thoại.')
        this.stop()
      }
    }
  }

  /** True while tutor audio is still playing (plus a short tail to swallow echo). */
  tutorSpeaking(): boolean {
    return !!this.ctx && this.ctx.currentTime < this.playTime + 0.25
  }

  sendText(text: string): void {
    if (this.ws?.readyState !== WebSocket.OPEN) return
    this.stopPlayback()
    this.ws.send(JSON.stringify({ type: 'text', text }))
  }

  stop(): void {
    if (this.closed) return
    this.closed = true
    this.running = false
    try {
      if (this.ws?.readyState === WebSocket.OPEN) this.ws.send(JSON.stringify({ type: 'stop' }))
    } catch {
      /* socket already gone */
    }
    this.ws?.close()
    this.stopPlayback()
    this.worklet?.disconnect()
    this.stream?.getTracks().forEach((t) => t.stop())
    void this.ctx?.close()
    this.ws = this.ctx = this.stream = this.worklet = this.outGain = null
    this.outAnalyser = this.inAnalyser = null
    this.micLevel = 0
    this.cb.onClosed?.()
  }

  private onMessage(ev: MessageEvent): void {
    if (ev.data instanceof ArrayBuffer) {
      this.play(ev.data)
      return
    }
    const msg = JSON.parse(ev.data as string)
    switch (msg.type) {
      case 'ready':
        this.startMic()
        this.cb.onReady?.(msg.session_id)
        break
      case 'transcript':
        this.cb.onTranscript?.(msg.role, msg.text)
        break
      case 'interrupted':
        this.stopPlayback()
        this.cb.onInterrupted?.()
        break
      case 'pronunciation':
        this.cb.onPronunciation?.(msg as TurnPronunciation)
        break
      case 'turn_complete':
        this.cb.onTurnEnd?.()
        break
      case 'error':
        this.cb.onError?.(msg.message)
        break
    }
  }

  private startMic(): void {
    const ctx = this.ctx
    if (!ctx || !this.stream) return
    this.running = true
    const source = ctx.createMediaStreamSource(this.stream)
    // visuals only: mic -> analyser -> muted gain (keeps the node pulled by the graph)
    this.inAnalyser = makeAnalyser(ctx)
    const mute = ctx.createGain()
    mute.gain.value = 0
    source.connect(this.inAnalyser).connect(mute).connect(ctx.destination)

    this.worklet = new AudioWorkletNode(ctx, 'pcm-capture')
    this.worklet.port.onmessage = ({ data }: MessageEvent<{ pcm: ArrayBuffer; rms: number }>) => {
      this.micLevel = data.rms
      if (this.ws?.readyState !== WebSocket.OPEN) return
      if (this.halfDuplex && this.tutorSpeaking()) return // avoid echo when using speakers
      this.ws.send(data.pcm)
    }
    source.connect(this.worklet)
  }

  private play(buffer: ArrayBuffer): void {
    const ctx = this.ctx
    if (!ctx || !this.outGain) return
    const pcm = new Int16Array(buffer)
    if (!pcm.length) return
    const buf = ctx.createBuffer(1, pcm.length, OUT_RATE)
    const ch = buf.getChannelData(0)
    for (let i = 0; i < pcm.length; i++) ch[i] = pcm[i] / 0x8000
    const src = ctx.createBufferSource()
    src.buffer = buf
    src.connect(this.outGain)
    this.playTime = Math.max(this.playTime, ctx.currentTime + 0.05)
    src.start(this.playTime)
    this.playTime += buf.duration
    this.sources.add(src)
    src.onended = () => this.sources.delete(src)
  }

  private stopPlayback(): void {
    for (const s of this.sources) {
      try {
        s.stop()
      } catch {
        /* already stopped */
      }
    }
    this.sources.clear()
    this.playTime = 0
  }
}
