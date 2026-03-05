import { Delete, CornerDownLeft } from 'lucide-react'

function triggerHaptic() {
  if (navigator.vibrate) {
    navigator.vibrate(30)
  }
}

export default function NumberPad({ value = '', onChange, onSubmit, maxLength = 6 }) {
  const keys = [
    ['1', '2', '3'],
    ['4', '5', '6'],
    ['7', '8', '9'],
    ['', '0', 'back'],
  ]

  function handlePress(key) {
    triggerHaptic()
    if (key === 'back') {
      onChange(value.slice(0, -1))
    } else if (key === 'enter') {
      onSubmit?.()
    } else if (value.length < maxLength) {
      onChange(value + key)
    }
  }

  return (
    <div className="space-y-3">
      {/* PIN Display */}
      <div className="flex justify-center gap-2.5 py-4">
        {Array.from({ length: maxLength }, (_, i) => (
          <div
            key={i}
            className={`h-3.5 w-3.5 rounded-full border-2 transition-all duration-200 ${
              i < value.length
                ? 'bg-primary-600 border-primary-600 scale-110'
                : 'border-slate-300 bg-white'
            }`}
          />
        ))}
      </div>

      {/* Number Grid */}
      <div className="grid grid-cols-3 gap-2.5 max-w-[280px] mx-auto">
        {keys.flat().map((key, idx) => {
          if (key === '') {
            return <div key={idx} />
          }
          if (key === 'back') {
            return (
              <button
                key={idx}
                type="button"
                onClick={() => handlePress('back')}
                className="flex items-center justify-center h-[60px] w-full rounded-2xl bg-slate-100 text-slate-600 text-lg font-semibold transition-all duration-150 hover:bg-slate-200 active:scale-95 active:bg-slate-300"
              >
                <Delete className="h-5 w-5" />
              </button>
            )
          }
          return (
            <button
              key={idx}
              type="button"
              onClick={() => handlePress(key)}
              className="flex items-center justify-center h-[60px] w-full rounded-2xl bg-white border border-slate-200 text-slate-800 text-xl font-semibold transition-all duration-150 hover:bg-primary-50 hover:border-primary-300 active:scale-95 active:bg-primary-100 shadow-sm"
            >
              {key}
            </button>
          )
        })}
      </div>

      {/* Enter Button */}
      <div className="max-w-[280px] mx-auto pt-1">
        <button
          type="button"
          onClick={() => {
            triggerHaptic()
            onSubmit?.()
          }}
          disabled={value.length < 4}
          className="w-full h-[52px] rounded-2xl gradient-primary text-white font-semibold text-base flex items-center justify-center gap-2 transition-all duration-200 hover:opacity-90 active:scale-[0.98] disabled:opacity-40 disabled:active:scale-100 shadow-lg shadow-primary-600/25"
        >
          <CornerDownLeft className="h-4.5 w-4.5" />
          Confirm
        </button>
      </div>
    </div>
  )
}
