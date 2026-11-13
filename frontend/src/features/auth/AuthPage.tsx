import { useState } from 'react'
import { Link, Navigate, useNavigate, useSearchParams } from 'react-router-dom'

import { useLogin, useMe, useRegister } from '../../api/hooks'
import { ErrorBox, Loading, Spinner } from '../../components/ui'
import './auth.css'

/** Only allow in-app redirects after login (no open redirect to other sites). */
function safeNext(raw: string | null): string {
  return raw && raw.startsWith('/') && !raw.startsWith('//') ? raw : '/'
}

export function AuthPage({ mode }: { mode: 'login' | 'register' }) {
  const { data: me, isPending } = useMe()
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
        <label className="field">
          Mật khẩu
          <input
            className="input"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            minLength={isLogin ? undefined : 8}
            maxLength={128}
            autoComplete={isLogin ? 'current-password' : 'new-password'}
            placeholder={isLogin ? '••••••••' : 'Ít nhất 8 ký tự'}
          />
        </label>

        {mutation.error && <ErrorBox error={mutation.error} />}

        <button className="btn primary auth-submit" type="submit" disabled={mutation.isPending}>
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
