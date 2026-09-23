import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { accounts as accountsApi, cards as cardsApi } from '../api'
import Layout from '../components/Layout'
import { formatMoney } from '../money'

const CARD_TYPES = [
  { value: 'virtual', label: 'Virtual' },
  { value: 'physical', label: 'Physical' },
]

function maskedPan(last4) {
  return `•••• •••• •••• ${last4 || '••••'}`
}

export default function Cards() {
  const [accts, setAccts] = useState([])
  const [myCards, setMyCards] = useState([])
  const [revealed, setRevealed] = useState({}) // cardId -> full detail (PAN + CVV)
  const [form, setForm] = useState({ account_id: '', card_type: 'virtual', spend_limit: '' })
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState(false)
  const navigate = useNavigate()

  const loadCards = () => {
    cardsApi
      .listMine()
      .then(setMyCards)
      .catch((err) => setError(err.message))
  }

  useEffect(() => {
    if (!localStorage.getItem('nimbus_access_token')) {
      navigate('/login')
      return
    }
    accountsApi
      .list()
      .then((list) => {
        setAccts(list)
        setForm((f) => ({ ...f, account_id: list[0] ? String(list[0].id) : '' }))
      })
      .catch((err) => setError(err.message))
    loadCards()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const onChange = (e) => setForm({ ...form, [e.target.name]: e.target.value })

  const onIssue = async (e) => {
    e.preventDefault()
    setError('')
    setMessage('')
    setBusy(true)
    try {
      const payload = {
        account_id: Number(form.account_id),
        card_type: form.card_type,
      }
      if (form.spend_limit !== '') {
        payload.spend_limit_cents = Math.round(Number(form.spend_limit) * 100)
      }
      const res = await cardsApi.issue(payload)
      setMessage(`Issued a ${res.card_type} card ending ${res.last4} on account ${res.account_id}.`)
      setForm((f) => ({ ...f, spend_limit: '' }))
      loadCards()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  const toggleFreeze = async (card) => {
    setError('')
    try {
      const updated = card.status === 'frozen' ? await cardsApi.unfreeze(card.id) : await cardsApi.freeze(card.id)
      setMyCards((list) => list.map((c) => (c.id === card.id ? { ...c, status: updated.status } : c)))
    } catch (err) {
      setError(err.message)
    }
  }

  const reveal = async (card) => {
    setError('')
    try {
      // GET /cards/{id} returns the FULL PAN + CVV — the excessive-data-exposure
      // sink. Fine to display in this lab; that's the whole point.
      const full = await cardsApi.get(card.id)
      setRevealed((r) => ({ ...r, [card.id]: full }))
    } catch (err) {
      setError(err.message)
    }
  }

  return (
    <Layout>
      <div className="page-head">
        <div>
          <p className="subtitle" style={{ margin: 0 }}>Wallet</p>
          <h1 className="page-title">Your cards</h1>
        </div>
        <Link to="/dashboard" className="btn-outline">← Dashboard</Link>
      </div>

      {error && <div className="error">{error}</div>}
      {message && <div className="notice success">{message}</div>}

      <div className="detail-grid" style={{ marginTop: 4 }}>
        <div>
          <p className="section-label" style={{ marginTop: 0 }}>Issued cards</p>
          <div className="account-grid">
            {myCards.map((c) => (
              <div key={c.id} className="account-card">
                <div className="account-card-head">
                  <span className="account-type">{c.card_type} card</span>
                  <span className={`status-badge ${c.status === 'frozen' ? 'failed' : ''}`}>{c.status}</span>
                </div>
                <div className="account-number">{revealed[c.id] ? revealed[c.id].card_number.replace(/(.{4})/g, '$1 ').trim() : maskedPan(c.last4)}</div>
                <div className="txn-sub" style={{ marginBottom: 10 }}>
                  Exp {c.expiry} · Funds acct {c.account_id}
                  {revealed[c.id] && <> · CVV {revealed[c.id].cvv}</>}
                </div>
                <div className="account-balance" style={{ fontSize: 20 }}>
                  {formatMoney(c.spend_limit_cents, 'USD')}
                  <span className="txn-sub" style={{ marginLeft: 6 }}>limit</span>
                </div>
                <div className="account-actions">
                  <button className="btn-outline" onClick={() => toggleFreeze(c)}>
                    {c.status === 'frozen' ? 'Unfreeze' : 'Freeze'}
                  </button>
                  <button className="btn" onClick={() => reveal(c)}>Reveal details</button>
                </div>
              </div>
            ))}
            {myCards.length === 0 && <p className="subtitle">No cards issued yet.</p>}
          </div>
        </div>

        <div className="card">
          <h3 style={{ marginTop: 0, fontSize: 18 }}>Issue a card</h3>
          <p className="subtitle">Spin up a new card funded by one of your accounts.</p>
          <form onSubmit={onIssue}>
            <div className="field">
              <label htmlFor="account_id">Funding account</label>
              <select id="account_id" name="account_id" value={form.account_id} onChange={onChange} required>
                {accts.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.account_type} · {a.account_number} · {a.currency}
                  </option>
                ))}
              </select>
            </div>
            <div className="field">
              <label htmlFor="card_type">Card type</label>
              <select id="card_type" name="card_type" value={form.card_type} onChange={onChange}>
                {CARD_TYPES.map((t) => (
                  <option key={t.value} value={t.value}>{t.label}</option>
                ))}
              </select>
            </div>
            <div className="field">
              <label htmlFor="spend_limit">Spend limit (optional)</label>
              <input
                id="spend_limit"
                name="spend_limit"
                type="number"
                step="0.01"
                value={form.spend_limit}
                onChange={onChange}
                placeholder="1000.00"
              />
              <p className="hint">Defaults to $1,000.00 if left blank.</p>
            </div>
            <button className="primary" type="submit" disabled={busy}>
              {busy ? 'Issuing…' : 'Issue card'}
            </button>
          </form>
        </div>
      </div>
    </Layout>
  )
}
