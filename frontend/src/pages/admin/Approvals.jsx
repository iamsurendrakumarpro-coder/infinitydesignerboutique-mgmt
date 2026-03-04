import { useState, useEffect, useCallback } from 'react'
import * as financialService from '../../services/financial'
import * as overtimeService from '../../services/overtime'
import SkeletonLoader from '../../components/common/SkeletonLoader'
import StatusBadge from '../../components/common/StatusBadge'
import {
  ClipboardCheck,
  Clock,
  IndianRupee,
  CheckCircle2,
  XCircle,
  AlertCircle,
  MessageSquare,
  User,
} from 'lucide-react'
import { format } from 'date-fns'

function ApprovalCard({ item, type, onApprove, onReject, processing }) {
  const [notes, setNotes] = useState('')
  const [showNotes, setShowNotes] = useState(false)

  const id = item.id || item._id
  const isProcessing = processing === id

  return (
    <div className="card-hover space-y-3">
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-3">
          <div className={`p-2 rounded-xl ${type === 'financial' ? 'bg-amber-50' : 'bg-violet-50'}`}>
            {type === 'financial' ? (
              <IndianRupee className={`h-4 w-4 ${type === 'financial' ? 'text-amber-600' : 'text-violet-600'}`} />
            ) : (
              <Clock className="h-4 w-4 text-violet-600" />
            )}
          </div>
          <div>
            <p className="text-sm font-semibold text-slate-800">
              {item.staff_name || item.staffName || item.employee_name || 'Staff'}
            </p>
            <p className="text-xs text-slate-400">
              {item.created_at ? format(new Date(item.created_at), 'dd MMM yyyy, hh:mm a') : ''}
            </p>
          </div>
        </div>
        <StatusBadge status={item.status || 'pending'} />
      </div>

      <div className="px-3 py-2.5 rounded-xl bg-slate-50 space-y-1">
        {type === 'financial' ? (
          <>
            <div className="flex items-center justify-between">
              <span className="text-xs text-slate-500 capitalize">{item.type?.replace('_', ' ')} — {item.category}</span>
              <span className="text-base font-bold text-slate-800">₹{item.amount}</span>
            </div>
            {item.notes && <p className="text-xs text-slate-500">{item.notes}</p>}
            {item.type === 'personal_advance' && item.week_earned !== undefined && (
              <p className="text-xs text-primary-600 font-medium">Week-to-date Earned: ₹{item.week_earned}</p>
            )}
          </>
        ) : (
          <>
            <div className="flex items-center justify-between">
              <span className="text-xs text-slate-500">
                {item.date ? format(new Date(item.date), 'dd MMM yyyy') : ''}
              </span>
              <span className="text-base font-bold text-slate-800">{item.extra_hours || item.hours} hrs</span>
            </div>
            {item.calculated_payout !== undefined && (
              <p className="text-xs text-emerald-600 font-medium">Payout: ₹{item.calculated_payout}</p>
            )}
          </>
        )}
      </div>

      {showNotes && (
        <div>
          <textarea
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder="Add a note (optional)..."
            className="input-field resize-none text-sm"
            rows={2}
          />
        </div>
      )}

      {item.status === 'pending' && (
        <div className="flex items-center gap-2">
          {!showNotes && (
            <button
              onClick={() => setShowNotes(true)}
              className="p-2 rounded-lg text-slate-400 hover:text-primary-600 hover:bg-primary-50 transition-colors"
              title="Add note"
            >
              <MessageSquare className="h-4 w-4" />
            </button>
          )}
          <div className="flex-1" />
          <button
            onClick={() => onReject(id, notes)}
            disabled={isProcessing}
            className="btn-ghost !text-danger-600 hover:!bg-danger-50 !py-2 !px-4 !text-xs"
          >
            <XCircle className="h-3.5 w-3.5" />
            Reject
          </button>
          <button
            onClick={() => onApprove(id, notes)}
            disabled={isProcessing}
            className="btn-primary !py-2 !px-4 !text-xs"
          >
            {isProcessing ? (
              <div className="h-3.5 w-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
            ) : (
              <CheckCircle2 className="h-3.5 w-3.5" />
            )}
            Approve
          </button>
        </div>
      )}
    </div>
  )
}

export default function Approvals() {
  const [tab, setTab] = useState('financial')
  const [financialRequests, setFinancialRequests] = useState([])
  const [overtimeRequests, setOvertimeRequests] = useState([])
  const [loading, setLoading] = useState(true)
  const [processing, setProcessing] = useState(null)
  const [success, setSuccess] = useState('')

  const fetchData = useCallback(async () => {
    try {
      const [fin, ot] = await Promise.allSettled([
        financialService.getRequests(),
        overtimeService.getPending(),
      ])
      if (fin.status === 'fulfilled') {
        const d = fin.value
        setFinancialRequests(Array.isArray(d) ? d : d.requests || [])
      }
      if (ot.status === 'fulfilled') {
        const d = ot.value
        setOvertimeRequests(Array.isArray(d) ? d : d.overtime || [])
      }
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchData()
  }, [fetchData])

  async function handleFinancialApprove(id, notes) {
    setProcessing(id)
    try {
      await financialService.approveRequest(id, notes)
      setSuccess('Request approved')
      fetchData()
      setTimeout(() => setSuccess(''), 3000)
    } catch {
      // Handle error
    } finally {
      setProcessing(null)
    }
  }

  async function handleFinancialReject(id, notes) {
    setProcessing(id)
    try {
      await financialService.rejectRequest(id, notes)
      setSuccess('Request rejected')
      fetchData()
      setTimeout(() => setSuccess(''), 3000)
    } catch {
      // Handle error
    } finally {
      setProcessing(null)
    }
  }

  async function handleOTApprove(id, notes) {
    setProcessing(id)
    try {
      await overtimeService.approve(id, notes)
      setSuccess('Overtime approved')
      fetchData()
      setTimeout(() => setSuccess(''), 3000)
    } catch {
      // Handle error
    } finally {
      setProcessing(null)
    }
  }

  async function handleOTReject(id, notes) {
    setProcessing(id)
    try {
      await overtimeService.reject(id, notes)
      setSuccess('Overtime rejected')
      fetchData()
      setTimeout(() => setSuccess(''), 3000)
    } catch {
      // Handle error
    } finally {
      setProcessing(null)
    }
  }

  const pendingFinancial = financialRequests.filter((r) => r.status === 'pending')
  const pendingOT = overtimeRequests.filter((r) => r.status === 'pending')

  return (
    <div className="space-y-6 animate-slide-up">
      <div>
        <h1 className="text-2xl font-bold text-slate-800">Approvals</h1>
        <p className="text-sm text-slate-500 mt-0.5">Review and process pending requests</p>
      </div>

      {success && (
        <div className="flex items-center gap-2 text-success-700 text-sm bg-success-50 rounded-xl px-4 py-3">
          <CheckCircle2 className="h-4 w-4 shrink-0" />
          {success}
        </div>
      )}

      {/* Tabs */}
      <div className="flex gap-1 p-1 bg-slate-100 rounded-xl">
        <button
          onClick={() => setTab('financial')}
          className={`flex-1 flex items-center justify-center gap-2 py-2.5 rounded-lg text-sm font-semibold transition-all ${
            tab === 'financial' ? 'bg-white text-primary-700 shadow-sm' : 'text-slate-500 hover:text-slate-700'
          }`}
        >
          <IndianRupee className="h-4 w-4" />
          Financial
          {pendingFinancial.length > 0 && (
            <span className="px-1.5 py-0.5 rounded-full bg-amber-100 text-amber-700 text-[10px] font-bold">
              {pendingFinancial.length}
            </span>
          )}
        </button>
        <button
          onClick={() => setTab('overtime')}
          className={`flex-1 flex items-center justify-center gap-2 py-2.5 rounded-lg text-sm font-semibold transition-all ${
            tab === 'overtime' ? 'bg-white text-primary-700 shadow-sm' : 'text-slate-500 hover:text-slate-700'
          }`}
        >
          <Clock className="h-4 w-4" />
          Overtime
          {pendingOT.length > 0 && (
            <span className="px-1.5 py-0.5 rounded-full bg-violet-100 text-violet-700 text-[10px] font-bold">
              {pendingOT.length}
            </span>
          )}
        </button>
      </div>

      {loading ? (
        <SkeletonLoader variant="card" count={3} />
      ) : tab === 'financial' ? (
        financialRequests.length === 0 ? (
          <div className="card text-center py-12">
            <ClipboardCheck className="h-12 w-12 text-slate-300 mx-auto mb-3" />
            <p className="text-sm font-medium text-slate-500">No financial requests</p>
            <p className="text-xs text-slate-400 mt-1">All caught up!</p>
          </div>
        ) : (
          <div className="space-y-3">
            {financialRequests.map((req) => (
              <ApprovalCard
                key={req.id || req._id}
                item={req}
                type="financial"
                onApprove={handleFinancialApprove}
                onReject={handleFinancialReject}
                processing={processing}
              />
            ))}
          </div>
        )
      ) : overtimeRequests.length === 0 ? (
        <div className="card text-center py-12">
          <Clock className="h-12 w-12 text-slate-300 mx-auto mb-3" />
          <p className="text-sm font-medium text-slate-500">No overtime requests</p>
          <p className="text-xs text-slate-400 mt-1">All caught up!</p>
        </div>
      ) : (
        <div className="space-y-3">
          {overtimeRequests.map((req) => (
            <ApprovalCard
              key={req.id || req._id}
              item={req}
              type="overtime"
              onApprove={handleOTApprove}
              onReject={handleOTReject}
              processing={processing}
            />
          ))}
        </div>
      )}
    </div>
  )
}
