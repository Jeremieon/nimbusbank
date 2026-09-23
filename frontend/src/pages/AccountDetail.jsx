import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'

import { accounts } from '../api'
import Layout from '../components/Layout'
import { formatMoney } from '../money'

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
    <Layout>
      <div className="page-head">
        <Link to="/dashboard" className="btn-outline">← Dashboard</Link>
        <Link to={`/transfer?from=${id}`} className="btn">Send money</Link>
      </div>

      {error && <div className="error">{error}</div>}

      {account && (
        <>
          <p className="subtitle" style={{ margin: 0, textTransform: 'capitalize' }}>
            {account.account_type} account
          </p>
          <h1 className="page-title" style={{ marginBottom: 8 }}>{account.account_number}</h1>

          <div className="detail-grid" style={{ marginTop: 22 }}>
            <div className="card">
              <p className="label" style={{ color: 'var(--muted)', fontWeight: 500, margin: 0 }}>
                Available balance
              </p>
              <div className="big-balance">{formatMoney(account.balance_cents, account.currency)}</div>
              <div className="kv">
                <span className="k">Currency</span>
                <span className="v">{account.currency}</span>
              </div>
              <div className="kv">
                <span className="k">Account type</span>
                <span className="v" style={{ textTransform: 'capitalize' }}>{account.account_type}</span>
              </div>
              <div className="kv">
                <span className="k">Owner user id</span>
                <span className="v">{account.user_id}</span>
              </div>
              <div className="kv">
                <span className="k">SSN on file</span>
                <span className="v">•••-••-{account.ssn_full.slice(-4)}</span>
              </div>
              <div className="kv">
                <span className="k">Date of birth</span>
                <span className="v">{account.date_of_birth}</span>
              </div>

              <div className="account-actions" style={{ marginTop: 20 }}>
                <button className="btn-outline" onClick={onDownloadStatement}>Download statement</button>
                <Link to={`/accounts/${id}/history`} className="btn-outline">Transactions</Link>
              </div>
            </div>

            <div className="card">
              <h3 style={{ marginTop: 0, fontSize: 18 }}>Verify external account</h3>
              <p className="subtitle">
                Enter a verification URL — we fetch it and show you what came back.
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
            </div>
          </div>
        </>
      )}
    </Layout>
  )
}
