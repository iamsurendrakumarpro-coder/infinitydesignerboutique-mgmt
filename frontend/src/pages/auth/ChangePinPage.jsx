import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../../context/AuthContext'
import * as authService from '../../services/auth'
import NumberPad from '../../components/common/NumberPad'
import { ShieldCheck, AlertCircle, Loader2, CheckCircle2 } from 'lucide-react'

export default function ChangePinPage() {
  const [step, setStep] = useState('current') // current | new | confirm
  const [currentPin, setCurrentPin] = useState('')
  const [newPin, setNewPin] = useState('')
  const [confirmPin, setConfirmPin] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const { completePinChange, user, isAdmin } = useAuth()
  const navigate = useNavigate()

  function handleCurrentSubmit() {
    if (currentPin.length < 4) {
      setError('PIN must be at least 4 digits')
      return
    }
    setError('')
    setStep('new')
  }

  function handleNewSubmit() {
    if (newPin.length < 4) {
      setError('PIN must be at least 4 digits')
      return
    }
    setError('')
    setStep('confirm')
  }

  async function handleConfirmSubmit() {
    if (confirmPin !== newPin) {
      setError('PINs do not match. Please try again.')
      setConfirmPin('')
      return
    }
    setLoading(true)
    setError('')
    try {
      await authService.changePin(currentPin, newPin, confirmPin)
      completePinChange()
      if (navigator.vibrate) navigator.vibrate(50)
      if (isAdmin) {
        navigate('/admin')
      } else {
        navigate('/staff')
      }
    } catch (err) {
      const msg = err.response?.data?.error || err.response?.data?.message || 'Failed to change PIN'
      setError(msg)
      setConfirmPin('')
      if (navigator.vibrate) navigator.vibrate([100, 50, 100])
    } finally {
      setLoading(false)
    }
  }

  const steps = [
    { key: 'current', label: 'Current PIN' },
    { key: 'new', label: 'New PIN' },
    { key: 'confirm', label: 'Confirm' },
  ]
  const currentStepIndex = steps.findIndex((s) => s.key === step)

  return (
    <div className="min-h-screen gradient-hero flex items-center justify-center p-4">
      <div className="w-full max-w-sm animate-scale-in">
        {/* Icon */}
        <div className="text-center mb-6">
          <div className="inline-flex items-center justify-center h-16 w-16 rounded-2xl bg-white/10 backdrop-blur-lg mb-3 border border-white/20">
            <ShieldCheck className="h-8 w-8 text-accent-300" />
          </div>
          <h1 className="text-xl font-bold text-white">Change Your PIN</h1>
          <p className="text-sm text-primary-200 mt-1">
            {user?.is_first_login
              ? "For security, please set a new PIN for your account."
              : "Update your PIN to keep your account secure."}
          </p>
        </div>

        {/* Progress */}
        <div className="flex items-center justify-center gap-2 mb-6">
          {steps.map((s, i) => (
            <div key={s.key} className="flex items-center gap-2">
              <div
                className={`h-2 w-2 rounded-full transition-all ${
                  i <= currentStepIndex ? 'bg-accent-400 scale-125' : 'bg-white/30'
                }`}
              />
              {i < steps.length - 1 && (
                <div
                  className={`h-0.5 w-6 rounded transition-all ${
                    i < currentStepIndex ? 'bg-accent-400' : 'bg-white/20'
                  }`}
                />
              )}
            </div>
          ))}
        </div>

        {/* Card */}
        <div className="bg-white rounded-3xl shadow-2xl p-6 space-y-4">
          <div>
            <h2 className="text-base font-bold text-slate-800">
              {step === 'current' && 'Enter Current PIN'}
              {step === 'new' && 'Create New PIN'}
              {step === 'confirm' && 'Confirm New PIN'}
            </h2>
            <p className="text-sm text-slate-500 mt-0.5">
              {step === 'current' && 'Enter the PIN you used to sign in'}
              {step === 'new' && 'Choose a secure 4-6 digit PIN'}
              {step === 'confirm' && 'Re-enter your new PIN to confirm'}
            </p>
          </div>

          {error && (
            <div className="flex items-center gap-2 text-danger-600 text-sm bg-danger-50 rounded-xl px-3 py-2.5">
              <AlertCircle className="h-4 w-4 shrink-0" />
              {error}
            </div>
          )}

          {loading ? (
            <div className="flex flex-col items-center justify-center py-12 gap-3">
              <Loader2 className="h-8 w-8 text-primary-600 animate-spin" />
              <p className="text-sm text-slate-500">Updating PIN...</p>
            </div>
          ) : (
            <>
              {step === 'current' && (
                <NumberPad value={currentPin} onChange={setCurrentPin} onSubmit={handleCurrentSubmit} />
              )}
              {step === 'new' && (
                <NumberPad value={newPin} onChange={setNewPin} onSubmit={handleNewSubmit} />
              )}
              {step === 'confirm' && (
                <NumberPad value={confirmPin} onChange={setConfirmPin} onSubmit={handleConfirmSubmit} />
              )}
            </>
          )}
        </div>
      </div>
    </div>
  )
}
