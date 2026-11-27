import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { useChangePassword, useLogout, useMe, useRenameMe } from '../../api/hooks'
import { AudioSourceSelect, ErrorBox, Icon, PageHeader, PasswordInput, Spinner, SpeakButton } from '../../components/ui'
import { passwordStrongEnough } from '../../lib/password'
import { THEME_OPTIONS, useTheme } from '../../lib/theme'
import { Segmented } from '../../components/ui/Segmented'
import { MyPlan } from './MyPlan'
import { SrsSettingsCard } from '../review/SrsSettingsCard'
import './auth.css'

export function AccountPage() {
  const { data: me } = useMe()
  const logout = useLogout()
  const change = useChangePassword()
  const navigate = useNavigate()
  const [current, setCurrent] = useState('')
  const [next, setNext] = useState('')
  const [theme, , setTheme] = useTheme()

  if (!me) return null
  return (
    <div className="page" style={{ maxWidth: 720 }}>
      <PageHeader title="Tài khoản" subtitle="Thông tin đăng nhập và bảo mật." />

      <div className="card row" style={{ gap: 16 }}>
        <span className="avatar lg">{me.display_name.charAt(0).toUpperCase()}</span>
        <div className="spacer">
          <DisplayName name={me.display_name} />
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

      <MyPlan />

      {me.is_admin && (
        <Link to="/admin" className="card row admin-link">
          <Icon name="shield" /> <b className="spacer">Trang quản trị</b> <Icon name="arrowRight" size={16} />
        </Link>
      )}

      <div className="card stack">
        <div className="card-title" style={{ marginBottom: 0 }}>
          <h3>Giao diện</h3>
        </div>
        <p className="small muted">Sáng, tối hoặc tự đổi theo cài đặt của máy. Lưu riêng cho trình duyệt này.</p>
        <Segmented label="Chế độ màu" value={theme} options={THEME_OPTIONS} onChange={setTheme} />
      </div>

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

      <SrsSettingsCard />

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

/** The account name, with inline editing. */
function DisplayName({ name }: { name: string }) {
  const rename = useRenameMe()
  const [draft, setDraft] = useState<string | null>(null)
  if (draft === null)
    return (
      <div className="row" style={{ gap: 6 }}>
        <h2 style={{ fontSize: '1.2rem' }}>{name}</h2>
        <button type="button" className="btn icon sm ghost" aria-label="Đổi tên" title="Đổi tên" onClick={() => setDraft(name)}>
          <Icon name="pen" size={16} />
        </button>
      </div>
    )
  const value = draft.trim()
  return (
    <form
      className="stack"
      style={{ gap: 6 }}
      onSubmit={(e) => {
        e.preventDefault()
        if (!value || value === name) return setDraft(null)
        rename.mutate(value, { onSuccess: () => setDraft(null) })
      }}
    >
      <div className="row" style={{ gap: 6, flexWrap: 'wrap' }}>
        <input
          className="input"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => e.key === 'Escape' && setDraft(null)}
          maxLength={80}
          aria-label="Tên hiển thị"
          autoFocus
          style={{ maxWidth: 260 }}
        />
        <button className="btn sm primary" type="submit" disabled={!value || rename.isPending}>
          Lưu
        </button>
        <button className="btn sm ghost" type="button" onClick={() => setDraft(null)}>
          Huỷ
        </button>
      </div>
      {rename.error && <ErrorBox error={rename.error} />}
    </form>
  )
}
