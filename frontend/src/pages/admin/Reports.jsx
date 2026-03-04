import { useState, useEffect } from 'react'
import * as dashboardService from '../../services/dashboard'
import SkeletonLoader from '../../components/common/SkeletonLoader'
import { BarChart3, TrendingUp, IndianRupee, Users, Calendar } from 'lucide-react'
import {
  BarChart,
  Bar,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from 'recharts'

const periods = [
  { value: 'daily', label: 'Day' },
  { value: 'weekly', label: 'Week' },
  { value: 'monthly', label: 'Month' },
  { value: 'quarterly', label: 'Quarter' },
  { value: 'yearly', label: 'Year' },
]

export default function Reports() {
  const [period, setPeriod] = useState('weekly')
  const [financialData, setFinancialData] = useState(null)
  const [attendanceData, setAttendanceData] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    async function fetchData() {
      setLoading(true)
      try {
        const [fin, att] = await Promise.allSettled([
          dashboardService.getFinancialSummary(period),
          dashboardService.getAttendanceSummary(period),
        ])
        if (fin.status === 'fulfilled') setFinancialData(fin.value)
        if (att.status === 'fulfilled') setAttendanceData(att.value)
      } finally {
        setLoading(false)
      }
    }
    fetchData()
  }, [period])

  const spendingData = financialData?.breakdown || financialData?.data || []
  const attendanceChartData = attendanceData?.daily_breakdown || attendanceData?.data || []

  const totals = financialData?.totals || {}

  return (
    <div className="space-y-6 animate-slide-up">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-800">Reports & Analytics</h1>
          <p className="text-sm text-slate-500 mt-0.5">Financial and operational insights</p>
        </div>

        {/* Period Selector */}
        <div className="flex items-center gap-2">
          <Calendar className="h-4 w-4 text-slate-400" />
          <div className="flex gap-1 p-1 bg-slate-100 rounded-xl">
            {periods.map((p) => (
              <button
                key={p.value}
                onClick={() => setPeriod(p.value)}
                className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                  period === p.value
                    ? 'bg-white text-primary-700 shadow-sm'
                    : 'text-slate-500 hover:text-slate-700'
                }`}
              >
                {p.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {loading ? (
        <div className="space-y-6">
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <SkeletonLoader variant="card" count={4} />
          </div>
        </div>
      ) : (
        <>
          {/* Summary Totals */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <div className="card">
              <div className="p-2 rounded-xl bg-primary-50 w-fit mb-3">
                <IndianRupee className="h-4 w-4 text-primary-600" />
              </div>
              <p className="text-xl font-bold text-slate-800">₹{totals.base_salaries ?? totals.total_salary ?? 0}</p>
              <p className="text-xs text-slate-500 mt-0.5">Base Salaries</p>
            </div>
            <div className="card">
              <div className="p-2 rounded-xl bg-violet-50 w-fit mb-3">
                <TrendingUp className="h-4 w-4 text-violet-600" />
              </div>
              <p className="text-xl font-bold text-slate-800">₹{totals.overtime ?? totals.total_overtime ?? 0}</p>
              <p className="text-xs text-slate-500 mt-0.5">Overtime Pay</p>
            </div>
            <div className="card">
              <div className="p-2 rounded-xl bg-amber-50 w-fit mb-3">
                <BarChart3 className="h-4 w-4 text-amber-600" />
              </div>
              <p className="text-xl font-bold text-slate-800">₹{totals.expenses ?? totals.total_expenses ?? 0}</p>
              <p className="text-xs text-slate-500 mt-0.5">Shop Expenses</p>
            </div>
            <div className="card">
              <div className="p-2 rounded-xl bg-red-50 w-fit mb-3">
                <Users className="h-4 w-4 text-red-600" />
              </div>
              <p className="text-xl font-bold text-slate-800">₹{totals.advances ?? totals.total_advances ?? 0}</p>
              <p className="text-xs text-slate-500 mt-0.5">Advances</p>
            </div>
          </div>

          {/* Spending Breakdown Chart */}
          <div className="card space-y-4">
            <h2 className="text-sm font-bold text-slate-700 flex items-center gap-2">
              <BarChart3 className="h-4 w-4 text-primary-500" />
              Spending Breakdown
            </h2>
            {spendingData.length > 0 ? (
              <div className="h-72">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={spendingData} barCategoryGap="15%">
                    <CartesianGrid strokeDasharray="3 3" stroke="#F1F5F9" />
                    <XAxis dataKey="label" tick={{ fontSize: 11, fill: '#94A3B8' }} axisLine={false} tickLine={false} />
                    <YAxis tick={{ fontSize: 11, fill: '#94A3B8' }} axisLine={false} tickLine={false} />
                    <Tooltip
                      contentStyle={{ borderRadius: '12px', border: 'none', boxShadow: '0 4px 20px rgba(0,0,0,0.1)' }}
                      formatter={(value) => [`₹${value}`, '']}
                    />
                    <Legend iconType="circle" iconSize={8} />
                    <Bar dataKey="salaries" name="Salaries" fill="#4F46E5" radius={[4, 4, 0, 0]} />
                    <Bar dataKey="overtime" name="Overtime" fill="#8B5CF6" radius={[4, 4, 0, 0]} />
                    <Bar dataKey="expenses" name="Expenses" fill="#F59E0B" radius={[4, 4, 0, 0]} />
                    <Bar dataKey="advances" name="Advances" fill="#EF4444" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <div className="h-72 flex items-center justify-center text-sm text-slate-400">
                No financial data available for this period
              </div>
            )}
          </div>

          {/* Attendance Trends Chart */}
          <div className="card space-y-4">
            <h2 className="text-sm font-bold text-slate-700 flex items-center gap-2">
              <TrendingUp className="h-4 w-4 text-emerald-500" />
              Attendance Trends
            </h2>
            {attendanceChartData.length > 0 ? (
              <div className="h-72">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={attendanceChartData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#F1F5F9" />
                    <XAxis dataKey="day" tick={{ fontSize: 11, fill: '#94A3B8' }} axisLine={false} tickLine={false} />
                    <YAxis tick={{ fontSize: 11, fill: '#94A3B8' }} axisLine={false} tickLine={false} />
                    <Tooltip
                      contentStyle={{ borderRadius: '12px', border: 'none', boxShadow: '0 4px 20px rgba(0,0,0,0.1)' }}
                    />
                    <Legend iconType="circle" iconSize={8} />
                    <Line type="monotone" dataKey="present" name="Present" stroke="#22C55E" strokeWidth={2.5} dot={{ r: 4, fill: '#22C55E' }} />
                    <Line type="monotone" dataKey="absent" name="Absent" stroke="#EF4444" strokeWidth={2.5} dot={{ r: 4, fill: '#EF4444' }} />
                    <Line type="monotone" dataKey="late" name="Late" stroke="#F59E0B" strokeWidth={2.5} dot={{ r: 4, fill: '#F59E0B' }} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <div className="h-72 flex items-center justify-center text-sm text-slate-400">
                No attendance data available for this period
              </div>
            )}
          </div>
        </>
      )}
    </div>
  )
}
