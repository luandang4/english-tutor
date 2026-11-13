import { useState } from 'react'

import { PASSWORD_RULES } from '../../lib/password'
import { Icon } from './Icon'

/** Password field with a show / hide button and (for new passwords) a live checklist of the rules. */
export function PasswordInput(props: {
  label: string
  value: string
  onChange: (value: string) => void
  autoComplete: 'current-password' | 'new-password'
  showRules?: boolean
  placeholder?: string
}) {
  const [visible, setVisible] = useState(false)
  return (
    <label className="field">
      {props.label}
      <span className="password-input">
        <input
          className="input"
          type={visible ? 'text' : 'password'}
          value={props.value}
          onChange={(e) => props.onChange(e.target.value)}
          required
          maxLength={128}
          autoComplete={props.autoComplete}
          placeholder={props.placeholder}
        />
        <button
          type="button"
          className="password-toggle"
          onClick={() => setVisible((v) => !v)}
          aria-label={visible ? 'Ẩn mật khẩu' : 'Hiện mật khẩu'}
          title={visible ? 'Ẩn mật khẩu' : 'Hiện mật khẩu'}
        >
          <Icon name={visible ? 'eyeOff' : 'eye'} size={18} />
        </button>
      </span>
      {props.showRules && (
        <span className="password-rules" aria-live="polite">
          {PASSWORD_RULES.map((r) => {
            const ok = r.ok(props.value)
            return (
              <span key={r.label} className={ok ? 'ok' : ''}>
                <Icon name={ok ? 'check' : 'x'} size={12} /> {r.label}
              </span>
            )
          })}
          <span className="hint">Nên thêm chữ hoa và ký tự đặc biệt (!@#…) để mạnh hơn.</span>
        </span>
      )}
    </label>
  )
}
