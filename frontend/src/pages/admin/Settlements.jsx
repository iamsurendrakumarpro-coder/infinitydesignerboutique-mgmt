import { useState, useEffect, useCallback } from 'react'
import * as settlementsService from '../../services/settlements'
import SkeletonLoader from '../../components/common/SkeletonLoader'
import {
  Wallet,
  Plus,
  Calendar,
  IndianRupee,
  AlertCircle,
  CheckCircle2,
  FileText,
  Loader2,
} from 'lucide-react'
import { format } from 'date-fns'

export default function Settlements() {
  const [settlements, setSettlements] = useState([])
  const [loading, setLoading] = useState(true)
  const [generating, setGenerating] = useState(false)
  const [period, setPeriod] = useState('weekly')
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  const fetchSettlements = useCallback(async () => {
    try {
      const data = await settlementsService.list({ period })
      setSettlements(Array.isArray(data) ? data : data.settlements || [])
    } catch {
      // Handle error
    } finally {
      setLoading(false)
    }
  }, [period])

  useEffect(() => {
    fetchSettlements()
  }, [fetchSettlements])

  async function handleGenerate() {
    setGenerating(true)
    setError('')
    setSuccess('')
    try {
      await settlementsService.generate({ period })
      setSuccess('Settlement generated successfully!')
      fetchSettlements()
      setTimeout(() => setSuccess(''), 3000)
    } catch (err) {
      setError(err.response?.data?.error || 'Failed to generate settlement')
    } finally {
      setGenerating(false)
    }
  }

  return (
    <div className="space-y-6 animate-slide-up">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-800">Settlements</h1>
          <p className="text-sm text-slate-500 mt-0.5">Generate and view weekly pay settlements</p>
        </div>
        <button
          onClick={handleGenerate}
          disabled={generating}
          className="btn-primary"
        >
          {generating ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Plus className="h-4 w-4" />
          )}
          {generating ? 'Generating...' : 'Generate Settlement'}
        </button>
      </div>

      {success && (
        <div className="flex items-center gap-2 text-success-700 text-sm bg-success-50 rounded-xl px-4 py-3">
          <CheckCircle2 className="h-4 w-4 shrink-0" />
          {success}
        </div>
      )}
      {error && (
        <div className="flex items-center gap-2 text-danger-600 text-sm bg-danger-50 rounded-xl px-4 py-3">
          <AlertCircle className="h-4 w-4 shrink-0" />
          {error}
        </div>
      )}

      {/* Period Filter */}
      <div className="flex items-center gap-3">
        <Calendar className="h-4 w-4 text-slate-400" />
        <select
          value={period}
          onChange={(e) => setPeriod(e.target.value)}
          className="input-field !w-auto"
        >
          <option value="weekly">This Week</option>
          <option value="monthly">This Month</option>
        </select>
      </div>

      {loading ? (
        <SkeletonLoader variant="table-row" count={5} />
      ) : settlements.length === 0 ? (
        <div className="card text-center py-12">
          <Wallet className="h-12 w-12 text-slate-300 mx-auto mb-3" />
          <p className="text-sm font-medium text-slate-500">No settlements generated yet</p>
          <p className="text-xs text-slate-400 mt-1">Click &quot;Generate Settlement&quot; to create the first one</p>
        </div>
      ) : (
        <>
          {/* Desktop Table */}
          <div className="hidden md:block card !p-0 overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-slate-100 bg-slate-50/50">
                    <th className="text-left px-5 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wider">Employee</th>
                    <th className="text-right px-5 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wider">Base Pay</th>
                    <th className="text-right px-5 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wider">OT Pay</th>
                    <th className="text-right px-5 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wider">Expenses</th>
                    <th className="text-right px-5 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wider">Advances</th>
                    <th className="text-right px-5 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wider">Net Payable</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-50">
                  {settlements.map((item, idx) => (
                    <tr key={item.id || item._id || idx} className="hover:bg-slate-50/50 transition-colors">
                      <td className="px-5 py-3.5">
                        <div className="flex items-center gap-3">
                          <div className="h-8 w-8 rounded-full gradient-primary flex items-center justify-center text-white text-xs font-bold">
                            {(item.staff_name || item.employee_name || '?').charAt(0)}
                          </div>
                          <div>
                            <p className="text-sm font-semibold text-slate-700">{item.staff_name || item.employee_name || 'Staff'}</p>
                            {item.period_start && (
                              <p className="text-xs text-slate-400">
                                {format(new Date(item.period_start), 'dd MMM')} — {item.period_end ? format(new Date(item.period_end), 'dd MMM') : ''}
                              </p>
                            )}
                          </div>
                        </div>
                      </td>
                      <td className="px-5 py-3.5 text-right text-sm font-medium text-slate-700">₹{item.base_pay ?? item.base_salary ?? 0}</td>
                      <td className="px-5 py-3.5 text-right text-sm font-medium text-slate-700">₹{item.ot_pay ?? item.overtime_pay ?? 0}</td>
                      <td className="px-5 py-3.5 text-right text-sm font-medium text-slate-700">₹{item.expenses ?? 0}</td>
                      <td className="px-5 py-3.5 text-right text-sm font-medium text-red-600">-₹{item.advances ?? 0}</td>
                      <td className="px-5 py-3.5 text-right">
                        <span className="text-sm font-bold text-emerald-700 bg-emerald-50 px-2.5 py-1 rounded-lg">
                          ₹{item.net_payable ?? item.net_pay ?? 0}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Mobile Cards */}
          <div className="md:hidden space-y-3">
            {settlements.map((item, idx) => (
              <div key={item.id || item._id || idx} className="card space-y-3">
                <div className="flex items-center gap-3">
                  <div className="h-10 w-10 rounded-full gradient-primary flex items-center justify-center text-white text-sm font-bold">
                    {(item.staff_name || item.employee_name || '?').charAt(0)}
                  </div>
                  <div>
                    <p className="text-sm font-bold text-slate-800">{item.staff_name || item.employee_name || 'Staff'}</p>
                    {item.period_start && (
                      <p className="text-xs text-slate-400">
                        {format(new Date(item.period_start), 'dd MMM')} — {item.period_end ? format(new Date(item.period_end), 'dd MMM') : ''}
                      </p>
                    )}
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-2">
                  <div className="p-2.5 rounded-xl bg-slate-50">
                    <p className="text-[10px] text-slate-400 uppercase">Base Pay</p>
                    <p className="text-sm font-bold text-slate-700">₹{item.base_pay ?? item.base_salary ?? 0}</p>
                  </div>
                  <div className="p-2.5 rounded-xl bg-slate-50">
                    <p className="text-[10px] text-slate-400 uppercase">OT Pay</p>
                    <p className="text-sm font-bold text-slate-700">₹{item.ot_pay ?? item.overtime_pay ?? 0}</p>
                  </div>
                  <div className="p-2.5 rounded-xl bg-slate-50">
                    <p className="text-[10px] text-slate-400 uppercase">Expenses</p>
                    <p className="text-sm font-bold text-slate-700">₹{item.expenses ?? 0}</p>
                  </div>
                  <div className="p-2.5 rounded-xl bg-red-50">
                    <p className="text-[10px] text-red-400 uppercase">Advances</p>
                    <p className="text-sm font-bold text-red-600">-₹{item.advances ?? 0}</p>
                  </div>
                </div>
                <div className="flex items-center justify-between pt-2 border-t border-slate-100">
                  <span className="text-sm font-medium text-slate-600">Net Payable</span>
                  <span className="text-lg font-bold text-emerald-700">₹{item.net_payable ?? item.net_pay ?? 0}</span>
                </div>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  )
}
