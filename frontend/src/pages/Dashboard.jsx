import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { accounts, auth } from '../api'

function formatCents(cents) {
  return (cents / 100).toLocaleString('en-US', { style: 'currency', currency: 'USD' })
}

export default function Dashboard() {
  const [user, setUser] = useState(null)
  const [accts, setAccts] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const navigate = useNavigate()

  useEffect(() => {
    if (!localStorage.getItem('nimbus_access_token')) {
      navigate('/login')
      return
    }
    Promise.all([auth.me(), accounts.list()])
      .then(([me, list]) => {
        setUser(me)
        setAccts(list)
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }, [navigate])

  const onLogout = () => {
    localStorage.removeItem('nimbus_access_token')
    navigate('/login')
  }

  if (loading) return null

  return (
    <div className="dashboard">
      <div className="dashboard-header">
        <div>
          <p className="brand">NimbusBank</p>
          <h1 className="title" style={{ margin: 0 }}>
            {user ? `Welcome, ${user.full_name}` : 'Welcome'}
          </h1>
        </div>
        <button className="secondary" onClick={onLogout}>
          Log out
        </button>
      </div>

      {error && <div className="error">{error}</div>}

      <p className="section-label">Your accounts</p>
      <div className="account-list">
        {accts.map((a) => (
          <Link key={a.id} to={`/accounts/${a.id}`} className="account-card">
            <div className="account-card-top">
              <span>
                {a.account_type} · {a.account_number}
              </span>
              <span>id {a.id}</span>
            </div>
            <div className="account-card-balance">{formatCents(a.balance_cents)}</div>
          </Link>
        ))}
        {accts.length === 0 && <p className="subtitle">No accounts found.</p>}
      </div>

      <div className="actions-row">
        <Link to="/transfer" className="secondary-link">
          Send a transfer
        </Link>
      </div>
    </div>
  )
}
