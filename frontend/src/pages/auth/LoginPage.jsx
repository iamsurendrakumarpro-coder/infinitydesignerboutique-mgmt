import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../../context/AuthContext'
import NumberPad from '../../components/common/NumberPad'
import { Phone, Gem, AlertCircle, Loader2 } from 'lucide-react'

export default function LoginPage() {
  const [step, setStep] = useState('phone')
  const [phone, setPhone] = useState('')
  const [pin, setPin] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const { login } = useAuth()
  const navigate = useNavigate()

  function formatPhone(val) {
    const digits = val.replace(/\D/g, '').slice(0, 10)
    if (digits.length <= 3) return digits
    if (digits.length <= 6) return `${digits.slice(0, 3)} ${digits.slice(3)}`
    return `${digits.slice(0, 3)} ${digits.slice(3, 6)} ${digits.slice(6)}`
  }

  function handlePhoneChange(e) {
    const raw = e.target.value.replace(/\D/g, '').slice(0, 10)
    setPhone(raw)
    setError('')
  }

  function handlePhoneSubmit(e) {
    e.preventDefault()
    if (phone.length !== 10) {
      setError('Please enter a valid 10-digit phone number')
      return
    }
    setStep('pin')
    setError('')
  }

  async function handlePinSubmit() {
    if (pin.length < 4) {
      setError('PIN must be at least 4 digits')
      return
    }
    setLoading(true)
    setError('')
    try {
      const user = await login(phone, pin)
      if (navigator.vibrate) navigator.vibrate(50)
      if (user.must_change_pin || user.is_first_login) {
        navigate('/change-pin')
      } else if (user.role === 'admin' || user.role === 'root_admin') {
        navigate('/admin')
      } else {
        navigate('/staff')
      }
    } catch (err) {
      const msg = err.response?.data?.error || err.response?.data?.message || 'Login failed. Please try again.'
      setError(msg)
      setPin('')
      if (navigator.vibrate) navigator.vibrate([100, 50, 100])
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen gradient-hero flex items-center justify-center p-4">
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute -top-40 -right-40 h-80 w-80 rounded-full bg-primary-400/10 blur-3xl" />
        <div className="absolute -bottom-40 -left-40 h-80 w-80 rounded-full bg-accent-400/10 blur-3xl" />
      </div>

      <div className="relative w-full max-w-sm animate-scale-in">
        {/* Brand */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center h-16 w-16 rounded-2xl bg-white/10 backdrop-blur-lg mb-4 border border-white/20">
            <Gem className="h-8 w-8 text-accent-300" />
          </div>
          <h1 className="text-2xl font-bold text-white tracking-tight">Infinity Designer</h1>
          <p className="text-primary-200 text-sm mt-1">Boutique Management System</p>
        </div>

        {/* Card */}
        <div className="bg-white rounded-3xl shadow-2xl p-6 space-y-5">
          {step === 'phone' ? (
            <form onSubmit={handlePhoneSubmit} className="space-y-5">
              <div>
                <h2 className="text-lg font-bold text-slate-800">Welcome back</h2>
                <p className="text-sm text-slate-500 mt-0.5">Enter your phone number to sign in</p>
              </div>

              <div>
                <label className="label">Phone Number</label>
                <div className="relative">
                  <div className="absolute left-3.5 top-1/2 -translate-y-1/2 flex items-center gap-1.5 text-slate-400">
                    <Phone className="h-4 w-4" />
                    <span className="text-sm font-medium text-slate-500">+91</span>
                  </div>
                  <input
                    type="tel"
                    value={formatPhone(phone)}
                    onChange={handlePhoneChange}
                    placeholder="000 000 0000"
                    className="input-field pl-[72px] text-lg tracking-wider font-medium"
                    autoFocus
                    inputMode="numeric"
                  />
                </div>
              </div>

              {error && (
                <div className="flex items-center gap-2 text-danger-600 text-sm bg-danger-50 rounded-xl px-3 py-2.5">
                  <AlertCircle className="h-4 w-4 shrink-0" />
                  {error}
                </div>
              )}

              <button
                type="submit"
                className="btn-primary w-full"
                disabled={phone.length !== 10}
              >
                Continue
              </button>
            </form>
          ) : (
            <div className="space-y-5">
              <div>
                <h2 className="text-lg font-bold text-slate-800">Enter your PIN</h2>
                <p className="text-sm text-slate-500 mt-0.5">
                  Signing in as{' '}
                  <button
                    onClick={() => {
                      setStep('phone')
                      setPin('')
                      setError('')
                    }}
                    className="text-primary-600 font-medium hover:underline"
                  >
                    +91 {formatPhone(phone)}
                  </button>
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
                  <p className="text-sm text-slate-500">Signing in...</p>
                </div>
              ) : (
                <NumberPad
                  value={pin}
                  onChange={setPin}
                  onSubmit={handlePinSubmit}
                  maxLength={6}
                />
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
