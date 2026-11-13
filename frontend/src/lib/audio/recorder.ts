// Short mic recordings as raw PCM16 mono 16 kHz (what Azure Pronunciation Assessment expects).

export class PcmRecorder {
  private ctx: AudioContext | null = null
  private stream: MediaStream | null = null
  private node: AudioWorkletNode | null = null
  private chunks: ArrayBuffer[] = []
  private timer = 0

  private readonly onLevel: (rms: number) => void
  private readonly maxSeconds: number
  private readonly onAutoStop: () => void

  constructor(onLevel: (rms: number) => void = () => {}, maxSeconds = 15, onAutoStop: () => void = () => {}) {
    this.onLevel = onLevel
    this.maxSeconds = maxSeconds
    this.onAutoStop = onAutoStop
  }

  async start(): Promise<void> {
    this.chunks = []
    this.stream = await navigator.mediaDevices.getUserMedia({
      audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true, channelCount: 1 },
    })
    this.ctx = new AudioContext()
    await this.ctx.audioWorklet.addModule('/pcm-worklet.js')
    const source = this.ctx.createMediaStreamSource(this.stream)
    this.node = new AudioWorkletNode(this.ctx, 'pcm-capture')
    this.node.port.onmessage = ({ data }: MessageEvent<{ pcm: ArrayBuffer; rms: number }>) => {
      this.chunks.push(data.pcm)
      this.onLevel(data.rms)
    }
    source.connect(this.node)
    this.timer = window.setTimeout(() => this.onAutoStop(), this.maxSeconds * 1000)
  }

  /** Stop and return the whole recording as one PCM16 buffer. */
  stop(): ArrayBuffer {
    window.clearTimeout(this.timer)
    this.node?.disconnect()
    this.stream?.getTracks().forEach((t) => t.stop())
    void this.ctx?.close()
    this.ctx = this.stream = this.node = null
    const total = this.chunks.reduce((n, c) => n + c.byteLength, 0)
    const out = new Uint8Array(total)
    let offset = 0
    for (const c of this.chunks) {
      out.set(new Uint8Array(c), offset)
      offset += c.byteLength
    }
    this.chunks = []
    return out.buffer
  }
}
