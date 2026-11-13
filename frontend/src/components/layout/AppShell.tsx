import { Link, Navigate, NavLink, Outlet, useLocation } from 'react-router-dom'

import { useDeckStats, useMe } from '../../api/hooks'
import '../../features/auth/auth.css'
import { Loading } from '../ui'
import { Icon, type IconName } from '../ui/Icon'

const NAV: { to: string; label: string; short: string; icon: IconName; end?: boolean }[] = [
  { to: '/', label: 'Tổng quan', short: 'Tổng quan', icon: 'home', end: true },
  { to: '/conversation', label: 'Hội thoại', short: 'Nói', icon: 'mic' },
  { to: '/vocabulary', label: 'Từ vựng', short: 'Từ vựng', icon: 'book' },
  { to: '/grammar', label: 'Ngữ pháp', short: 'Ngữ pháp', icon: 'grammar' },
  { to: '/writing', label: 'Viết', short: 'Viết', icon: 'pen' },
  { to: '/review', label: 'Ôn tập từ', short: 'Ôn tập', icon: 'cards' },
]

function NavItems({ compact }: { compact?: boolean }) {
  const { data: deck } = useDeckStats()
  return (
    <>
      {NAV.map((item) => (
        <NavLink key={item.to} to={item.to} end={item.end} className="nav-link">
          <Icon name={item.icon} />
          <span>{compact ? item.short : item.label}</span>
          {item.to === '/review' && !!deck?.due && <span className="nav-badge">{deck.due}</span>}
        </NavLink>
      ))}
    </>
  )
}

export function AppShell() {
  const { data: me, isPending } = useMe()
  const location = useLocation()
  if (isPending) return <Loading />
  if (!me) return <Navigate to={`/login?next=${encodeURIComponent(location.pathname + location.search)}`} replace />
  return (
    <>
      <div className="aurora" aria-hidden="true">
        <span />
        <span />
        <span />
      </div>
      <div className="shell">
        <aside className="sidebar">
          <div className="brand">
            <span className="logo" aria-hidden="true" />
            <div>
              <b>English Tutor</b>
              <small>Học tiếng Anh cùng AI</small>
            </div>
          </div>
          <nav className="stack" style={{ gap: 4 }} aria-label="Điều hướng chính">
            <NavItems />
          </nav>
          <Link to="/account" className="user-chip" title="Tài khoản">
            <span className="avatar">{me.display_name.charAt(0).toUpperCase()}</span>
            <span className="who">
              <b>{me.display_name}</b>
              <small>{me.email}</small>
            </span>
          </Link>
        </aside>
        <main className="main">
          <Outlet />
        </main>
        <nav className="tabbar" aria-label="Điều hướng chính">
          <NavItems compact />
        </nav>
      </div>
    </>
  )
}
