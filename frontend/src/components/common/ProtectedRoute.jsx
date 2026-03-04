import { Navigate } from 'react-router-dom'
import { useAuth } from '../../context/AuthContext'
import LoadingSpinner from './LoadingSpinner'

export default function ProtectedRoute({ children, allowedRoles = [] }) {
  const { isAuthenticated, user, loading, mustChangePin } = useAuth()

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50">
        <LoadingSpinner message="Verifying session..." size="lg" />
      </div>
    )
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />
  }

  if (mustChangePin && window.location.pathname !== '/change-pin') {
    return <Navigate to="/change-pin" replace />
  }

  if (allowedRoles.length > 0 && !allowedRoles.includes(user?.role)) {
    const role = user?.role
    if (role === 'admin' || role === 'root_admin') {
      return <Navigate to="/admin" replace />
    }
    return <Navigate to="/staff" replace />
  }

  return children
}
