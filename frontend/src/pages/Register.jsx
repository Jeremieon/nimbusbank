import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { auth } from '../api'

function Hero() {
  return (
    <section className="hero">
      <span className="hero-brand">
        <span aria-hidden="true">◈</span> NimbusBank
      </span>
      <h1 className="hero-title">Open an account in minutes</h1>
      <p className="hero-sub">
        Join thousands moving money across currencies with a bank built for speed and clarity.
      </p>
      <div className="hero-badges">
        <span className="hero-badge">No monthly fees</span>
        <span className="hero-badge">Multi-currency by default</span>
        <span className="hero-badge">You control your security</span>
      </div>
    </section>
  )
}

export default function Register() {
  const [form, setForm] = useState({ email: '', full_name: '', password: '', ssn_last4: '' })
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const navigate = useNavigate()

  const onChange = (e) => setForm({ ...form, [e.target.name]: e.target.value })

  const onSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      await auth.register(form)
      navigate('/login')
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="auth-page">
      <Hero />
      <div className="auth-panel">
        <form className="auth-card" onSubmit={onSubmit}>
          <h1>Create your account</h1>
          <p className="lead">It only takes a moment to get started.</p>
          {error && <div className="error">{error}</div>}
          <div className="field">
            <label htmlFor="full_name">Full name</label>
            <input id="full_name" name="full_name" value={form.full_name} onChange={onChange} placeholder="Jane Doe" required />
          </div>
          <div className="field">
            <label htmlFor="email">Email</label>
            <input
              id="email"
              name="email"
              type="email"
              autoComplete="email"
              placeholder="you@nimbusbank.io"
              value={form.email}
              onChange={onChange}
              required
            />
          </div>
          <div className="field">
            <label htmlFor="password">Password</label>
            <input
              id="password"
              name="password"
              type="password"
              autoComplete="new-password"
              placeholder="At least 8 characters"
              value={form.password}
              onChange={onChange}
              required
              minLength={8}
            />
          </div>
          <div className="field">
            <label htmlFor="ssn_last4">SSN (last 4 digits)</label>
            <input
              id="ssn_last4"
              name="ssn_last4"
              maxLength={4}
              inputMode="numeric"
              placeholder="1234"
              value={form.ssn_last4}
              onChange={onChange}
              required
            />
            <p className="hint">Test data only — never enter a real SSN into this lab.</p>
          </div>
          <button className="primary" type="submit" disabled={loading}>
            {loading ? 'Creating account…' : 'Create account'}
          </button>
          <p className="alt-link">
            Already have an account? <Link to="/login">Sign in</Link>
          </p>
        </form>
      </div>
    </div>
  )
}
