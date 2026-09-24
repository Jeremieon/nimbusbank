import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { auth } from '../api'
import Layout from '../components/Layout'

function formatDate(iso) {
  if (!iso) return '—'
  try {
    return new Date(iso).toLocaleDateString(undefined, { year: 'numeric', month: 'long', day: 'numeric' })
  } catch {
    return iso
  }
}

export default function Profile() {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  // Profile edit form
  const [profileForm, setProfileForm] = useState({ full_name: '', email: '', ssn_last4: '', role: '' })
  const [profileMsg, setProfileMsg] = useState('')
  const [profileErr, setProfileErr] = useState('')
  const [savingProfile, setSavingProfile] = useState(false)

  // Change-password form
  const [pwForm, setPwForm] = useState({ current_password: '', new_password: '' })
  const [pwMsg, setPwMsg] = useState('')
  const [pwErr, setPwErr] = useState('')
  const [savingPw, setSavingPw] = useState(false)

  const navigate = useNavigate()

  useEffect(() => {
    if (!localStorage.getItem('nimbus_access_token')) {
      navigate('/login')
      return
    }
    auth
      .me()
      .then((u) => {
        setUser(u)
        setProfileForm({
          full_name: u.full_name || '',
          email: u.email || '',
          ssn_last4: '',
          role: u.role || '',
        })
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }, [navigate])

  const onProfileChange = (e) => setProfileForm({ ...profileForm, [e.target.name]: e.target.value })
  const onPwChange = (e) => setPwForm({ ...pwForm, [e.target.name]: e.target.value })

  const onSaveProfile = async (e) => {
    e.preventDefault()
    setProfileErr('')
    setProfileMsg('')
    setSavingProfile(true)
    try {
      // Only send fields the user actually filled in. NOTE: `role` is sent
      // straight through — a real bank UI would never let a customer set their
      // own role, and neither would a hardened API. It's here on purpose so the
      // PATCH /me mass-assignment / privilege-escalation gap is exercisable
      // right from the UI (see auth-service main.py update_me).
      const payload = {}
      if (profileForm.full_name) payload.full_name = profileForm.full_name
      if (profileForm.email) payload.email = profileForm.email
      if (profileForm.ssn_last4) payload.ssn_last4 = profileForm.ssn_last4
      if (profileForm.role) payload.role = profileForm.role
      const updated = await auth.updateProfile(payload)
      setUser(updated)
      setProfileForm((f) => ({ ...f, role: updated.role, ssn_last4: '' }))
      setProfileMsg(`Profile saved. Your role is now "${updated.role}".`)
    } catch (err) {
      setProfileErr(err.message)
    } finally {
      setSavingProfile(false)
    }
  }

  const onChangePassword = async (e) => {
    e.preventDefault()
    setPwErr('')
    setPwMsg('')
    setSavingPw(true)
    try {
      await auth.changePassword({
        current_password: pwForm.current_password,
        new_password: pwForm.new_password,
      })
      setPwForm({ current_password: '', new_password: '' })
      setPwMsg('Password changed. (Note: the current password is not actually verified — see the lab notes.)')
    } catch (err) {
      setPwErr(err.message)
    } finally {
      setSavingPw(false)
    }
  }

  if (loading) return null

  return (
    <Layout>
      <p className="subtitle" style={{ margin: 0 }}>Account</p>
      <h1 className="greeting">Profile</h1>

      {error && <div className="error">{error}</div>}

      <div className="detail-grid" style={{ marginTop: 20 }}>
        <div className="card">
          <h3 style={{ marginTop: 0, fontSize: 18 }}>Your details</h3>
          {user && (
            <>
              <div className="kv">
                <span className="k">Name</span>
                <span className="v">{user.full_name}</span>
              </div>
              <div className="kv">
                <span className="k">Email</span>
                <span className="v">{user.email}</span>
              </div>
              <div className="kv">
                <span className="k">Role</span>
                <span className="v">
                  <span className={`status-badge ${user.role === 'admin' ? 'pending' : ''}`}>{user.role}</span>
                </span>
              </div>
              <div className="kv">
                <span className="k">Verified</span>
                <span className="v">{user.is_verified ? 'Yes' : 'No'}</span>
              </div>
              <div className="kv">
                <span className="k">Member since</span>
                <span className="v">{formatDate(user.created_at)}</span>
              </div>
            </>
          )}
        </div>

        <div className="security-grid">
          <div className="card">
            <h3 style={{ marginTop: 0, fontSize: 18 }}>Edit profile</h3>
            {profileMsg && <div className="notice success">{profileMsg}</div>}
            {profileErr && <div className="error">{profileErr}</div>}
            <form onSubmit={onSaveProfile}>
              <div className="field">
                <label htmlFor="full_name">Full name</label>
                <input id="full_name" name="full_name" value={profileForm.full_name} onChange={onProfileChange} />
              </div>
              <div className="field">
                <label htmlFor="email">Email</label>
                <input id="email" name="email" type="email" value={profileForm.email} onChange={onProfileChange} />
              </div>
              <div className="field">
                <label htmlFor="ssn_last4">SSN (last 4)</label>
                <input
                  id="ssn_last4"
                  name="ssn_last4"
                  maxLength={4}
                  inputMode="numeric"
                  placeholder="leave blank to keep"
                  value={profileForm.ssn_last4}
                  onChange={onProfileChange}
                />
              </div>
              {/* INTENTIONAL: a self-editable Role field. No real bank UI would
                  expose this — it's here so the PATCH /me mass-assignment
                  privilege escalation can be driven straight from the UI. */}
              <div className="field">
                <label htmlFor="role">Role (intentionally editable — lab)</label>
                <select id="role" name="role" value={profileForm.role} onChange={onProfileChange}>
                  <option value="customer">customer</option>
                  <option value="admin">admin</option>
                </select>
                <p className="hint">
                  A normal bank would never let you set your own role. This escalates you via the
                  mass-assignment gap in PATCH /me.
                </p>
              </div>
              <button className="primary" type="submit" disabled={savingProfile}>
                {savingProfile ? 'Saving…' : 'Save profile'}
              </button>
            </form>
          </div>

          <div className="card">
            <h3 style={{ marginTop: 0, fontSize: 18 }}>Change password</h3>
            {pwMsg && <div className="notice success">{pwMsg}</div>}
            {pwErr && <div className="error">{pwErr}</div>}
            <form onSubmit={onChangePassword}>
              <div className="field">
                <label htmlFor="current_password">Current password</label>
                <input
                  id="current_password"
                  name="current_password"
                  type="password"
                  autoComplete="current-password"
                  value={pwForm.current_password}
                  onChange={onPwChange}
                />
              </div>
              <div className="field">
                <label htmlFor="new_password">New password</label>
                <input
                  id="new_password"
                  name="new_password"
                  type="password"
                  autoComplete="new-password"
                  minLength={8}
                  value={pwForm.new_password}
                  onChange={onPwChange}
                  required
                />
              </div>
              <button className="primary" type="submit" disabled={savingPw}>
                {savingPw ? 'Updating…' : 'Change password'}
              </button>
            </form>
          </div>
        </div>
      </div>
    </Layout>
  )
}
