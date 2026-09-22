import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { auth } from '../api'

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
    <div className="page">
      <form className="card" onSubmit={onSubmit}>
        <p className="brand">NimbusBank</p>
        <h1 className="title">Open an account</h1>
        {error && <div className="error">{error}</div>}
        <div className="field">
          <label htmlFor="full_name">Full name</label>
          <input id="full_name" name="full_name" value={form.full_name} onChange={onChange} required />
        </div>
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
            autoComplete="new-password"
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
            value={form.ssn_last4}
            onChange={onChange}
            required
          />
        </div>
        <button className="primary" type="submit" disabled={loading}>
          {loading ? 'Creating account…' : 'Create account'}
        </button>
        <p className="alt-link">
          Already have an account? <Link to="/login">Sign in</Link>
        </p>
      </form>
    </div>
  )
}
