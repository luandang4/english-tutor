// Audio-reactive orb ("AI presence") drawn on a 2D canvas.
// Modes: idle | connecting | listening | tutor | user. Feed it an AnalyserNode to react to sound.

export type OrbMode = 'idle' | 'connecting' | 'listening' | 'tutor' | 'user'
type RGB = [number, number, number]

const PALETTES: Record<OrbMode, [RGB, RGB, RGB]> = {
  idle: [[255, 244, 205], [255, 213, 74], [255, 160, 110]],
  connecting: [[255, 244, 205], [255, 222, 120], [140, 220, 255]],
  listening: [[255, 246, 215], [255, 205, 90], [110, 220, 255]],
  tutor: [[255, 246, 200], [255, 196, 50], [255, 140, 90]],
  user: [[214, 252, 255], [94, 240, 255], [124, 140, 255]],
}
const N = 96 // points around the blob
const BARS = 72 // frequency bars around the ring
const TAU = Math.PI * 2

export class Orb {
  private readonly g: CanvasRenderingContext2D
  private mode: OrbMode = 'idle'
  private analyser: AnalyserNode | null = null
  private data: Uint8Array<ArrayBuffer> | null = null
  private readonly amp = new Float32Array(N)
  private level = 0
  private t = 0
  private last = performance.now()
  private lastRipple = 0
  private ripples: { r: number; a: number }[] = []
  private spin = 0
  private readonly colors: [RGB, RGB, RGB] = PALETTES.idle.map((c) => [...c]) as [RGB, RGB, RGB]
  private readonly dark = matchMedia('(prefers-color-scheme: dark)')
  private readonly reduced = matchMedia('(prefers-reduced-motion: reduce)').matches
  private readonly observer: ResizeObserver
  private raf = 0
  private w = 1
  private h = 1
  private dpr = 1

  private readonly canvas: HTMLCanvasElement

  constructor(canvas: HTMLCanvasElement) {
    this.canvas = canvas
    this.g = canvas.getContext('2d')!
    this.observer = new ResizeObserver(() => this.resize())
    this.observer.observe(canvas)
    this.resize()
    this.raf = requestAnimationFrame((now) => this.frame(now))
  }

  destroy(): void {
    cancelAnimationFrame(this.raf)
    this.observer.disconnect()
  }

  setMode(mode: OrbMode): void {
    this.mode = mode
  }

  setSource(analyser: AnalyserNode | null): void {
    if (analyser === this.analyser) return
    this.analyser = analyser
    this.data = analyser ? new Uint8Array(analyser.frequencyBinCount) : null
  }

  private resize(): void {
    const dpr = Math.min(window.devicePixelRatio || 1, 2)
    const r = this.canvas.getBoundingClientRect()
    this.w = Math.max(1, Math.round(r.width * dpr))
    this.h = Math.max(1, Math.round(r.height * dpr))
    this.canvas.width = this.w
    this.canvas.height = this.h
    this.dpr = dpr
  }

  // Read the analyser and update per-point amplitudes + overall level.
  private sample(): void {
    let target = 0
    if (this.analyser && this.data) {
      this.analyser.getByteFrequencyData(this.data)
      const binHz = this.analyser.context.sampleRate / this.analyser.fftSize
      const lo = Math.max(1, Math.floor(90 / binHz))
      const hi = Math.min(this.data.length - 1, Math.ceil(5000 / binHz))
      let sum = 0
      for (let b = lo; b <= hi; b++) sum += this.data[b]
      target = Math.min(1, (sum / (hi - lo + 1) / 255) * 2.4)
      for (let i = 0; i < N; i++) {
        const f = i / N
        const m = f < 0.5 ? f * 2 : (1 - f) * 2 // mirror so the shape is symmetric
        const v = this.data[lo + Math.floor(m * (hi - lo))] / 255
        this.amp[i] += (v * v * 1.6 - this.amp[i]) * 0.3
      }
    } else {
      for (let i = 0; i < N; i++) this.amp[i] *= 0.9
    }
    const k = target > this.level ? 0.35 : 0.07 // fast attack, slow release
    this.level += (target - this.level) * k
  }

  private ampAt(theta: number): number {
    const x = ((((theta % TAU) + TAU) % TAU) / TAU) * N
    const i = Math.floor(x)
    const f = x - i
    return this.amp[i % N] * (1 - f) + this.amp[(i + 1) % N] * f
  }

  private rgba(c: RGB, a: number): string {
    return `rgba(${c[0] | 0},${c[1] | 0},${c[2] | 0},${a})`
  }

  private frame(now: number): void {
    const dt = Math.min(0.05, (now - this.last) / 1000)
    this.last = now
    this.t += this.reduced ? dt * 0.3 : dt
    this.sample()
    const target = PALETTES[this.mode]
    const ck = Math.min(1, dt * 4)
    for (let c = 0; c < 3; c++) for (let j = 0; j < 3; j++) this.colors[c][j] += (target[c][j] - this.colors[c][j]) * ck
    this.draw(dt)
    this.raf = requestAnimationFrame((n) => this.frame(n))
  }

  private draw(dt: number): void {
    const { g, w, h, t, level, colors } = this
    const [core, mid, edge] = colors
    const dark = this.dark.matches
    const cx = w / 2
    const cy = h / 2
    const base = Math.min(w, h) * 0.22
    const maxR = Math.min(w, h) * 0.5
    const active = this.mode === 'tutor' || this.mode === 'user'
    const breathe = 1 + Math.sin(t * 1.4) * (active ? 0.01 : 0.025)
    const R = base * breathe * (1 + level * 0.16)

    g.clearRect(0, 0, w, h)
    g.globalCompositeOperation = dark ? 'lighter' : 'source-over'

    // 1. halo
    const halo = g.createRadialGradient(cx, cy, R * 0.6, cx, cy, maxR)
    halo.addColorStop(0, this.rgba(mid, (dark ? 0.32 : 0.22) + level * 0.3))
    halo.addColorStop(0.5, this.rgba(edge, (dark ? 0.1 : 0.08) + level * 0.12))
    halo.addColorStop(1, this.rgba(edge, 0))
    g.fillStyle = halo
    g.beginPath()
    g.arc(cx, cy, maxR, 0, TAU)
    g.fill()

    // 2. ripples emitted while someone is speaking
    if (active && level > 0.12 && t - this.lastRipple > 0.55 - level * 0.3) {
      this.ripples.push({ r: R, a: 0.35 + level * 0.4 })
      this.lastRipple = t
    }
    g.lineWidth = 2 * this.dpr
    this.ripples = this.ripples.filter((rp) => {
      rp.r += dt * base * 0.9
      rp.a -= dt * 0.38
      if (rp.a <= 0 || rp.r > maxR) return false
      rp.a = Math.min(rp.a, (maxR - rp.r) / (base * 0.5)) // fade out before the canvas edge
      g.strokeStyle = this.rgba(edge, rp.a)
      g.beginPath()
      g.arc(cx, cy, rp.r, 0, TAU)
      g.stroke()
      return true
    })

    // 3. frequency bars around the orb
    const inner = R * 1.16
    g.lineCap = 'round'
    g.lineWidth = Math.max(2, base * 0.022)
    for (let b = 0; b < BARS; b++) {
      const a = (b / BARS) * TAU - Math.PI / 2
      const v = this.ampAt(a + Math.PI / 2)
      const len = base * (0.025 + v * 0.42)
      g.strokeStyle = this.rgba(b % 2 ? mid : edge, 0.22 + Math.min(0.7, v * 1.2))
      g.beginPath()
      g.moveTo(cx + Math.cos(a) * inner, cy + Math.sin(a) * inner)
      g.lineTo(cx + Math.cos(a) * (inner + len), cy + Math.sin(a) * (inner + len))
      g.stroke()
    }

    // 4. liquid blob layers
    for (let k = 0; k < 3; k++) {
      const rot = t * (0.25 + k * 0.12) * (k % 2 ? -1 : 1)
      const pts: [number, number][] = []
      for (let i = 0; i < N; i++) {
        const th = (i / N) * TAU
        const wob =
          0.045 * Math.sin(3 * th + t * 1.3 + k * 2) +
          0.03 * Math.sin(5 * th - t * 0.9 + k) +
          0.02 * Math.sin(7 * th + t * 1.7 - k)
        const r = R * (0.92 - k * 0.06) * (1 + wob * (0.6 + level) + this.ampAt(th + rot) * 0.26 * (1 - k * 0.25))
        pts.push([cx + Math.cos(th + rot) * r, cy + Math.sin(th + rot) * r])
      }
      const grad = g.createRadialGradient(cx - R * 0.25, cy - R * 0.3, R * 0.05, cx, cy, R * 1.25)
      grad.addColorStop(0, this.rgba(core, dark ? 0.28 : 0.7))
      grad.addColorStop(0.4, this.rgba(k === 1 ? edge : mid, dark ? 0.38 : 0.55))
      grad.addColorStop(1, this.rgba(k === 2 ? mid : edge, dark ? 0.16 : 0.3))
      g.fillStyle = grad
      g.beginPath()
      const m0 = mean(pts[N - 1], pts[0])
      g.moveTo(m0[0], m0[1])
      for (let i = 0; i < N; i++) {
        const p = pts[i]
        const q = mean(p, pts[(i + 1) % N])
        g.quadraticCurveTo(p[0], p[1], q[0], q[1])
      }
      g.closePath()
      g.fill()
    }

    // 5. glossy highlight
    g.globalCompositeOperation = 'source-over'
    const hl = g.createRadialGradient(cx - R * 0.32, cy - R * 0.38, 0, cx - R * 0.32, cy - R * 0.38, R * 0.55)
    hl.addColorStop(0, `rgba(255,255,255,${dark ? 0.28 : 0.45})`)
    hl.addColorStop(1, 'rgba(255,255,255,0)')
    g.fillStyle = hl
    g.beginPath()
    g.arc(cx, cy, R * 0.95, 0, TAU)
    g.fill()

    // 6. spinner while connecting
    if (this.mode === 'connecting') {
      this.spin += dt * 3.2
      g.lineWidth = 3 * this.dpr
      g.strokeStyle = this.rgba(edge, 0.9)
      g.beginPath()
      g.arc(cx, cy, R * 1.42, this.spin, this.spin + 1.3)
      g.stroke()
      g.strokeStyle = this.rgba(mid, 0.6)
      g.beginPath()
      g.arc(cx, cy, R * 1.42, this.spin + Math.PI, this.spin + Math.PI + 0.7)
      g.stroke()
    }
  }
}

function mean(a: [number, number], b: [number, number]): [number, number] {
  return [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2]
}
