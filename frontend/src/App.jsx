import { Navigate, Route, Routes } from 'react-router-dom'

import AccountDetail from './pages/AccountDetail'
import AgentConsole from './pages/AgentConsole'
import Cards from './pages/Cards'
import Dashboard from './pages/Dashboard'
import Kyc from './pages/Kyc'
import Login from './pages/Login'
import Ops from './pages/Ops'
import Register from './pages/Register'
import Security from './pages/Security'
import Support from './pages/Support'
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
      <Route path="/cards" element={<Cards />} />
      <Route path="/ops" element={<Ops />} />
      <Route path="/kyc" element={<Kyc />} />
      <Route path="/support" element={<Support />} />
      <Route path="/support/agent" element={<AgentConsole />} />
      <Route path="/security" element={<Security />} />
    </Routes>
  )
}
