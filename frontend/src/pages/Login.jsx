import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { auth } from '../api'

export default function Login() {
  const [step, setStep] = useState('credentials')
  const [form, setForm] = useState({ email: '', password: '' })
  const [userId, setUserId] = useState('')
  const [otp, setOtp] = useState('')
  const [otpHint, setOtpHint] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const navigate = useNavigate()

  const onChange = (e) => setForm({ ...form, [e.target.name]: e.target.value })

  const onSubmitCredentials = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      // LAB-ONLY: the OTP is returned in this response body (see auth-service's
      // schemas.py) so you can complete the flow without a mail server.
      const res = await auth.login(form)
      setUserId(res.user_id)
      setOtpHint(res.otp)
      setOtp(res.otp)
      setStep('otp')
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

  if (step === 'otp') {
    return (
      <div className="page">
        <form className="card" onSubmit={onSubmitOtp}>
          <p className="brand">NimbusBank</p>
          <h1 className="title">Enter your code</h1>
          <p className="subtitle">We sent a 4-digit code to your device.</p>
          {otpHint && (
            <div className="notice">Lab hint: OTP is {otpHint} (also returned by /login for convenience)</div>
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
      </div>
    )
  }

  return (
    <div className="page">
      <form className="card" onSubmit={onSubmitCredentials}>
        <p className="brand">NimbusBank</p>
        <h1 className="title">Sign in</h1>
        {error && <div className="error">{error}</div>}
        <div className="field">
          <label htmlFor="email">Email</label>
          <input
            id="email"
            name="email"
            type="email"
            autoComplete="email"
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
            value={form.password}
            onChange={onChange}
            required
          />
        </div>
        <button className="primary" type="submit" disabled={loading}>
          {loading ? 'Signing in…' : 'Sign in'}
        </button>
        <p className="alt-link">
          No account yet? <Link to="/register">Create one</Link>
        </p>
      </form>
    </div>
  )
}
