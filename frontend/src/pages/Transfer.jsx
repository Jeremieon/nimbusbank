import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { transfers } from '../api'

export default function Transfer() {
  const [form, setForm] = useState({ from_account_id: '', to_account_id: '', amount_cents: '', memo: '' })
  const [error, setError] = useState('')
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const navigate = useNavigate()

  const onChange = (e) => setForm({ ...form, [e.target.name]: e.target.value })

  const onSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      const payload = {
        from_account_id: Number(form.from_account_id),
        to_account_id: Number(form.to_account_id),
        amount_cents: Number(form.amount_cents),
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
    <div className="transfer-page">
      <div className="detail-header">
        <p className="brand">NimbusBank</p>
        <Link to="/dashboard" className="secondary-link">
          Back to dashboard
        </Link>
      </div>
      <h1 className="title">Send a transfer</h1>
      {error && <div className="error">{error}</div>}
      {result && (
        <div className="notice">
          Transfer #{result.id} recorded — status: {result.status}
        </div>
      )}
      <form onSubmit={onSubmit}>
        <div className="field">
          <label htmlFor="from_account_id">From account id</label>
          <input
            id="from_account_id"
            name="from_account_id"
            type="number"
            value={form.from_account_id}
            onChange={onChange}
            required
          />
        </div>
        <div className="field">
          <label htmlFor="to_account_id">To account id</label>
          <input
            id="to_account_id"
            name="to_account_id"
            type="number"
            value={form.to_account_id}
            onChange={onChange}
            required
          />
        </div>
        <div className="field">
          <label htmlFor="amount_cents">Amount (cents)</label>
          <input
            id="amount_cents"
            name="amount_cents"
            type="number"
            value={form.amount_cents}
            onChange={onChange}
            required
          />
        </div>
        <div className="field">
          <label htmlFor="memo">Memo</label>
          <textarea id="memo" name="memo" rows={3} value={form.memo} onChange={onChange} />
        </div>
        <button className="primary" type="submit" disabled={loading}>
          {loading ? 'Sending…' : 'Send transfer'}
        </button>
      </form>
    </div>
  )
}
