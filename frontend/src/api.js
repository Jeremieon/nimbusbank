const BASE = '/api'

function authHeader() {
  const token = localStorage.getItem('nimbus_access_token')
  return token ? { Authorization: `Bearer ${token}` } : {}
}

async function request(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    credentials: 'include',
    headers: { 'Content-Type': 'application/json', ...authHeader(), ...(options.headers || {}) },
    ...options,
  })
  const contentType = res.headers.get('content-type') || ''
  const data = contentType.includes('application/json') ? await res.json().catch(() => ({})) : await res.text()
  if (!res.ok) {
    throw new Error((data && data.detail) || 'Request failed')
  }
  return data
}

// auth-service — routes are bare (no /auth prefix on the service side); the
// gateway's /api/auth/ location strips the prefix back off before proxying.
export const auth = {
  register: (payload) => request('/auth/register', { method: 'POST', body: JSON.stringify(payload) }),
  login: (payload) => request('/auth/login', { method: 'POST', body: JSON.stringify(payload) }),
  verifyOtp: (payload) => request('/auth/login/otp/verify', { method: 'POST', body: JSON.stringify(payload) }),
  verifyTotp: (payload) => request('/auth/login/totp/verify', { method: 'POST', body: JSON.stringify(payload) }),
  refresh: () => request('/auth/token/refresh', { method: 'POST' }),
  me: () => request('/auth/me'),
}

// Real TOTP (Google Authenticator) second factor — opt-in via the Security
// page, alongside the weak echoed 4-digit OTP.
export const totp = {
  status: () => request('/auth/totp/status'),
  enroll: () => request('/auth/totp/enroll', { method: 'POST' }),
  confirm: (code) => request('/auth/totp/confirm', { method: 'POST', body: JSON.stringify({ code }) }),
  disable: () => request('/auth/totp/disable', { method: 'POST' }),
}

// accounts-service — every route already starts with /accounts on the
// service side, so the full gateway path is /api/accounts/accounts/... .
export const accounts = {
  list: () => request('/accounts/accounts'),
  get: (id) => request(`/accounts/accounts/${id}`),
  update: (id, payload) => request(`/accounts/accounts/${id}`, { method: 'PATCH', body: JSON.stringify(payload) }),
  search: (q) => request(`/accounts/accounts/search?q=${encodeURIComponent(q)}`),
  statementUrl: (id, file) => `${BASE}/accounts/accounts/${id}/statement?file=${encodeURIComponent(file || 'statement.csv')}`,
  linkExternal: (payload) => request('/accounts/accounts/link-external', { method: 'POST', body: JSON.stringify(payload) }),
}

// transfers-service — same pattern: routes start with /transfers already.
export const transfers = {
  create: (payload) => request('/transfers/transfers', { method: 'POST', body: JSON.stringify(payload) }),
  list: (accountId) => request(`/transfers/transfers?account_id=${accountId}`),
  adminOverride: (payload) => request('/transfers/transfers/admin-override', { method: 'POST', body: JSON.stringify(payload) }),
}

// kyc-service — routes start with /kyc already, so the full gateway path is
// /api/kyc/kyc/... .
export const kyc = {
  // Multipart upload: build a FormData body and send ONLY the Authorization
  // header — do NOT set Content-Type manually, or the browser won't add the
  // multipart boundary. This bypasses the shared JSON `request` helper.
  uploadDocument: async (docType, file) => {
    const fd = new FormData()
    fd.append('doc_type', docType)
    fd.append('file', file)
    const res = await fetch(`${BASE}/kyc/kyc/upload`, {
      method: 'POST',
      credentials: 'include',
      headers: { ...authHeader() },
      body: fd,
    })
    const data = await res.json().catch(() => ({}))
    if (!res.ok) throw new Error((data && data.detail) || 'Upload failed')
    return data
  },
  list: () => request('/kyc/kyc/documents'),
  get: (id) => request(`/kyc/kyc/${id}`),
  downloadUrl: (id) => `${BASE}/kyc/kyc/${id}/download`,
  pending: () => request('/kyc/kyc/pending'),
  review: (id, status) => request(`/kyc/kyc/${id}/review`, { method: 'POST', body: JSON.stringify({ status }) }),
}

// support-service — routes start with /tickets already, so the full gateway
// path is /api/support/tickets/... .
export const support = {
  createTicket: (payload) => request('/support/tickets', { method: 'POST', body: JSON.stringify(payload) }),
  listMine: () => request('/support/tickets'),
  listAll: () => request('/support/tickets/all'),
  getTicket: (id) => request(`/support/tickets/${id}`),
  postMessage: (id, payload) => request(`/support/tickets/${id}/messages`, { method: 'POST', body: JSON.stringify(payload) }),
}
