import { FileBarChart2 } from 'lucide-react'

interface Props {
  title: string
  message: string
  action?: React.ReactNode
}

export default function EmptyState({ title, message, action }: Props) {
  return (
    <div className="card flex flex-col items-center justify-center py-12 px-6 text-center">
      <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-surface border border-surface-border text-textPrimary">
        <FileBarChart2 size={24} />
      </div>
      <h3 className="mt-4 text-base font-semibold text-textPrimary">{title}</h3>
      <p className="mt-1.5 max-w-sm text-sm text-textSecondary leading-relaxed">{message}</p>
      {action && <div className="mt-5">{action}</div>}
    </div>
  )
}
