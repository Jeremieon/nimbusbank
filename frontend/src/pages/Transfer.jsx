import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'

import { accounts as accountsApi, transfers } from '../api'
import Layout from '../components/Layout'
import { convertCents, formatMoney } from '../money'

export default function Transfer() {
  const [searchParams] = useSearchParams()
  const [accts, setAccts] = useState([])
  const [form, setForm] = useState({
    from_account_id: '',
    to_account_id: '',
    amount: '',
    memo: '',
  })
  // Best-effort guess of the destination currency for the preview: we only
  // know currencies of the caller's own accounts. Default to USD otherwise;
  // the server is authoritative on execution.
  const [toCurrency, setToCurrency] = useState('USD')
  const [error, setError] = useState('')
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const navigate = useNavigate()

  useEffect(() => {
    if (!localStorage.getItem('nimbus_access_token')) {
      navigate('/login')
      return
    }
    accountsApi
      .list()
      .then((list) => {
        setAccts(list)
        const preset = searchParams.get('from')
        setForm((f) => ({
          ...f,
          from_account_id: preset || (list[0] ? String(list[0].id) : ''),
        }))
      })
      .catch((err) => setError(err.message))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const onChange = (e) => setForm({ ...form, [e.target.name]: e.target.value })

  const fromAccount = useMemo(
    () => accts.find((a) => String(a.id) === String(form.from_account_id)),
    [accts, form.from_account_id],
  )
  const fromCurrency = fromAccount ? fromAccount.currency : 'USD'

  // If the destination id is one of the caller's own accounts, use its real
  // currency in the preview; else fall back to the manually-picked toCurrency.
  const destOwn = useMemo(
    () => accts.find((a) => String(a.id) === String(form.to_account_id)),
    [accts, form.to_account_id],
  )
  const effectiveToCcy = destOwn ? destOwn.currency : toCurrency

  const amountCents = Math.round((Number(form.amount) || 0) * 100)
  const preview = convertCents(amountCents, fromCurrency, effectiveToCcy)

  const onSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setResult(null)
    setLoading(true)
    try {
      const payload = {
        from_account_id: Number(form.from_account_id),
        to_account_id: Number(form.to_account_id),
        amount_cents: amountCents,
        memo: form.memo,
      }
      const res = await transfers.create(payload)
      setResult(res)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <Layout>
      <div className="page-head">
        <div>
          <p className="subtitle" style={{ margin: 0 }}>Move money</p>
          <h1 className="page-title">Send a transfer</h1>
        </div>
        <Link to="/dashboard" className="btn-outline">← Dashboard</Link>
      </div>

      {error && <div className="error">{error}</div>}
      {result && (
        <div className={`notice ${result.status === 'completed' ? 'success' : ''}`}>
          Transfer #{result.id} — status: {result.status}.
          {result.to_amount_cents != null && result.to_currency && (
            <>
              {' '}Sent {formatMoney(result.amount_cents, result.currency || fromCurrency)} →
              recipient received {formatMoney(result.to_amount_cents, result.to_currency)}
              {result.fx_rate != null && ` (rate ${result.fx_rate.toFixed(4)})`}.
            </>
          )}
          <div style={{ marginTop: 12 }}>
            <button className="btn" onClick={() => navigate('/dashboard')}>
              Back to dashboard
            </button>
          </div>
        </div>
      )}

      <div className="transfer-layout">
        <form className="card" onSubmit={onSubmit}>
          <div className="field">
            <label htmlFor="from_account_id">From account</label>
            <select id="from_account_id" name="from_account_id" value={form.from_account_id} onChange={onChange} required>
              {accts.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.account_type} · {a.account_number} · {a.currency} ({formatMoney(a.balance_cents, a.currency)})
                </option>
              ))}
            </select>
            <p className="hint">Sends in {fromCurrency}, this account's currency.</p>
          </div>

          <div className="field">
            <label htmlFor="to_account_id">To account id</label>
            <input
              id="to_account_id"
              name="to_account_id"
              type="number"
              value={form.to_account_id}
              onChange={onChange}
              placeholder="e.g. 5"
              required
            />
          </div>

          <div className="field">
            <label htmlFor="amount">Amount ({fromCurrency})</label>
            <input
              id="amount"
              name="amount"
              type="number"
              step="0.01"
              value={form.amount}
              onChange={onChange}
              placeholder="0.00"
              required
            />
          </div>

          <div className="field">
            <label htmlFor="toCurrency">Recipient currency (for preview)</label>
            <select
              id="toCurrency"
              value={effectiveToCcy}
              onChange={(e) => setToCurrency(e.target.value)}
              disabled={!!destOwn}
            >
              {['USD', 'EUR', 'GBP', 'JPY', 'KES'].map((c) => (
                <option key={c} value={c}>{c}</option>
              ))}
            </select>
            <p className="hint">
              {destOwn
                ? "Detected from the recipient account (one of yours)."
                : 'Preview only — the server uses the real recipient account currency on execution.'}
            </p>
          </div>

          <div className="field">
            <label htmlFor="memo">Memo</label>
            <textarea id="memo" name="memo" rows={3} value={form.memo} onChange={onChange} placeholder="What's this for?" />
          </div>

          <button className="primary" type="submit" disabled={loading}>
            {loading ? 'Sending…' : 'Send transfer'}
          </button>
        </form>

        <aside className="fx-preview">
          <h3>Transfer preview</h3>
          <p className="subtitle" style={{ margin: '2px 0 6px' }}>Live estimate</p>
          <div className="fx-row">
            <span className="fx-label">You send</span>
            <span className="fx-amount">{formatMoney(amountCents, fromCurrency)}</span>
          </div>
          <div className="fx-arrow">↓</div>
          <div className="fx-row">
            <span className="fx-label">Recipient gets</span>
            <span className="fx-amount receive">{formatMoney(preview.cents, effectiveToCcy)}</span>
          </div>
          <p className="fx-rate">
            1 {fromCurrency} = {preview.rate.toFixed(4)} {effectiveToCcy}
          </p>
        </aside>
      </div>
    </Layout>
  )
}
