import { useState, useEffect, useCallback } from 'react'
import * as financialService from '../../services/financial'
import LoadingSpinner from '../../components/common/LoadingSpinner'
import StatusBadge from '../../components/common/StatusBadge'
import SkeletonLoader from '../../components/common/SkeletonLoader'
import {
  Scissors,
  Coffee,
  Wallet,
  X,
  Send,
  AlertCircle,
  CheckCircle2,
  IndianRupee,
  FileText,
  Package,
} from 'lucide-react'
import { format } from 'date-fns'

const categories = [
  {
    id: 'materials',
    label: 'Materials / Thread',
    icon: Scissors,
    type: 'shop_expense',
    color: 'bg-violet-50 text-violet-600 border-violet-200',
    iconBg: 'bg-violet-100',
  },
  {
    id: 'food',
    label: 'Food / Tea',
    icon: Coffee,
    type: 'shop_expense',
    color: 'bg-orange-50 text-orange-600 border-orange-200',
    iconBg: 'bg-orange-100',
  },
  {
    id: 'advance',
    label: 'Personal Advance',
    icon: Wallet,
    type: 'personal_advance',
    color: 'bg-blue-50 text-blue-600 border-blue-200',
    iconBg: 'bg-blue-100',
  },
  {
    id: 'other',
    label: 'Other Expense',
    icon: Package,
    type: 'shop_expense',
    color: 'bg-slate-50 text-slate-600 border-slate-200',
    iconBg: 'bg-slate-100',
  },
]

function RequestModal({ category, onClose, onSubmit }) {
  const [amount, setAmount] = useState('')
  const [notes, setNotes] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')

  async function handleSubmit(e) {
    e.preventDefault()
    if (!amount || parseFloat(amount) <= 0) {
      setError('Please enter a valid amount')
      return
    }
    setSubmitting(true)
    setError('')
    try {
      await onSubmit({
        type: category.type,
        category: category.id,
        amount: parseFloat(amount),
        notes: notes.trim(),
      })
      onClose()
    } catch (err) {
      setError(err.response?.data?.error || 'Failed to submit request')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/40 backdrop-blur-sm" onClick={onClose} />
      <div className="relative w-full max-w-md bg-white rounded-t-3xl sm:rounded-3xl shadow-2xl animate-slide-up">
        <div className="flex items-center justify-between px-6 pt-5 pb-3">
          <div className="flex items-center gap-3">
            <div className={`p-2 rounded-xl ${category.iconBg}`}>
              <category.icon className="h-5 w-5" />
            </div>
            <h3 className="text-base font-bold text-slate-800">{category.label}</h3>
          </div>
          <button onClick={onClose} className="p-2 rounded-xl hover:bg-slate-100 text-slate-400">
            <X className="h-5 w-5" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="px-6 pb-6 space-y-4">
          <div>
            <label className="label">Amount (₹)</label>
            <div className="relative">
              <IndianRupee className="absolute left-3.5 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
              <input
                type="number"
                value={amount}
                onChange={(e) => setAmount(e.target.value)}
                placeholder="0.00"
                className="input-field pl-10 text-lg font-semibold"
                autoFocus
                min="1"
                step="any"
                inputMode="decimal"
              />
            </div>
          </div>

          <div>
            <label className="label">Notes (optional)</label>
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Add details about this request..."
              className="input-field resize-none"
              rows={3}
            />
          </div>

          {error && (
            <div className="flex items-center gap-2 text-danger-600 text-sm bg-danger-50 rounded-xl px-3 py-2.5">
              <AlertCircle className="h-4 w-4 shrink-0" />
              {error}
            </div>
          )}

          <button type="submit" disabled={submitting} className="btn-primary w-full">
            {submitting ? (
              <div className="h-4 w-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
            ) : (
              <Send className="h-4 w-4" />
            )}
            {submitting ? 'Submitting...' : 'Submit Request'}
          </button>
        </form>
      </div>
    </div>
  )
}

export default function MyMoney() {
  const [requests, setRequests] = useState([])
  const [loading, setLoading] = useState(true)
  const [activeCategory, setActiveCategory] = useState(null)
  const [success, setSuccess] = useState('')

  const fetchRequests = useCallback(async () => {
    try {
      const data = await financialService.getRequests()
      setRequests(Array.isArray(data) ? data : data.requests || [])
    } catch {
      // Silently handle
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchRequests()
  }, [fetchRequests])

  async function handleSubmit(requestData) {
    await financialService.createRequest(requestData)
    setSuccess('Request submitted successfully!')
    fetchRequests()
    setTimeout(() => setSuccess(''), 3000)
  }

  const grouped = {
    pending: requests.filter((r) => r.status === 'pending'),
    approved: requests.filter((r) => r.status === 'approved'),
    rejected: requests.filter((r) => r.status === 'rejected'),
  }

  return (
    <div className="max-w-lg mx-auto space-y-6 animate-slide-up">
      <div>
        <h1 className="text-xl font-bold text-slate-800">My Money</h1>
        <p className="text-sm text-slate-500 mt-0.5">Submit expenses & track requests</p>
      </div>

      {success && (
        <div className="flex items-center gap-2 text-success-700 text-sm bg-success-50 rounded-xl px-4 py-3 border border-emerald-100">
          <CheckCircle2 className="h-4 w-4 shrink-0" />
          {success}
        </div>
      )}

      {/* Category Buttons */}
      <div>
        <h2 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">
          Shop Expenses
        </h2>
        <div className="grid grid-cols-2 gap-3">
          {categories.filter((c) => c.type === 'shop_expense').map((cat) => (
            <button
              key={cat.id}
              onClick={() => setActiveCategory(cat)}
              className={`flex flex-col items-center gap-2.5 p-5 rounded-2xl border-2 transition-all duration-200 hover:shadow-md active:scale-[0.97] ${cat.color}`}
            >
              <div className={`p-3 rounded-xl ${cat.iconBg}`}>
                <cat.icon className="h-6 w-6" />
              </div>
              <span className="text-sm font-semibold">{cat.label}</span>
            </button>
          ))}
        </div>
      </div>

      <div>
        <h2 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">
          Personal
        </h2>
        <div className="grid grid-cols-2 gap-3">
          {categories.filter((c) => c.type === 'personal_advance').map((cat) => (
            <button
              key={cat.id}
              onClick={() => setActiveCategory(cat)}
              className={`flex flex-col items-center gap-2.5 p-5 rounded-2xl border-2 transition-all duration-200 hover:shadow-md active:scale-[0.97] ${cat.color}`}
            >
              <div className={`p-3 rounded-xl ${cat.iconBg}`}>
                <cat.icon className="h-6 w-6" />
              </div>
              <span className="text-sm font-semibold">{cat.label}</span>
            </button>
          ))}
        </div>
      </div>

      {/* Request Tracking */}
      <div className="card space-y-4">
        <h2 className="text-sm font-bold text-slate-700 flex items-center gap-2">
          <FileText className="h-4 w-4 text-primary-500" />
          Request Tracker
        </h2>

        {loading ? (
          <SkeletonLoader variant="table-row" count={3} />
        ) : requests.length === 0 ? (
          <div className="text-center py-8">
            <Wallet className="h-10 w-10 text-slate-300 mx-auto mb-2" />
            <p className="text-sm text-slate-400">No requests yet</p>
            <p className="text-xs text-slate-300 mt-1">Tap a category above to create one</p>
          </div>
        ) : (
          <div className="space-y-4">
            {Object.entries(grouped).map(([status, items]) =>
              items.length > 0 ? (
                <div key={status}>
                  <p className="text-xs font-semibold text-slate-400 uppercase mb-2">
                    {status} ({items.length})
                  </p>
                  <div className="space-y-2">
                    {items.map((req) => (
                      <div
                        key={req.id || req._id}
                        className="flex items-center justify-between px-3 py-2.5 rounded-xl bg-slate-50"
                      >
                        <div className="flex-1 min-w-0">
                          <p className="text-sm font-medium text-slate-700 truncate">
                            {req.category || req.type}
                          </p>
                          <p className="text-xs text-slate-400">
                            {req.created_at
                              ? format(new Date(req.created_at), 'dd MMM, hh:mm a')
                              : '-'}
                          </p>
                        </div>
                        <div className="flex items-center gap-3">
                          <span className="text-sm font-bold text-slate-800">
                            ₹{req.amount}
                          </span>
                          <StatusBadge status={req.status} />
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              ) : null
            )}
          </div>
        )}
      </div>

      {/* Modal */}
      {activeCategory && (
        <RequestModal
          category={activeCategory}
          onClose={() => setActiveCategory(null)}
          onSubmit={handleSubmit}
        />
      )}
    </div>
  )
}
