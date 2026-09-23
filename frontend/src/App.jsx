import { Navigate, Route, Routes } from 'react-router-dom'

import AccountDetail from './pages/AccountDetail'
import Dashboard from './pages/Dashboard'
import Login from './pages/Login'
import Register from './pages/Register'
import Security from './pages/Security'
import Transfer from './pages/Transfer'
import TransactionHistory from './pages/TransactionHistory'

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Navigate to="/login" replace />} />
      <Route path="/login" element={<Login />} />
      <Route path="/register" element={<Register />} />
      <Route path="/dashboard" element={<Dashboard />} />
      <Route path="/accounts/:id" element={<AccountDetail />} />
      <Route path="/accounts/:id/history" element={<TransactionHistory />} />
      <Route path="/transfer" element={<Transfer />} />
      <Route path="/security" element={<Security />} />
    </Routes>
  )
}
