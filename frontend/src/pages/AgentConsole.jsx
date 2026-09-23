import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { support } from '../api'
import Layout from '../components/Layout'

// Support agent console. Meant to be an internal, staff-only screen — but the
// backing route (/tickets/all) has no role check, so any authenticated
// customer reaches it (BFLA). It also renders customer-submitted message
// bodies as raw HTML: the stored-XSS / formjacking sink for this service.
export default function AgentConsole() {
  const [tickets, setTickets] = useState([])
  const [threads, setThreads] = useState({}) // ticketId -> detail
  const [error, setError] = useState('')
  const navigate = useNavigate()

  useEffect(() => {
    if (!localStorage.getItem('nimbus_access_token')) {
      navigate('/login')
      return
    }
    support
      .listAll()
      .then(async (list) => {
        setTickets(list)
        // Eagerly load every thread so an agent sees all conversations — and
        // so any planted payload renders immediately.
        const details = await Promise.all(list.map((t) => support.getTicket(t.id).catch(() => null)))
        const map = {}
        details.forEach((d) => {
          if (d) map[d.id] = d
        })
        setThreads(map)
      })
      .catch((err) => setError(err.message))
  }, [navigate])

  return (
    <Layout>
      <div className="page-head">
        <div>
          <p className="subtitle" style={{ margin: 0 }}>Staff</p>
          <h1 className="page-title">Agent console</h1>
        </div>
        <Link to="/support" className="btn-outline">← Support</Link>
      </div>

      {error && <div className="error">{error}</div>}

      <p className="subtitle">Every ticket across all customers.</p>

      {tickets.map((t) => (
        <div key={t.id} className="card" style={{ marginBottom: 16 }}>
          <div className="account-card-head" style={{ marginBottom: 8 }}>
            <span className="account-type" style={{ textTransform: 'none' }}>#{t.id} · {t.subject}</span>
            <span className={`status-badge ${t.status === 'open' ? 'pending' : ''}`}>{t.status}</span>
          </div>
          <div className="txn-sub" style={{ marginBottom: 12 }}>Customer {t.user_id}</div>
          {(threads[t.id]?.messages || []).map((m) => (
            <div key={m.id} className="kv" style={{ display: 'block' }}>
              <div className="txn-sub" style={{ textTransform: 'capitalize' }}>{m.sender}</div>
              {/*
                INTENTIONALLY VULNERABLE: the customer-submitted message body is
                rendered as raw HTML via dangerouslySetInnerHTML instead of
                plain text. A stored `<script>` / `<img onerror=...>` payload in
                a ticket message executes right here, in the support agent's
                browser — stored XSS / formjacking (OWASP Top 10 / F5 XC WAF
                category). See support-service's models.py for the matching
                server-side comment; the customer-facing Support.jsx renders the
                same bodies as safe text.
              */}
              <div dangerouslySetInnerHTML={{ __html: m.body }} />
            </div>
          ))}
        </div>
      ))}
      {tickets.length === 0 && <p className="subtitle">No tickets found.</p>}
    </Layout>
  )
}
