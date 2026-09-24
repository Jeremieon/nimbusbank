import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { auth } from '../api'

function Hero() {
  return (
    <section className="hero">
      <span className="hero-brand">
        <span aria-hidden="true">◈</span> NimbusBank
      </span>
      <h1 className="hero-title">Reset your password</h1>
      <p className="hero-sub">
        Tell us the email on your account and we'll issue a reset code. Enter it on the next
        step to choose a new password.
      </p>
      <div className="hero-badges">
        <span className="hero-badge">Back in minutes</span>
        <span className="hero-badge">No support call needed</span>
      </div>
    </section>
  )
}

export default function ForgotPassword() {
  const [email, setEmail] = useState('')
  const [tokenHint, setTokenHint] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const navigate = useNavigate()

  const onSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      const res = await auth.forgotPassword({ email })
      // LAB-ONLY: the reset token comes straight back in the response body
      // (like the login OTP) so you can finish the flow without a mail server.
      setTokenHint(res.reset_token)
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
          <h1>Forgot password</h1>
          <p className="lead">Enter your account email to get a reset code.</p>
          {tokenHint && (
            <div className="lab-hint">
              Lab hint: reset token is {tokenHint} (also returned by /password/forgot for convenience)
            </div>
          )}
          {error && <div className="error">{error}</div>}
          <div className="field">
            <label htmlFor="email">Email</label>
            <input
              id="email"
              name="email"
              type="email"
              autoComplete="email"
              placeholder="you@nimbusbank.io"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </div>
          <button className="primary" type="submit" disabled={loading}>
            {loading ? 'Sending…' : 'Send reset code'}
          </button>
          {tokenHint ? (
            <p className="alt-link">
              Got your code? <Link to="/reset">Continue to reset your password</Link>
            </p>
          ) : (
            <p className="alt-link">
              Remembered it? <Link to="/login">Back to sign in</Link>
            </p>
          )}
        </form>
      </div>
    </div>
  )
}
