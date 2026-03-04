import { useState } from 'react'
import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { useAuth } from '../../context/AuthContext'
import {
  LayoutDashboard,
  Users,
  ClipboardCheck,
  Wallet,
  BarChart3,
  Menu,
  X,
  LogOut,
  ChevronRight,
  Gem,
} from 'lucide-react'

const navItems = [
  { to: '/admin', icon: LayoutDashboard, label: 'Dashboard', end: true },
  { to: '/admin/staff', icon: Users, label: 'Staff Directory' },
  { to: '/admin/approvals', icon: ClipboardCheck, label: 'Approvals' },
  { to: '/admin/settlements', icon: Wallet, label: 'Settlements' },
  { to: '/admin/reports', icon: BarChart3, label: 'Reports' },
]

export default function AdminLayout() {
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  async function handleLogout() {
    await logout()
    navigate('/login')
  }

  return (
    <div className="min-h-screen bg-slate-50">
      {/* Mobile Overlay */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 bg-black/40 z-40 lg:hidden backdrop-blur-sm"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside
        className={`fixed top-0 left-0 z-50 h-full w-[272px] gradient-hero text-white flex flex-col transition-transform duration-300 lg:translate-x-0 ${
          sidebarOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        {/* Brand Header */}
        <div className="flex items-center gap-3 px-6 py-6 border-b border-white/10">
          <div className="flex items-center justify-center h-10 w-10 rounded-xl bg-white/15 backdrop-blur">
            <Gem className="h-5 w-5 text-accent-300" />
          </div>
          <div className="flex-1 min-w-0">
            <h1 className="text-sm font-bold tracking-tight leading-tight">Infinity Designer</h1>
            <p className="text-xs text-primary-200 font-medium">Boutique Management</p>
          </div>
          <button
            onClick={() => setSidebarOpen(false)}
            className="lg:hidden p-1 rounded-lg hover:bg-white/10"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Navigation */}
        <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              onClick={() => setSidebarOpen(false)}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all duration-200 group ${
                  isActive
                    ? 'bg-white/15 text-white shadow-lg shadow-black/10'
                    : 'text-primary-200 hover:bg-white/8 hover:text-white'
                }`
              }
            >
              <item.icon className="h-[18px] w-[18px] shrink-0" />
              <span className="flex-1">{item.label}</span>
              <ChevronRight className="h-3.5 w-3.5 opacity-0 group-hover:opacity-60 transition-opacity" />
            </NavLink>
          ))}
        </nav>

        {/* User Section */}
        <div className="px-3 pb-4">
          <div className="rounded-xl bg-white/8 px-4 py-3 mb-2">
            <p className="text-sm font-semibold text-white truncate">{user?.full_name || 'Admin'}</p>
            <p className="text-xs text-primary-300 capitalize">{user?.role?.replace('_', ' ')}</p>
          </div>
          <button
            onClick={handleLogout}
            className="w-full flex items-center gap-3 px-4 py-2.5 rounded-xl text-sm font-medium text-primary-200 hover:bg-white/8 hover:text-white transition-all"
          >
            <LogOut className="h-[18px] w-[18px]" />
            Sign Out
          </button>
        </div>
      </aside>

      {/* Main Content */}
      <div className="lg:ml-[272px]">
        {/* Top Bar */}
        <header className="sticky top-0 z-30 bg-white/80 backdrop-blur-lg border-b border-slate-100">
          <div className="flex items-center gap-4 px-4 lg:px-8 h-16">
            <button
              onClick={() => setSidebarOpen(true)}
              className="lg:hidden p-2 -ml-1 rounded-xl hover:bg-slate-100 transition-colors"
            >
              <Menu className="h-5 w-5 text-slate-600" />
            </button>
            <div className="flex-1" />
            <div className="flex items-center gap-2">
              <div className="h-8 w-8 rounded-full gradient-primary flex items-center justify-center text-white text-xs font-bold">
                {user?.full_name?.charAt(0) || 'A'}
              </div>
            </div>
          </div>
        </header>

        {/* Page Content */}
        <main className="p-4 lg:p-8 animate-fade-in">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
