import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { useAuth } from '../../context/AuthContext'
import { Clock, Wallet, User, Gem, LogOut } from 'lucide-react'

const navItems = [
  { to: '/staff', icon: Clock, label: 'Duty Station', end: true },
  { to: '/staff/money', icon: Wallet, label: 'My Money' },
  { to: '/staff/profile', icon: User, label: 'Profile' },
]

export default function StaffLayout() {
  const { logout } = useAuth()
  const navigate = useNavigate()

  async function handleLogout() {
    await logout()
    navigate('/login')
  }

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col">
      {/* Top Header */}
      <header className="sticky top-0 z-30 bg-white/80 backdrop-blur-lg border-b border-slate-100">
        <div className="flex items-center gap-3 px-4 h-14">
          <div className="flex items-center justify-center h-8 w-8 rounded-lg gradient-primary">
            <Gem className="h-4 w-4 text-white" />
          </div>
          <div className="flex-1 min-w-0">
            <h1 className="text-sm font-bold text-slate-800 truncate">Infinity Designer Boutique</h1>
          </div>
          <button
            onClick={handleLogout}
            className="p-2 rounded-xl hover:bg-slate-100 transition-colors text-slate-500"
            title="Sign out"
          >
            <LogOut className="h-4.5 w-4.5" />
          </button>
        </div>
      </header>

      {/* Page Content */}
      <main className="flex-1 p-4 pb-24 animate-fade-in">
        <Outlet />
      </main>

      {/* Bottom Navigation */}
      <nav className="fixed bottom-0 left-0 right-0 z-30 bg-white/90 backdrop-blur-lg border-t border-slate-100 safe-area-bottom">
        <div className="flex items-center justify-around h-16 max-w-lg mx-auto">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) =>
                `flex flex-col items-center gap-1 px-4 py-1.5 rounded-xl min-w-[72px] transition-all duration-200 ${
                  isActive
                    ? 'text-primary-600'
                    : 'text-slate-400 hover:text-slate-600'
                }`
              }
            >
              {({ isActive }) => (
                <>
                  <div
                    className={`p-1.5 rounded-xl transition-all duration-200 ${
                      isActive ? 'bg-primary-50' : ''
                    }`}
                  >
                    <item.icon
                      className={`h-5 w-5 transition-all ${isActive ? 'stroke-[2.5]' : ''}`}
                    />
                  </div>
                  <span className={`text-[10px] font-semibold ${isActive ? 'text-primary-700' : ''}`}>
                    {item.label}
                  </span>
                </>
              )}
            </NavLink>
          ))}
        </div>
      </nav>
    </div>
  )
}
