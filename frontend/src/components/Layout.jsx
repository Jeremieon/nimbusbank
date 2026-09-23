import { Link, NavLink, useNavigate } from 'react-router-dom'

// Shared chrome for every signed-in page: a sticky top bar with the pink
// NimbusBank wordmark on the left and the primary nav + Log out on the right,
// wrapped around a centered ~1080px content container.
export default function Layout({ children, authed = true }) {
  const navigate = useNavigate()

  const onLogout = () => {
    localStorage.removeItem('nimbus_access_token')
    navigate('/login')
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="topbar-inner">
          <Link to={authed ? '/dashboard' : '/login'} className="wordmark">
            <span className="wordmark-mark" aria-hidden="true">◈</span>
            NimbusBank
          </Link>
          {authed && (
            <nav className="topnav">
              <NavLink to="/dashboard" className={({ isActive }) => (isActive ? 'active' : '')}>
                Dashboard
              </NavLink>
              <NavLink to="/transfer" className={({ isActive }) => (isActive ? 'active' : '')}>
                Transfer
              </NavLink>
              <NavLink to="/cards" className={({ isActive }) => (isActive ? 'active' : '')}>
                Cards
              </NavLink>
              <NavLink to="/kyc" className={({ isActive }) => (isActive ? 'active' : '')}>
                Verify ID
              </NavLink>
              <NavLink to="/support" className={({ isActive }) => (isActive ? 'active' : '')}>
                Support
              </NavLink>
              <NavLink to="/security" className={({ isActive }) => (isActive ? 'active' : '')}>
                Security
              </NavLink>
              <NavLink to="/profile" className={({ isActive }) => (isActive ? 'active' : '')}>
                Profile
              </NavLink>
              <NavLink to="/ops" className={({ isActive }) => (isActive ? 'active' : '')}>
                Ops
              </NavLink>
              <button className="btn-ghost" onClick={onLogout}>
                Log out
              </button>
            </nav>
          )}
        </div>
      </header>
      <main className="container">{children}</main>
    </div>
  )
}
