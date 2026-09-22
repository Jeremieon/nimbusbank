import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'

import { accounts } from '../api'

function formatCents(cents) {
  return (cents / 100).toLocaleString('en-US', { style: 'currency', currency: 'USD' })
}

export default function AccountDetail() {
  const { id } = useParams()
  const [account, setAccount] = useState(null)
  const [error, setError] = useState('')
  const [linkUrl, setLinkUrl] = useState('')
  const [linkResult, setLinkResult] = useState(null)
  const [linkLoading, setLinkLoading] = useState(false)
  const navigate = useNavigate()

  const load = () => {
    accounts
      .get(id)
      .then(setAccount)
      .catch((err) => setError(err.message))
  }

  useEffect(() => {
    if (!localStorage.getItem('nimbus_access_token')) {
      navigate('/login')
      return
    }
    load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id])

  const onDownloadStatement = () => {
    window.open(accounts.statementUrl(id), '_blank')
  }

  const onLinkExternal = async (e) => {
    e.preventDefault()
    setLinkLoading(true)
    setLinkResult(null)
    try {
      const res = await accounts.linkExternal({ account_id: Number(id), verification_url: linkUrl })
      setLinkResult(res)
    } catch (err) {
      setLinkResult({ error: err.message })
    } finally {
      setLinkLoading(false)
    }
  }

  return (
    <div className="account-detail">
      <div className="detail-header">
        <p className="brand">NimbusBank</p>
        <Link to="/dashboard" className="secondary-link">
          Back to dashboard
        </Link>
      </div>

      {error && <div className="error">{error}</div>}

      {account && (
        <>
          <h1 className="title">
            {account.account_type} — {account.account_number}
          </h1>
          <div className="kv">
            <span>Balance</span>
            <span>{formatCents(account.balance_cents)}</span>
          </div>
          <div className="kv">
            <span>Currency</span>
            <span>{account.currency}</span>
          </div>
          <div className="kv">
            <span>Owner user id</span>
            <span>{account.user_id}</span>
          </div>
          <div className="kv">
            <span>SSN on file</span>
            <span>•••-••-{account.ssn_full.slice(-4)}</span>
          </div>
          <div className="kv">
            <span>Date of birth</span>
            <span>{account.date_of_birth}</span>
          </div>

          <div className="actions-row">
            <button className="secondary-link" onClick={onDownloadStatement}>
              Download statement
            </button>
            <Link to={`/accounts/${id}/history`} className="secondary-link">
              Transaction history
            </Link>
          </div>

          <p className="section-label">Link an external account</p>
          <p className="subtitle">
            Enter a verification URL — the server fetches it and shows you what came back.
          </p>
          <form onSubmit={onLinkExternal}>
            <div className="field">
              <label htmlFor="verification_url">Verification URL</label>
              <input
                id="verification_url"
                value={linkUrl}
                onChange={(e) => setLinkUrl(e.target.value)}
                placeholder="https://example.com/verify"
                required
              />
            </div>
            <button className="primary" type="submit" disabled={linkLoading}>
              {linkLoading ? 'Verifying…' : 'Verify & link'}
            </button>
          </form>
          {linkResult && <pre className="raw-response">{JSON.stringify(linkResult, null, 2)}</pre>}
        </>
      )}
    </div>
  )
}
