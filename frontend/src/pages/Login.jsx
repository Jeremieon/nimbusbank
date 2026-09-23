import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { auth } from '../api'

function Hero() {
  return (
    <section className="hero">
      <span className="hero-brand">
        <span aria-hidden="true">◈</span> NimbusBank
      </span>
      <h1 className="hero-title">Banking that moves at your speed</h1>
      <p className="hero-sub">
        Multi-currency accounts, instant transfers, and a security setup you control — all in
        one clean place.
      </p>
      <div className="hero-badges">
        <span className="hero-badge">Send in USD, EUR, GBP, JPY</span>
        <span className="hero-badge">Real-time FX preview</span>
        <span className="hero-badge">Authenticator app support</span>
      </div>
    </section>
  )
}

export default function Login() {
  const [step, setStep] = useState('credentials')
  const [form, setForm] = useState({ email: '', password: '' })
  const [userId, setUserId] = useState('')
  const [otp, setOtp] = useState('')
  const [otpHint, setOtpHint] = useState('')
  const [totpCode, setTotpCode] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const navigate = useNavigate()

  const onChange = (e) => setForm({ ...form, [e.target.name]: e.target.value })

  const onSubmitCredentials = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      const res = await auth.login(form)
      setUserId(res.user_id)
      if (res.totp_enabled) {
        // User enrolled a real authenticator app — collect a 6-digit code.
        setStep('totp')
      } else {
        // LAB-ONLY: the weak OTP is returned in this response body (see
        // auth-service's schemas.py) so you can complete the flow without a
        // mail server. Prefill it for convenience.
        setOtpHint(res.otp)
        setOtp(res.otp)
        setStep('otp')
      }
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const onSubmitOtp = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      const res = await auth.verifyOtp({ user_id: userId, otp })
      localStorage.setItem('nimbus_access_token', res.access_token)
      navigate('/dashboard')
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const onSubmitTotp = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      const res = await auth.verifyTotp({ user_id: userId, code: totpCode })
      localStorage.setItem('nimbus_access_token', res.access_token)
      navigate('/dashboard')
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
        {step === 'credentials' && (
          <form className="auth-card" onSubmit={onSubmitCredentials}>
            <h1>Sign in</h1>
            <p className="lead">Welcome back. Enter your details to continue.</p>
            {error && <div className="error">{error}</div>}
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
                autoComplete="current-password"
                placeholder="••••••••"
                value={form.password}
                onChange={onChange}
                required
              />
            </div>
            <button className="primary" type="submit" disabled={loading}>
              {loading ? 'Signing in…' : 'Sign in'}
            </button>
            <p className="alt-link">
              New to NimbusBank? <Link to="/register">Create an account</Link>
            </p>
          </form>
        )}

        {step === 'otp' && (
          <form className="auth-card" onSubmit={onSubmitOtp}>
            <h1>Enter your code</h1>
            <p className="lead">We sent a 4-digit code to your device.</p>
            {otpHint && (
              <div className="lab-hint">
                Lab hint: OTP is {otpHint} (also returned by /login for convenience)
              </div>
            )}
            {error && <div className="error">{error}</div>}
            <div className="field">
              <label htmlFor="otp">Verification code</label>
              <input
                id="otp"
                name="otp"
                className="otp-input"
                inputMode="numeric"
                maxLength={4}
                value={otp}
                onChange={(e) => setOtp(e.target.value)}
                required
              />
            </div>
            <button className="primary" type="submit" disabled={loading}>
              {loading ? 'Verifying…' : 'Verify'}
            </button>
          </form>
        )}

        {step === 'totp' && (
          <form className="auth-card" onSubmit={onSubmitTotp}>
            <h1>Authenticator code</h1>
            <p className="lead">Open your authenticator app and enter the 6-digit code.</p>
            {error && <div className="error">{error}</div>}
            <div className="field">
              <label htmlFor="totp">6-digit code</label>
              <input
                id="totp"
                name="totp"
                className="otp-input"
                inputMode="numeric"
                maxLength={6}
                value={totpCode}
                onChange={(e) => setTotpCode(e.target.value)}
                placeholder="000000"
                required
              />
            </div>
            <button className="primary" type="submit" disabled={loading}>
              {loading ? 'Verifying…' : 'Verify'}
            </button>
          </form>
        )}
      </div>
    </div>
  )
}
