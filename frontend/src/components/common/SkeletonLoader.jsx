export default function SkeletonLoader({ variant = 'card', count = 1, className = '' }) {
  const items = Array.from({ length: count }, (_, i) => i)

  const variants = {
    card: () => (
      <div className="rounded-2xl bg-white border border-slate-100 p-6 space-y-4">
        <div className="h-4 w-3/4 rounded-lg shimmer-bg" />
        <div className="h-3 w-full rounded-lg shimmer-bg" />
        <div className="h-3 w-5/6 rounded-lg shimmer-bg" />
        <div className="flex gap-3 pt-2">
          <div className="h-8 w-20 rounded-lg shimmer-bg" />
          <div className="h-8 w-20 rounded-lg shimmer-bg" />
        </div>
      </div>
    ),
    'table-row': () => (
      <div className="flex items-center gap-4 px-4 py-3 border-b border-slate-100">
        <div className="h-10 w-10 rounded-full shimmer-bg shrink-0" />
        <div className="flex-1 space-y-2">
          <div className="h-3.5 w-1/3 rounded shimmer-bg" />
          <div className="h-3 w-1/4 rounded shimmer-bg" />
        </div>
        <div className="h-6 w-16 rounded-full shimmer-bg" />
        <div className="h-8 w-8 rounded-lg shimmer-bg" />
      </div>
    ),
    text: () => (
      <div className="space-y-2.5">
        <div className="h-3.5 w-full rounded shimmer-bg" />
        <div className="h-3.5 w-4/5 rounded shimmer-bg" />
        <div className="h-3.5 w-3/5 rounded shimmer-bg" />
      </div>
    ),
    avatar: () => (
      <div className="flex items-center gap-3">
        <div className="h-12 w-12 rounded-full shimmer-bg" />
        <div className="space-y-2">
          <div className="h-3.5 w-28 rounded shimmer-bg" />
          <div className="h-3 w-20 rounded shimmer-bg" />
        </div>
      </div>
    ),
  }

  const Skeleton = variants[variant] || variants.card

  return (
    <div className={`space-y-3 animate-pulse ${className}`}>
      {items.map((i) => (
        <div key={i}>
          <Skeleton />
        </div>
      ))}
    </div>
  )
}
