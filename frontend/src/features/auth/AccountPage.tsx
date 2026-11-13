import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { useChangePassword, useLogout, useMe } from '../../api/hooks'
import { AudioSourceSelect, ErrorBox, Icon, PageHeader, PasswordInput, Spinner, SpeakButton } from '../../components/ui'
import { passwordStrongEnough } from '../../lib/password'
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

      {me.is_admin && (
        <Link to="/admin" className="card row admin-link">
          <Icon name="shield" /> <b className="spacer">Trang quản trị</b> <Icon name="arrowRight" size={16} />
        </Link>
      )}

      <div className="card stack">
        <div className="card-title" style={{ marginBottom: 0 }}>
          <h3>Âm thanh phát âm</h3>
        </div>
        <p className="small muted">Nguồn đọc từ vựng và câu ví dụ. Lưu riêng cho trình duyệt này.</p>
        <div className="row">
          <AudioSourceSelect />
          <SpeakButton text="Hello, nice to meet you." label="Nghe thử" />
        </div>
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
        <PasswordInput label="Mật khẩu hiện tại" value={current} onChange={setCurrent} autoComplete="current-password" />
        <PasswordInput
          label="Mật khẩu mới"
          value={next}
          onChange={setNext}
          autoComplete="new-password"
          showRules
          placeholder="Ít nhất 8 ký tự, có chữ và số"
        />
        {change.error && <ErrorBox error={change.error} />}
        {change.isSuccess && (
          <div className="alert success">Đã đổi mật khẩu. Các thiết bị khác đã được đăng xuất.</div>
        )}
        <div>
          <button className="btn primary" type="submit" disabled={change.isPending || !passwordStrongEnough(next)}>
            {change.isPending && <Spinner small />} Đổi mật khẩu
          </button>
        </div>
      </form>
    </div>
  )
}
