import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { accounts, auth } from '../api'
import Layout from '../components/Layout'
import { formatMoney, maskAccountNumber, totalInUsdCents } from '../money'

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

  if (loading) return null

  const firstName = user ? user.full_name.split(' ')[0] : ''
  const totalUsd = totalInUsdCents(accts)

  return (
    <Layout>
      <p className="subtitle" style={{ margin: 0 }}>Overview</p>
      <h1 className="greeting">{user ? `Welcome back, ${firstName}` : 'Welcome back'}</h1>

      {error && <div className="error">{error}</div>}

      <div className="total-card">
        <p className="label">Total balance</p>
        <div className="amount">{formatMoney(totalUsd, 'USD')}</div>
        <p className="sublabel">Across {accts.length} account{accts.length === 1 ? '' : 's'}, converted to USD</p>
      </div>

      <p className="section-label">Your accounts</p>
      <div className="account-grid">
        {accts.map((a) => (
          <div key={a.id} className="account-card">
            <div className="account-card-head">
              <span className="account-type">{a.account_type}</span>
              <span className="ccy-chip">{a.currency}</span>
            </div>
            <div className="account-number">{maskAccountNumber(a.account_number)}</div>
            <div className="account-balance">{formatMoney(a.balance_cents, a.currency)}</div>
            <div className="account-actions">
              <Link to={`/accounts/${a.id}`} className="btn-outline">View</Link>
              <Link to={`/transfer?from=${a.id}`} className="btn">Send money</Link>
            </div>
          </div>
        ))}
        {accts.length === 0 && <p className="subtitle">No accounts found.</p>}
      </div>
    </Layout>
  )
}
