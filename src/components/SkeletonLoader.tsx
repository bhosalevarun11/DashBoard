import { motion } from 'framer-motion'

export function KPICardSkeleton() {
  return (
    <div className="card h-28 flex flex-col justify-between animate-pulse bg-slate-50 border border-slate-200/80">
      <div className="flex justify-between items-center">
        <div className="h-3.5 w-24 bg-slate-200 rounded" />
        <div className="h-4 w-12 bg-slate-200 rounded-full" />
      </div>
      <div className="h-7 w-32 bg-slate-300 rounded" />
      <div className="h-3 w-20 bg-slate-100 rounded" />
    </div>
  )
}

export function ChartPanelSkeleton() {
  return (
    <div className="card h-[320px] flex flex-col justify-between animate-pulse bg-slate-50 border border-slate-200/80">
      <div className="flex justify-between items-center pb-3 border-b border-slate-100">
        <div className="h-4 w-40 bg-slate-200 rounded" />
        <div className="h-3 w-16 bg-slate-200 rounded" />
      </div>
      <div className="flex-1 flex items-end space-x-3 pt-6 pb-2">
        <div className="h-[40%] flex-1 bg-slate-200 rounded-t" />
        <div className="h-[70%] flex-1 bg-slate-300 rounded-t" />
        <div className="h-[55%] flex-1 bg-slate-200 rounded-t" />
        <div className="h-[85%] flex-1 bg-slate-300 rounded-t" />
        <div className="h-[60%] flex-1 bg-slate-200 rounded-t" />
        <div className="h-[90%] flex-1 bg-slate-300 rounded-t" />
      </div>
    </div>
  )
}

export function TableSkeleton({ rows = 5, cols = 5 }: { rows?: number; cols?: number }) {
  return (
    <div className="card animate-pulse space-y-4 bg-slate-50 border border-slate-200/80">
      <div className="h-4 w-48 bg-slate-200 rounded" />
      <div className="space-y-3">
        {Array.from({ length: rows }).map((_, rIdx) => (
          <div key={rIdx} className="flex justify-between items-center py-2 border-b border-slate-100">
            {Array.from({ length: cols }).map((_, cIdx) => (
              <div key={cIdx} className="h-3 bg-slate-200 rounded" style={{ width: `${100 / cols - 4}%` }} />
            ))}
          </div>
        ))}
      </div>
    </div>
  )
}

export function FadeContainer({ children }: { children: React.ReactNode }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -6 }}
      transition={{ duration: 0.2, ease: 'easeOut' }}
    >
      {children}
    </motion.div>
  )
}
