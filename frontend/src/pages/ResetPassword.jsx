import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { auth } from '../api'

function Hero() {
  return (
    <section className="hero">
      <span className="hero-brand">
        <span aria-hidden="true">◈</span> NimbusBank
      </span>
      <h1 className="hero-title">Choose a new password</h1>
      <p className="hero-sub">
        Paste the reset code from the previous step and set the password you'll use to sign in.
      </p>
      <div className="hero-badges">
        <span className="hero-badge">One code, one reset</span>
        <span className="hero-badge">Codes expire in 15 minutes</span>
      </div>
    </section>
  )
}

export default function ResetPassword() {
  const [form, setForm] = useState({ token: '', new_password: '' })
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [loading, setLoading] = useState(false)
  const navigate = useNavigate()

  const onChange = (e) => setForm({ ...form, [e.target.name]: e.target.value })

  const onSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setMessage('')
    setLoading(true)
    try {
      await auth.resetPassword({ token: form.token, new_password: form.new_password })
      setMessage('Password reset. Redirecting to sign in…')
      setTimeout(() => navigate('/login'), 1200)
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
          <h1>Reset password</h1>
          <p className="lead">Enter your reset code and a new password.</p>
          {message && <div className="notice success">{message}</div>}
          {error && <div className="error">{error}</div>}
          <div className="field">
            <label htmlFor="token">Reset code</label>
            <input
              id="token"
              name="token"
              className="otp-input"
              inputMode="numeric"
              maxLength={6}
              placeholder="000000"
              value={form.token}
              onChange={onChange}
              required
            />
          </div>
          <div className="field">
            <label htmlFor="new_password">New password</label>
            <input
              id="new_password"
              name="new_password"
              type="password"
              autoComplete="new-password"
              placeholder="At least 8 characters"
              value={form.new_password}
              onChange={onChange}
              required
              minLength={8}
            />
          </div>
          <button className="primary" type="submit" disabled={loading}>
            {loading ? 'Resetting…' : 'Reset password'}
          </button>
          <p className="alt-link">
            Need a code? <Link to="/forgot">Request a reset</Link>
          </p>
        </form>
      </div>
    </div>
  )
}
