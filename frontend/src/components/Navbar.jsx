import { useAuth } from '../AuthContext'
import { useNavigate } from 'react-router-dom'

export default function Navbar() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  return (
    <nav className="bg-blue-700 text-white px-6 py-3 flex items-center justify-between shadow">
      <div className="flex items-center gap-2">
        <span className="text-xl font-bold tracking-tight">Playto</span>
        <span className="text-blue-200 text-sm font-medium">KYC</span>
      </div>
      {user && (
        <div className="flex items-center gap-4">
          <span className="text-sm text-blue-100">
            {user.username}
            <span className="ml-2 bg-blue-500 text-white text-xs px-2 py-0.5 rounded-full capitalize">
              {user.role}
            </span>
          </span>
          <button
            onClick={handleLogout}
            className="text-sm bg-blue-600 hover:bg-blue-500 px-3 py-1.5 rounded transition"
          >
            Logout
          </button>
        </div>
      )}
    </nav>
  )
}
