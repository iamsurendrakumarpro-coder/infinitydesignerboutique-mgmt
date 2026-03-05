import { Routes, Route, Navigate } from 'react-router-dom'
import { useAuth } from './context/AuthContext'
import ProtectedRoute from './components/common/ProtectedRoute'
import AdminLayout from './components/layout/AdminLayout'
import StaffLayout from './components/layout/StaffLayout'
import LoginPage from './pages/auth/LoginPage'
import ChangePinPage from './pages/auth/ChangePinPage'
import Dashboard from './pages/admin/Dashboard'
import StaffDirectory from './pages/admin/StaffDirectory'
import StaffCreate from './pages/admin/StaffCreate'
import StaffEdit from './pages/admin/StaffEdit'
import StaffProfileView from './pages/admin/StaffProfileView'
import Approvals from './pages/admin/Approvals'
import Settlements from './pages/admin/Settlements'
import Reports from './pages/admin/Reports'
import DutyStation from './pages/staff/DutyStation'
import MyMoney from './pages/staff/MyMoney'
import StaffProfile from './pages/staff/StaffProfile'

function RootRedirect() {
  const { isAuthenticated, isAdmin, loading } = useAuth()
  if (loading) return null
  if (!isAuthenticated) return <Navigate to="/login" replace />
  return <Navigate to={isAdmin ? '/admin' : '/staff'} replace />
}

export default function App() {
  return (
    <Routes>
      {/* Public Routes */}
      <Route path="/login" element={<LoginPage />} />
      <Route
        path="/change-pin"
        element={
          <ProtectedRoute>
            <ChangePinPage />
          </ProtectedRoute>
        }
      />

      {/* Admin Routes */}
      <Route
        path="/admin"
        element={
          <ProtectedRoute allowedRoles={['admin', 'root_admin']}>
            <AdminLayout />
          </ProtectedRoute>
        }
      >
        <Route index element={<Dashboard />} />
        <Route path="staff" element={<StaffDirectory />} />
        <Route path="staff/create" element={<StaffCreate />} />
        <Route path="staff/:id" element={<StaffProfileView />} />
        <Route path="staff/:id/edit" element={<StaffEdit />} />
        <Route path="approvals" element={<Approvals />} />
        <Route path="settlements" element={<Settlements />} />
        <Route path="reports" element={<Reports />} />
      </Route>

      {/* Staff Routes */}
      <Route
        path="/staff"
        element={
          <ProtectedRoute allowedRoles={['staff']}>
            <StaffLayout />
          </ProtectedRoute>
        }
      >
        <Route index element={<DutyStation />} />
        <Route path="money" element={<MyMoney />} />
        <Route path="profile" element={<StaffProfile />} />
      </Route>

      {/* Catch-all */}
      <Route path="/" element={<RootRedirect />} />
      <Route path="*" element={<RootRedirect />} />
    </Routes>
  )
}
