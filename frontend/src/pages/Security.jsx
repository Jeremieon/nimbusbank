import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { totp } from '../api'
import Layout from '../components/Layout'

export default function Security() {
  const [enabled, setEnabled] = useState(false)
  const [loading, setLoading] = useState(true)
  const [enroll, setEnroll] = useState(null) // { secret, otpauth_uri, qr_png_base64 }
  const [code, setCode] = useState('')
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState(false)
  const navigate = useNavigate()

  useEffect(() => {
    if (!localStorage.getItem('nimbus_access_token')) {
      navigate('/login')
      return
    }
    totp
      .status()
      .then((s) => setEnabled(s.totp_enabled))
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }, [navigate])

  const onEnroll = async () => {
    setError('')
    setMessage('')
    setBusy(true)
    try {
      const res = await totp.enroll()
      setEnroll(res)
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  const onConfirm = async (e) => {
    e.preventDefault()
    setError('')
    setMessage('')
    setBusy(true)
    try {
      await totp.confirm(code)
      setEnabled(true)
      setEnroll(null)
      setCode('')
      setMessage('Authenticator app enabled. You will use a 6-digit code at your next login.')
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  const onDisable = async () => {
    setError('')
    setMessage('')
    setBusy(true)
    try {
      await totp.disable()
      setEnabled(false)
      setEnroll(null)
      setMessage('Authenticator app disabled. Login now uses the standard code again.')
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  if (loading) return null

  return (
    <Layout>
      <p className="subtitle" style={{ margin: 0 }}>Account</p>
      <h1 className="greeting">Security</h1>

      {error && <div className="error">{error}</div>}
      {message && <div className="notice success">{message}</div>}

      <div className="security-grid" style={{ marginTop: 20 }}>
        <div className="card">
          <h3 style={{ marginTop: 0, fontSize: 18 }}>Authenticator app (TOTP)</h3>
          <div className="status-row">
            <span className={`dot ${enabled ? 'on' : ''}`} />
            <span>{enabled ? 'Enabled' : 'Not enabled'}</span>
          </div>
          <p className="subtitle">
            Add a time-based one-time code from an app like Google Authenticator or 1Password as a
            real second factor, alongside the standard login code.
          </p>

          {!enabled && !enroll && (
            <button className="primary" onClick={onEnroll} disabled={busy}>
              {busy ? 'Preparing…' : 'Enable authenticator app'}
            </button>
          )}

          {enabled && (
            <button className="btn-outline btn-danger" onClick={onDisable} disabled={busy}>
              {busy ? 'Working…' : 'Disable authenticator app'}
            </button>
          )}
        </div>

        {enroll && !enabled && (
          <div className="card">
            <h3 style={{ marginTop: 0, fontSize: 18 }}>Scan to enroll</h3>
            <p className="subtitle">
              Scan this QR code with your authenticator app, then enter the 6-digit code it shows.
            </p>
            <div className="qr-wrap">
              <img src={`data:image/png;base64,${enroll.qr_png_base64}`} alt="TOTP QR code" />
            </div>
            <p className="hint" style={{ marginBottom: 6 }}>Or enter this secret manually:</p>
            <div className="secret-box">{enroll.secret}</div>
            <form onSubmit={onConfirm}>
              <div className="field">
                <label htmlFor="code">6-digit code</label>
                <input
                  id="code"
                  className="otp-input"
                  inputMode="numeric"
                  maxLength={6}
                  value={code}
                  onChange={(e) => setCode(e.target.value)}
                  placeholder="000000"
                  required
                />
              </div>
              <button className="primary" type="submit" disabled={busy}>
                {busy ? 'Confirming…' : 'Confirm & enable'}
              </button>
            </form>
          </div>
        )}
      </div>
    </Layout>
  )
}
