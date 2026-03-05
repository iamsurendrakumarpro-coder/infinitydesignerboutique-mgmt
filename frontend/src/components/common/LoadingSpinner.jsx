import { Loader2 } from 'lucide-react'

export default function LoadingSpinner({ message = 'Loading...', size = 'md', className = '' }) {
  const sizes = {
    sm: 'h-4 w-4',
    md: 'h-8 w-8',
    lg: 'h-12 w-12',
  }

  return (
    <div className={`flex flex-col items-center justify-center gap-3 py-12 ${className}`}>
      <Loader2 className={`${sizes[size]} text-primary-600 animate-spin`} />
      {message && <p className="text-sm text-slate-500 font-medium">{message}</p>}
    </div>
  )
}
