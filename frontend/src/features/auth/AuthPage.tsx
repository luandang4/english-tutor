import { useState } from 'react'
import { Link, Navigate, useNavigate, useSearchParams } from 'react-router-dom'

import { useLogin, useMe, useMeta, useRegister } from '../../api/hooks'
import { ErrorBox, Loading, PasswordInput, Spinner } from '../../components/ui'
import { passwordStrongEnough } from '../../lib/password'
import './auth.css'

/** Only allow in-app redirects after login (no open redirect to other sites). */
function safeNext(raw: string | null): string {
  return raw && raw.startsWith('/') && !raw.startsWith('//') ? raw : '/'
}

export function AuthPage({ mode }: { mode: 'login' | 'register' }) {
  const { data: me, isPending } = useMe()
  const { data: meta } = useMeta()
  const [params] = useSearchParams()
  const next = safeNext(params.get('next'))
  const navigate = useNavigate()
  const login = useLogin()
  const register = useRegister()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [name, setName] = useState('')

  if (isPending) return <Loading />
  if (me) return <Navigate to={next} replace />

  const isLogin = mode === 'login'
  const closed = !isLogin && meta?.registration_open === false
  const mutation = isLogin ? login : register
  const submit = (e: { preventDefault(): void }) => {
    e.preventDefault()
    const done = { onSuccess: () => navigate(next, { replace: true }) }
    if (isLogin) login.mutate({ email, password }, done)
    else register.mutate({ email, password, display_name: name }, done)
  }
  const swapTo = `${isLogin ? '/register' : '/login'}${next !== '/' ? `?next=${encodeURIComponent(next)}` : ''}`

  return (
    <div className="auth-screen">
      <div className="aurora" aria-hidden="true">
        <span />
        <span />
        <span />
      </div>
      <form className="auth-card" onSubmit={submit}>
        <div className="auth-brand">
          <span className="logo auth-logo" aria-hidden="true" />
          <h1>{isLogin ? 'Chào mừng trở lại' : 'Tạo tài khoản'}</h1>
          <p className="muted">
            {isLogin ? 'Đăng nhập để tiếp tục lộ trình học của bạn.' : 'Mỗi tài khoản có lộ trình, bộ từ và lịch sử riêng.'}
          </p>
        </div>

        {!isLogin && (
          <label className="field">
            Tên hiển thị
            <input
              className="input"
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
              maxLength={80}
              autoComplete="nickname"
              placeholder="VD: Luân"
            />
          </label>
        )}
        <label className="field">
          Email
          <input
            className="input"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            autoComplete="email"
            placeholder="ban@example.com"
          />
        </label>
        <PasswordInput
          label="Mật khẩu"
          value={password}
          onChange={setPassword}
          autoComplete={isLogin ? 'current-password' : 'new-password'}
          showRules={!isLogin}
          placeholder={isLogin ? '••••••••' : 'Ít nhất 8 ký tự, có chữ và số'}
        />

        {closed && <div className="alert info">Đăng ký tài khoản mới đang tạm đóng. Hãy liên hệ admin.</div>}
        {!isLogin && !closed && (
          <p className="small muted">Tài khoản mới cần admin duyệt trước khi dùng các tính năng học.</p>
        )}
        {mutation.error && <ErrorBox error={mutation.error} />}

        <button
          className="btn primary auth-submit"
          type="submit"
          disabled={mutation.isPending || (!isLogin && (closed || !passwordStrongEnough(password)))}
        >
          {mutation.isPending && <Spinner small />}
          {isLogin ? 'Đăng nhập' : 'Tạo tài khoản'}
        </button>

        <p className="auth-swap muted">
          {isLogin ? 'Chưa có tài khoản?' : 'Đã có tài khoản?'} <Link to={swapTo}>{isLogin ? 'Đăng ký' : 'Đăng nhập'}</Link>
        </p>
      </form>
    </div>
  )
}
