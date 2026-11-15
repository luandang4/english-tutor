import { useState } from 'react'

import { useSaveSrsSettings, useSrsSettings } from '../../api/hooks'
import type { SrsSettings } from '../../api/types'
import { ErrorBox, Spinner } from '../../components/ui'

/** Account page: target retention (FSRS desired_retention) and the daily cap on new words. */
export function SrsSettingsCard() {
  const { data } = useSrsSettings()
  const save = useSaveSrsSettings()
  if (!data) return null
  return <SrsSettingsForm key={`${data.desired_retention}-${data.new_cards_per_day}`} initial={data} save={save} />
}

function SrsSettingsForm({ initial, save }: { initial: SrsSettings; save: ReturnType<typeof useSaveSrsSettings> }) {
  const [retention, setRetention] = useState(Math.round(initial.desired_retention * 100))
  const [perDay, setPerDay] = useState(initial.new_cards_per_day)
  const changed = retention !== Math.round(initial.desired_retention * 100) || perDay !== initial.new_cards_per_day
  const validPerDay = Number.isInteger(perDay) && perDay >= 5 && perDay <= 100

  return (
    <form
      className="card stack"
      onSubmit={(e) => {
        e.preventDefault()
        save.mutate({ desired_retention: retention / 100, new_cards_per_day: perDay })
      }}
    >
      <div className="card-title" style={{ marginBottom: 0 }}>
        <h3>Ôn tập từ vựng</h3>
      </div>
      <label className="field">
        Mục tiêu ghi nhớ: {retention}%
        <input type="range" min={85} max={95} step={1} value={retention} onChange={(e) => setRetention(Number(e.target.value))} />
      </label>
      <p className="small muted">
        Cao hơn thì nhớ chắc hơn nhưng phải ôn thường xuyên hơn. 90% là mức cân bằng được khuyên dùng.
      </p>
      <label className="field" style={{ maxWidth: 240 }}>
        Số từ mới tối đa mỗi ngày
        <input
          className="input"
          type="number"
          min={5}
          max={100}
          value={perDay}
          onChange={(e) => setPerDay(Number(e.target.value))}
        />
      </label>
      <p className="small muted">Từ mới vượt mức này sẽ bắt đầu ôn vào những ngày sau, để ngày ôn không bị dồn.</p>
      {save.error && <ErrorBox error={save.error} />}
      {save.isSuccess && !changed && <div className="alert success">Đã lưu.</div>}
      <div>
        <button className="btn primary" type="submit" disabled={!changed || !validPerDay || save.isPending}>
          {save.isPending && <Spinner small />} Lưu
        </button>
      </div>
    </form>
  )
}
