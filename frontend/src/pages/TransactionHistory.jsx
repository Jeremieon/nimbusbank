import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'

import { transfers } from '../api'
import Layout from '../components/Layout'
import { formatMoney } from '../money'

export default function TransactionHistory() {
  const { id } = useParams()
  const accountId = Number(id)
  const [rows, setRows] = useState([])
  const [error, setError] = useState('')
  const navigate = useNavigate()

  useEffect(() => {
    if (!localStorage.getItem('nimbus_access_token')) {
      navigate('/login')
      return
    }
    transfers
      .list(id)
      .then(setRows)
      .catch((err) => setError(err.message))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id])

  return (
    <Layout>
      <div className="page-head">
        <div>
          <p className="subtitle" style={{ margin: 0 }}>Account {id}</p>
          <h1 className="page-title">Transactions</h1>
        </div>
        <Link to={`/accounts/${id}`} className="btn-outline">← Account</Link>
      </div>

      {error && <div className="error">{error}</div>}

      <div className="ledger">
        <table className="ledger-table">
          <thead>
            <tr>
              <th>Date</th>
              <th>Description</th>
              <th>Direction</th>
              <th style={{ textAlign: 'right' }}>Amount</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((t) => {
              const isIncoming = t.to_account_id === accountId
              // For an incoming leg, the amount landed in the destination
              // currency; for an outgoing leg it left in the source currency.
              const displayCents = isIncoming
                ? (t.to_amount_cents ?? t.amount_cents)
                : t.amount_cents
              const displayCcy = isIncoming
                ? (t.to_currency || t.currency || 'USD')
                : (t.currency || 'USD')
              const sign = isIncoming ? '+' : '−'
              return (
                <tr key={t.id}>
                  <td>
                    <div className="txn-desc">{new Date(t.created_at).toLocaleDateString()}</div>
                    <div className="txn-sub">{new Date(t.created_at).toLocaleTimeString()}</div>
                  </td>
                  <td>
                    {/*
                      INTENTIONALLY VULNERABLE: memo is rendered as raw HTML
                      instead of text ({t.memo}) — a stored <script> or
                      <img onerror=...> payload in a transfer's memo executes
                      here (stored XSS, OWASP Top 10 / F5 XC WAF category). See
                      transfers-service's models.py for the matching
                      server-side comment.
                    */}
                    <div className="txn-desc" dangerouslySetInnerHTML={{ __html: t.memo || '<em>No memo</em>' }} />
                    <div className="txn-sub">#{t.from_account_id} → #{t.to_account_id}</div>
                  </td>
                  <td>
                    <span className={`dir-pill ${isIncoming ? 'dir-in' : 'dir-out'}`}>
                      {isIncoming ? 'In' : 'Out'}
                    </span>
                  </td>
                  <td style={{ textAlign: 'right' }} className={isIncoming ? 'amount-in' : 'amount-out'}>
                    {sign} {formatMoney(Math.abs(displayCents), displayCcy)}
                  </td>
                  <td>
                    <span className={`status-badge ${t.status}`}>{t.status}</span>
                  </td>
                </tr>
              )
            })}
            {rows.length === 0 && (
              <tr>
                <td colSpan={5} className="empty">No transactions yet.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </Layout>
  )
}
