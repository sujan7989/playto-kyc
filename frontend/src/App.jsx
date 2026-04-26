import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider, useAuth } from './AuthContext'
import Login from './pages/Login'
import Register from './pages/Register'
import MerchantDashboard from './pages/MerchantDashboard'
import KYCForm from './pages/KYCForm'
import ReviewerDashboard from './pages/ReviewerDashboard'
import ReviewSubmission from './pages/ReviewSubmission'

function PrivateRoute({ children, role }) {
  const { user, loading } = useAuth()
  if (loading) return <div className="flex items-center justify-center h-screen text-gray-500">Loading...</div>
  if (!user) return <Navigate to="/login" replace />
  if (role && user.role !== role) return <Navigate to="/" replace />
  return children
}

function HomeRedirect() {
  const { user, loading } = useAuth()
  if (loading) return null
  if (!user) return <Navigate to="/login" replace />
  if (user.role === 'reviewer') return <Navigate to="/reviewer" replace />
  return <Navigate to="/merchant" replace />
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<HomeRedirect />} />
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />
          <Route path="/merchant" element={
            <PrivateRoute role="merchant"><MerchantDashboard /></PrivateRoute>
          } />
          <Route path="/merchant/kyc/:id" element={
            <PrivateRoute role="merchant"><KYCForm /></PrivateRoute>
          } />
          <Route path="/reviewer" element={
            <PrivateRoute role="reviewer"><ReviewerDashboard /></PrivateRoute>
          } />
          <Route path="/reviewer/submission/:id" element={
            <PrivateRoute role="reviewer"><ReviewSubmission /></PrivateRoute>
          } />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  )
}
