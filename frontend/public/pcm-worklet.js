// Captures mic audio, downsamples to 16 kHz, converts to PCM16, posts ~100 ms chunks.
class PcmCapture extends AudioWorkletProcessor {
  constructor() {
    super();
    this.ratio = sampleRate / 16000;
    this.buf = new Int16Array(1600);
    this.len = 0;
    this.pos = 0; // fractional read position across process() calls
  }
  process(inputs) {
    const ch = inputs[0] && inputs[0][0];
    if (!ch) return true;
    let sum = 0;
    for (let i = 0; i < ch.length; i++) sum += ch[i] * ch[i];
    // simple decimation with averaging window
    while (this.pos < ch.length) {
      const start = Math.floor(this.pos);
      const end = Math.min(ch.length, Math.floor(this.pos + this.ratio));
      let acc = 0, n = 0;
      for (let j = start; j < Math.max(end, start + 1); j++) { acc += ch[j]; n++; }
      const s = Math.max(-1, Math.min(1, acc / n));
      this.buf[this.len++] = s < 0 ? s * 0x8000 : s * 0x7fff;
      if (this.len === this.buf.length) {
        this.port.postMessage({ pcm: this.buf.buffer.slice(0), rms: Math.sqrt(sum / ch.length) });
        this.len = 0;
      }
      this.pos += this.ratio;
    }
    this.pos -= ch.length;
    return true;
  }
}
registerProcessor("pcm-capture", PcmCapture);
