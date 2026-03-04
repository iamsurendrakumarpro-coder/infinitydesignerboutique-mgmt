import { useState, useEffect, useRef, useCallback } from 'react'
import { useAuth } from '../../context/AuthContext'
import * as attendanceService from '../../services/attendance'
import LoadingSpinner from '../../components/common/LoadingSpinner'
import { Clock, LogIn, LogOut, Timer, AlertCircle, CheckCircle2, Sun, Moon } from 'lucide-react'
import { format } from 'date-fns'

function useCurrentTime() {
  const [time, setTime] = useState(new Date())
  useEffect(() => {
    const interval = setInterval(() => setTime(new Date()), 1000)
    return () => clearInterval(interval)
  }, [])
  return time
}

function formatIST(date) {
  return date.toLocaleString('en-IN', { timeZone: 'Asia/Kolkata', hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: true })
}

function formatDateIST(date) {
  return date.toLocaleDateString('en-IN', { timeZone: 'Asia/Kolkata', weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' })
}

function DurationTimer({ punchInTime }) {
  const [elapsed, setElapsed] = useState('')

  useEffect(() => {
    function calc() {
      const start = new Date(punchInTime)
      const diff = Math.floor((Date.now() - start.getTime()) / 1000)
      const hrs = Math.floor(diff / 3600)
      const mins = Math.floor((diff % 3600) / 60)
      const secs = diff % 60
      setElapsed(`${hrs.toString().padStart(2, '0')}:${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`)
    }
    calc()
    const interval = setInterval(calc, 1000)
    return () => clearInterval(interval)
  }, [punchInTime])

  return (
    <div className="flex items-center gap-2 text-2xl font-mono font-bold text-primary-700">
      <Timer className="h-5 w-5" />
      {elapsed}
    </div>
  )
}

export default function DutyStation() {
  const { user } = useAuth()
  const now = useCurrentTime()
  const [status, setStatus] = useState(null)
  const [loading, setLoading] = useState(true)
  const [punching, setPunching] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const punchGuard = useRef(false)

  const fetchStatus = useCallback(async () => {
    try {
      const data = await attendanceService.getStatus()
      setStatus(data)
    } catch {
      setError('Failed to load attendance status')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchStatus()
  }, [fetchStatus])

  async function handlePunch() {
    if (punchGuard.current || punching) return
    punchGuard.current = true
    setPunching(true)
    setError('')
    setSuccess('')

    if (navigator.vibrate) navigator.vibrate(80)

    try {
      await attendanceService.punch()
      setSuccess(status?.is_punched_in ? 'Punched out successfully!' : 'Punched in successfully!')
      await fetchStatus()
      setTimeout(() => setSuccess(''), 3000)
    } catch (err) {
      const msg = err.response?.data?.error || 'Punch failed. Please try again.'
      setError(msg)
      if (navigator.vibrate) navigator.vibrate([100, 50, 100])
    } finally {
      setPunching(false)
      setTimeout(() => { punchGuard.current = false }, 1000)
    }
  }

  const isPunchedIn = status?.is_punched_in
  const hour = now.getHours()
  const greeting = hour < 12 ? 'Good morning' : hour < 17 ? 'Good afternoon' : 'Good evening'
  const GreetingIcon = hour < 17 ? Sun : Moon

  if (loading) return <LoadingSpinner message="Loading duty station..." />

  return (
    <div className="max-w-lg mx-auto space-y-6 animate-slide-up">
      {/* Date & Time */}
      <div className="text-center space-y-1">
        <p className="text-sm text-slate-500 font-medium">{formatDateIST(now)}</p>
        <p className="text-3xl font-bold text-slate-800 font-mono tracking-tight">{formatIST(now)}</p>
      </div>

      {/* Greeting */}
      <div className="flex items-center gap-3 px-4 py-3 rounded-2xl bg-primary-50 border border-primary-100">
        <GreetingIcon className="h-5 w-5 text-accent-600" />
        <div>
          <p className="text-sm font-semibold text-primary-800">
            {greeting}, {user?.full_name?.split(' ')[0] || 'there'}!
          </p>
          <p className="text-xs text-primary-600">
            {isPunchedIn ? "You're on duty" : 'Ready to start your shift?'}
          </p>
        </div>
      </div>

      {/* Messages */}
      {error && (
        <div className="flex items-center gap-2 text-danger-600 text-sm bg-danger-50 rounded-xl px-4 py-3 border border-danger-100">
          <AlertCircle className="h-4 w-4 shrink-0" />
          {error}
        </div>
      )}
      {success && (
        <div className="flex items-center gap-2 text-success-700 text-sm bg-success-50 rounded-xl px-4 py-3 border border-emerald-100">
          <CheckCircle2 className="h-4 w-4 shrink-0" />
          {success}
        </div>
      )}

      {/* Punch Button */}
      <div className="card text-center space-y-5 !py-8">
        {isPunchedIn && status.punch_in_time && (
          <DurationTimer punchInTime={status.punch_in_time} />
        )}

        <button
          onClick={handlePunch}
          disabled={punching}
          className={`relative h-40 w-40 mx-auto rounded-full text-white font-bold text-lg shadow-2xl transition-all duration-300 active:scale-95 disabled:active:scale-100 disabled:opacity-70 ${
            isPunchedIn
              ? 'bg-gradient-to-br from-red-500 to-red-600 shadow-red-500/30 hover:shadow-red-500/50'
              : 'bg-gradient-to-br from-emerald-500 to-emerald-600 shadow-emerald-500/30 hover:shadow-emerald-500/50'
          }`}
        >
          {punching ? (
            <div className="flex flex-col items-center gap-2">
              <div className="h-6 w-6 border-3 border-white/30 border-t-white rounded-full animate-spin" />
              <span className="text-sm">Processing...</span>
            </div>
          ) : (
            <div className="flex flex-col items-center gap-2">
              {isPunchedIn ? (
                <LogOut className="h-8 w-8" />
              ) : (
                <LogIn className="h-8 w-8" />
              )}
              <span>{isPunchedIn ? 'PUNCH OUT' : 'PUNCH IN'}</span>
            </div>
          )}
          {/* Pulse ring */}
          {!punching && (
            <div
              className={`absolute inset-0 rounded-full animate-ping opacity-20 ${
                isPunchedIn ? 'bg-red-400' : 'bg-emerald-400'
              }`}
              style={{ animationDuration: '2s' }}
            />
          )}
        </button>

        <p className="text-xs text-slate-400">
          {isPunchedIn ? 'Tap to end your shift' : 'Tap to start your shift'}
        </p>
      </div>

      {/* Today's History */}
      {status?.today_records && status.today_records.length > 0 && (
        <div className="card space-y-3">
          <h3 className="text-sm font-semibold text-slate-700 flex items-center gap-2">
            <Clock className="h-4 w-4 text-primary-500" />
            Today&apos;s Punches
          </h3>
          <div className="space-y-2">
            {status.today_records.map((record, idx) => (
              <div
                key={idx}
                className="flex items-center justify-between px-3 py-2 rounded-xl bg-slate-50 text-sm"
              >
                <div className="flex items-center gap-2">
                  <div
                    className={`h-2 w-2 rounded-full ${
                      record.type === 'punch_in' ? 'bg-emerald-500' : 'bg-red-500'
                    }`}
                  />
                  <span className="font-medium text-slate-700">
                    {record.type === 'punch_in' ? 'Punch In' : 'Punch Out'}
                  </span>
                </div>
                <span className="text-slate-500 font-mono text-xs">
                  {record.time ? format(new Date(record.time), 'hh:mm a') : '-'}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
