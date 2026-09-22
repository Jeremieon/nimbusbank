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
  refresh: () => request('/auth/token/refresh', { method: 'POST' }),
  me: () => request('/auth/me'),
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
