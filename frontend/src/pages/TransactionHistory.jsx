import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'

import { transfers } from '../api'

function formatCents(cents) {
  return (cents / 100).toLocaleString('en-US', { style: 'currency', currency: 'USD' })
}

export default function TransactionHistory() {
  const { id } = useParams()
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
    <div className="history-page">
      <div className="detail-header">
        <p className="brand">NimbusBank</p>
        <Link to={`/accounts/${id}`} className="secondary-link">
          Back to account
        </Link>
      </div>
      <h1 className="title">Transaction history — account {id}</h1>
      {error && <div className="error">{error}</div>}
      <table className="transfer-table">
        <thead>
          <tr>
            <th>Date</th>
            <th>From</th>
            <th>To</th>
            <th>Amount</th>
            <th>Memo</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((t) => (
            <tr key={t.id}>
              <td>{new Date(t.created_at).toLocaleString()}</td>
              <td>{t.from_account_id}</td>
              <td>{t.to_account_id}</td>
              <td className={t.to_account_id === Number(id) ? 'amount-positive' : ''}>
                {formatCents(t.amount_cents)}
              </td>
              {/*
                INTENTIONALLY VULNERABLE: memo is rendered as raw HTML instead
                of text ({t.memo}) — a stored <script> or <img onerror=...>
                payload in a transfer's memo executes here (stored XSS, OWASP
                Top 10 / F5 XC WAF category). See transfers-service's
                models.py for the matching server-side comment.
              */}
              <td dangerouslySetInnerHTML={{ __html: t.memo || '' }} />
              <td>
                <span className="status-pill">{t.status}</span>
              </td>
            </tr>
          ))}
          {rows.length === 0 && (
            <tr>
              <td colSpan={6} className="subtitle">
                No transfers yet.
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  )
}
