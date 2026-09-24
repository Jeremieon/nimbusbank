import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { admin } from '../api'
import Layout from '../components/Layout'

function statusClass(code) {
  if (code >= 500) return 'failed'
  if (code >= 400) return 'pending'
  return ''
}

function shortTime(ts) {
  try {
    return new Date(ts).toLocaleTimeString()
  } catch {
    return ts
  }
}

export default function Ops() {
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const timer = useRef(null)
  const navigate = useNavigate()

  useEffect(() => {
    if (!localStorage.getItem('nimbus_access_token')) {
      navigate('/login')
      return
    }
    const tick = () => {
      // /admin/traffic is an open (LAB-ONLY) observability view — no auth
      // needed — so this dashboard just polls it every ~4s.
      admin
        .traffic()
        .then((d) => {
          setData(d)
          setError('')
        })
        .catch((err) => setError(err.message))
    }
    tick()
    timer.current = setInterval(tick, 4000)
    return () => clearInterval(timer.current)
  }, [navigate])

  const perService = data ? Object.entries(data.per_service) : []
  const buckets = data ? data.per_status_bucket : {}
  const recent = data ? data.recent : []

  return (
    <Layout>
      <div className="page-head">
        <div>
          <p className="subtitle" style={{ margin: 0 }}>Operations</p>
          <h1 className="page-title">Ops console</h1>
        </div>
        <Link to="/dashboard" className="btn-outline">← Dashboard</Link>
      </div>

      {error && <div className="error">{error}</div>}

      <p className="subtitle">
        Live cross-service request traffic, refreshing every 4 seconds. Fed by the fire-and-forget
        log events every service posts to admin-service.
      </p>

      <div className="account-grid" style={{ marginBottom: 8 }}>
        <div className="account-card">
          <div className="account-card-head"><span className="account-type">Total requests</span></div>
          <div className="account-balance">{data ? data.total : '—'}</div>
        </div>
        <div className="account-card">
          <div className="account-card-head"><span className="account-type">Status mix</span></div>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            {['2xx', '3xx', '4xx', '5xx'].map((b) => (
              <span key={b} className={`status-badge ${b === '5xx' ? 'failed' : b === '4xx' ? 'pending' : ''}`}>
                {b} {buckets[b] || 0}
              </span>
            ))}
          </div>
        </div>
        <div className="account-card">
          <div className="account-card-head"><span className="account-type">Per service</span></div>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            {perService.map(([svc, cnt]) => (
              <span key={svc} className="ccy-chip">{svc}: {cnt}</span>
            ))}
            {perService.length === 0 && <span className="txn-sub">No traffic yet</span>}
          </div>
        </div>
      </div>

      <p className="section-label">Recent requests</p>
      <div className="ledger">
        <table className="ledger-table">
          <thead>
            <tr>
              <th>Service</th>
              <th>Method</th>
              <th>Path</th>
              <th>Status</th>
              <th>User</th>
              <th>Time</th>
            </tr>
          </thead>
          <tbody>
            {recent.map((r) => (
              <tr key={r.id}>
                <td className="txn-desc" style={{ textTransform: 'capitalize' }}>{r.service}</td>
                <td className="txn-sub">{r.method}</td>
                <td className="txn-sub">{r.path}</td>
                <td>
                  <span className={`status-badge ${statusClass(r.status_code)}`}>{r.status_code}</span>
                </td>
                <td className="txn-sub">{r.user_id ? `${r.user_id.slice(0, 8)}…` : '—'}</td>
                <td className="txn-sub">{shortTime(r.ts)}</td>
              </tr>
            ))}
            {recent.length === 0 && (
              <tr>
                <td colSpan={6} className="empty">No requests logged yet — go click around the app.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </Layout>
  )
}
