import { useEffect, useState } from 'react'

const WARN_SECONDS = 120

const pad = (n: number) => String(n).padStart(2, '0')

/** Time left in the session (the server's limit), e.g. "12:34 còn lại". */
export function Countdown({ endsAt }: { endsAt: number }) {
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    const id = window.setInterval(() => setNow(Date.now()), 1000)
    return () => window.clearInterval(id)
  }, [])
  const left = Math.max(0, Math.round((endsAt - now) / 1000))
  return (
    <span className={`countdown ${left <= WARN_SECONDS ? 'warn' : ''}`} title="Thời gian còn lại của buổi học">
      {Math.floor(left / 60)}:{pad(left % 60)}
      <span className="countdown-label"> còn lại</span>
    </span>
  )
}
