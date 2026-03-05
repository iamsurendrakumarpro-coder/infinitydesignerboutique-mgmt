import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import * as dashboardService from '../../services/dashboard'
import * as financialService from '../../services/financial'
import * as overtimeService from '../../services/overtime'
import SkeletonLoader from '../../components/common/SkeletonLoader'
import {
  Users,
  UserCheck,
  ClipboardList,
  Clock,
  TrendingUp,
  ArrowRight,
  Plus,
  IndianRupee,
} from 'lucide-react'
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts'

function SummaryCard({ icon, label, value, color, onClick }) {
  const Icon = icon
  return (
    <button
      onClick={onClick}
      className="card-hover text-left w-full group"
    >
      <div className="flex items-start justify-between">
        <div className={`p-2.5 rounded-xl ${color}`}>
          <Icon className="h-5 w-5" />
        </div>
        <ArrowRight className="h-4 w-4 text-slate-300 group-hover:text-primary-400 transition-colors" />
      </div>
      <div className="mt-3">
        <p className="text-2xl font-bold text-slate-800">{value ?? '—'}</p>
        <p className="text-xs font-medium text-slate-500 mt-0.5">{label}</p>
      </div>
    </button>
  )
}

export default function Dashboard() {
  const [summary, setSummary] = useState(null)
  const [attendance, setAttendance] = useState(null)
  const [pendingFinancial, setPendingFinancial] = useState([])
  const [pendingOT, setPendingOT] = useState([])
  const [loading, setLoading] = useState(true)
  const navigate = useNavigate()

  useEffect(() => {
    async function fetchData() {
      try {
        const [summaryData, attendanceData, financialData, otData] = await Promise.allSettled([
          dashboardService.getSummary(),
          dashboardService.getAttendanceSummary('weekly'),
          financialService.getRequests({ status: 'pending' }),
          overtimeService.getPending(),
        ])

        if (summaryData.status === 'fulfilled') setSummary(summaryData.value)
        if (attendanceData.status === 'fulfilled') setAttendance(attendanceData.value)
        if (financialData.status === 'fulfilled') {
          const d = financialData.value
          setPendingFinancial(Array.isArray(d) ? d : d.requests || [])
        }
        if (otData.status === 'fulfilled') {
          const d = otData.value
          setPendingOT(Array.isArray(d) ? d : d.overtime || [])
        }
      } finally {
        setLoading(false)
      }
    }
    fetchData()
  }, [])

  const chartData = attendance?.daily_breakdown || attendance?.data || []

  if (loading) {
    return (
      <div className="space-y-6">
        <SkeletonLoader variant="text" />
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <SkeletonLoader variant="card" count={4} />
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-8 animate-slide-up">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-800">Dashboard</h1>
          <p className="text-sm text-slate-500 mt-0.5">Overview of your boutique operations</p>
        </div>
        <button
          onClick={() => navigate('/admin/staff/create')}
          className="btn-primary hidden sm:inline-flex"
        >
          <Plus className="h-4 w-4" />
          Add Staff
        </button>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <SummaryCard
          icon={Users}
          label="Total Staff"
          value={summary?.total_staff ?? summary?.totalStaff ?? 0}
          color="bg-primary-50 text-primary-600"
          onClick={() => navigate('/admin/staff')}
        />
        <SummaryCard
          icon={UserCheck}
          label="Present Today"
          value={summary?.present_today ?? summary?.presentToday ?? 0}
          color="bg-emerald-50 text-emerald-600"
          onClick={() => navigate('/admin/staff')}
        />
        <SummaryCard
          icon={ClipboardList}
          label="Pending Requests"
          value={summary?.pending_requests ?? summary?.pendingRequests ?? pendingFinancial.length}
          color="bg-amber-50 text-amber-600"
          onClick={() => navigate('/admin/approvals')}
        />
        <SummaryCard
          icon={Clock}
          label="Pending OT"
          value={summary?.pending_overtime ?? summary?.pendingOT ?? pendingOT.length}
          color="bg-violet-50 text-violet-600"
          onClick={() => navigate('/admin/approvals')}
        />
      </div>

      {/* Charts Section */}
      <div className="grid lg:grid-cols-2 gap-6">
        {/* Attendance Chart */}
        <div className="card space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-bold text-slate-700 flex items-center gap-2">
              <TrendingUp className="h-4 w-4 text-primary-500" />
              Weekly Attendance
            </h2>
          </div>
          {chartData.length > 0 ? (
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={chartData} barCategoryGap="20%">
                  <CartesianGrid strokeDasharray="3 3" stroke="#F1F5F9" />
                  <XAxis
                    dataKey="day"
                    tick={{ fontSize: 12, fill: '#94A3B8' }}
                    axisLine={false}
                    tickLine={false}
                  />
                  <YAxis
                    tick={{ fontSize: 12, fill: '#94A3B8' }}
                    axisLine={false}
                    tickLine={false}
                  />
                  <Tooltip
                    contentStyle={{
                      borderRadius: '12px',
                      border: 'none',
                      boxShadow: '0 4px 20px rgba(0,0,0,0.1)',
                    }}
                  />
                  <Bar dataKey="present" fill="#4F46E5" radius={[6, 6, 0, 0]} name="Present" />
                  <Bar dataKey="absent" fill="#E0E7FF" radius={[6, 6, 0, 0]} name="Absent" />
                </BarChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <div className="h-64 flex items-center justify-center text-sm text-slate-400">
              No attendance data available
            </div>
          )}
        </div>

        {/* Recent Activity */}
        <div className="card space-y-4">
          <h2 className="text-sm font-bold text-slate-700">Recent Activity</h2>
          <div className="space-y-3">
            {pendingFinancial.slice(0, 5).map((req) => (
              <div key={req.id || req._id} className="flex items-center gap-3 px-3 py-2 rounded-xl bg-slate-50">
                <div className="p-2 rounded-lg bg-amber-50">
                  <IndianRupee className="h-3.5 w-3.5 text-amber-600" />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-slate-700 truncate">
                    {req.staff_name || req.staffName || 'Staff'} — ₹{req.amount}
                  </p>
                  <p className="text-xs text-slate-400">
                    {req.type?.replace('_', ' ')} • {req.category || ''}
                  </p>
                </div>
                <span className="text-xs font-medium text-amber-600 bg-amber-50 px-2 py-1 rounded-full">
                  Pending
                </span>
              </div>
            ))}
            {pendingFinancial.length === 0 && pendingOT.length === 0 && (
              <div className="text-center py-6 text-sm text-slate-400">
                No pending items
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Quick Actions */}
      <div className="card">
        <h2 className="text-sm font-bold text-slate-700 mb-4">Quick Actions</h2>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <button
            onClick={() => navigate('/admin/staff/create')}
            className="flex flex-col items-center gap-2 p-4 rounded-xl bg-primary-50 text-primary-700 hover:bg-primary-100 transition-colors"
          >
            <Plus className="h-5 w-5" />
            <span className="text-xs font-semibold">Add Staff</span>
          </button>
          <button
            onClick={() => navigate('/admin/approvals')}
            className="flex flex-col items-center gap-2 p-4 rounded-xl bg-amber-50 text-amber-700 hover:bg-amber-100 transition-colors"
          >
            <ClipboardList className="h-5 w-5" />
            <span className="text-xs font-semibold">Approvals</span>
          </button>
          <button
            onClick={() => navigate('/admin/settlements')}
            className="flex flex-col items-center gap-2 p-4 rounded-xl bg-emerald-50 text-emerald-700 hover:bg-emerald-100 transition-colors"
          >
            <IndianRupee className="h-5 w-5" />
            <span className="text-xs font-semibold">Settlements</span>
          </button>
          <button
            onClick={() => navigate('/admin/reports')}
            className="flex flex-col items-center gap-2 p-4 rounded-xl bg-violet-50 text-violet-700 hover:bg-violet-100 transition-colors"
          >
            <TrendingUp className="h-5 w-5" />
            <span className="text-xs font-semibold">Reports</span>
          </button>
        </div>
      </div>
    </div>
  )
}
