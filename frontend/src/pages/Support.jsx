import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { support } from '../api'
import Layout from '../components/Layout'

export default function Support() {
  const [tickets, setTickets] = useState([])
  const [selected, setSelected] = useState(null) // { ...ticket, messages }
  const [subject, setSubject] = useState('')
  const [body, setBody] = useState('')
  const [reply, setReply] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const navigate = useNavigate()

  const loadList = () => {
    support
      .listMine()
      .then(setTickets)
      .catch((err) => setError(err.message))
  }

  useEffect(() => {
    if (!localStorage.getItem('nimbus_access_token')) {
      navigate('/login')
      return
    }
    loadList()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const openTicket = async (id) => {
    setError('')
    try {
      const t = await support.getTicket(id)
      setSelected(t)
    } catch (err) {
      setError(err.message)
    }
  }

  const onCreate = async (e) => {
    e.preventDefault()
    setError('')
    setBusy(true)
    try {
      const t = await support.createTicket({ subject, body })
      setSubject('')
      setBody('')
      setSelected(t)
      loadList()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  const onReply = async (e) => {
    e.preventDefault()
    if (!selected) return
    setError('')
    setBusy(true)
    try {
      await support.postMessage(selected.id, { sender: 'customer', body: reply })
      setReply('')
      openTicket(selected.id)
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <Layout>
      <div className="page-head">
        <div>
          <p className="subtitle" style={{ margin: 0 }}>Help</p>
          <h1 className="page-title">Support</h1>
        </div>
        <Link to="/support/agent" className="btn-outline">Agent console →</Link>
      </div>

      {error && <div className="error">{error}</div>}

      <div className="detail-grid" style={{ marginTop: 4 }}>
        <div className="card">
          <h3 style={{ marginTop: 0, fontSize: 18 }}>Open a new ticket</h3>
          <form onSubmit={onCreate}>
            <div className="field">
              <label htmlFor="subject">Subject</label>
              <input
                id="subject"
                value={subject}
                onChange={(e) => setSubject(e.target.value)}
                placeholder="What do you need help with?"
                required
              />
            </div>
            <div className="field">
              <label htmlFor="body">Message</label>
              <textarea
                id="body"
                rows={4}
                value={body}
                onChange={(e) => setBody(e.target.value)}
                placeholder="Describe your issue…"
                required
              />
            </div>
            <button className="primary" type="submit" disabled={busy}>
              {busy ? 'Sending…' : 'Create ticket'}
            </button>
          </form>

          <p className="section-label" style={{ fontSize: 16, marginBottom: 12 }}>Your tickets</p>
          {tickets.length === 0 && <p className="subtitle">No tickets yet.</p>}
          {tickets.map((t) => (
            <div key={t.id} className="kv">
              <span className="k">
                <button className="alt-link" style={{ margin: 0, background: 'none', border: 'none', cursor: 'pointer', padding: 0 }} onClick={() => openTicket(t.id)}>
                  #{t.id} · {t.subject}
                </button>
              </span>
              <span className="v">
                <span className={`status-badge ${t.status === 'open' ? 'pending' : ''}`}>{t.status}</span>
              </span>
            </div>
          ))}
        </div>

        <div className="card">
          {!selected && <p className="subtitle" style={{ margin: 0 }}>Select a ticket to view the conversation.</p>}
          {selected && (
            <>
              <h3 style={{ marginTop: 0, fontSize: 18 }}>#{selected.id} · {selected.subject}</h3>
              <div style={{ marginBottom: 16 }}>
                {selected.messages.map((m) => (
                  <div key={m.id} className="kv" style={{ display: 'block' }}>
                    <div className="txn-sub" style={{ textTransform: 'capitalize' }}>{m.sender}</div>
                    {/* Customer view: message bodies are rendered as PLAIN TEXT
                        (safe interpolation). The raw-HTML sink lives only in the
                        agent console — see AgentConsole.jsx. */}
                    <div>{m.body}</div>
                  </div>
                ))}
              </div>
              <form onSubmit={onReply}>
                <div className="field">
                  <label htmlFor="reply">Reply</label>
                  <textarea
                    id="reply"
                    rows={3}
                    value={reply}
                    onChange={(e) => setReply(e.target.value)}
                    placeholder="Add a reply…"
                    required
                  />
                </div>
                <button className="primary" type="submit" disabled={busy}>
                  {busy ? 'Sending…' : 'Send reply'}
                </button>
              </form>
            </>
          )}
        </div>
      </div>
    </Layout>
  )
}
