import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { useChangePassword, useLogout, useMe } from '../../api/hooks'
import { ErrorBox, Icon, PageHeader, Spinner } from '../../components/ui'
import './auth.css'

export function AccountPage() {
  const { data: me } = useMe()
  const logout = useLogout()
  const change = useChangePassword()
  const navigate = useNavigate()
  const [current, setCurrent] = useState('')
  const [next, setNext] = useState('')

  if (!me) return null
  return (
    <div className="page" style={{ maxWidth: 720 }}>
      <PageHeader title="Tài khoản" subtitle="Thông tin đăng nhập và bảo mật." />

      <div className="card row" style={{ gap: 16 }}>
        <span className="avatar lg">{me.display_name.charAt(0).toUpperCase()}</span>
        <div className="spacer">
          <h2 style={{ fontSize: '1.2rem' }}>{me.display_name}</h2>
          <p className="muted">{me.email}</p>
          <p className="small muted">Tham gia {new Date(me.created_at).toLocaleDateString('vi-VN')}</p>
        </div>
        <button
          className="btn danger"
          onClick={() => logout.mutate(undefined, { onSettled: () => navigate('/login', { replace: true }) })}
          disabled={logout.isPending}
        >
          <Icon name="arrowRight" size={16} /> Đăng xuất
        </button>
      </div>

      <form
        className="card stack"
        onSubmit={(e) => {
          e.preventDefault()
          change.mutate(
            { current_password: current, new_password: next },
            {
              onSuccess: () => {
                setCurrent('')
                setNext('')
              },
            },
          )
        }}
      >
        <div className="card-title" style={{ marginBottom: 0 }}>
          <h3>Đổi mật khẩu</h3>
        </div>
        <label className="field">
          Mật khẩu hiện tại
          <input
            className="input"
            type="password"
            value={current}
            onChange={(e) => setCurrent(e.target.value)}
            required
            autoComplete="current-password"
          />
        </label>
        <label className="field">
          Mật khẩu mới
          <input
            className="input"
            type="password"
            value={next}
            onChange={(e) => setNext(e.target.value)}
            required
            minLength={8}
            maxLength={128}
            autoComplete="new-password"
            placeholder="Ít nhất 8 ký tự"
          />
        </label>
        {change.error && <ErrorBox error={change.error} />}
        {change.isSuccess && (
          <div className="alert success">Đã đổi mật khẩu. Các thiết bị khác đã được đăng xuất.</div>
        )}
        <div>
          <button className="btn primary" type="submit" disabled={change.isPending}>
            {change.isPending && <Spinner small />} Đổi mật khẩu
          </button>
        </div>
      </form>
    </div>
  )
}
