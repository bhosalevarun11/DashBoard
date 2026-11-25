import { KPICard as KPICardType } from '../lib/api'
import { Info } from 'lucide-react'
import { formatCurrency, formatNumber } from '../lib/formatters'

interface Props {
  kpi: KPICardType
  currency?: string
  isHero?: boolean
}

// Metrics where a DECREASE is good (green) and an INCREASE is bad (red)
const LOWER_IS_BETTER_KEYS = ['return_rate', 'refund_rate', 'cac', 'churn_rate', 'cogs', 'shipping_cost', 'payment_fee']

export default function KPICard({ kpi, currency = 'INR', isHero = false }: Props) {
  const unavailable = kpi.unavailable_reason || kpi.value === 'N/A' || kpi.value == null

  let displayValue = '—'
  if (!unavailable) {
    if (typeof kpi.value === 'number') {
      if (kpi.format === 'currency') {
        displayValue = formatCurrency(kpi.value, currency)
      } else if (kpi.format === 'percent') {
        displayValue = `${kpi.value.toFixed(1)}%`
      } else {
        displayValue = formatNumber(kpi.value)
      }
    } else {
      displayValue = String(kpi.value)
    }
  }

  const isLowerBetter = LOWER_IS_BETTER_KEYS.includes(kpi.key.toLowerCase())
  const hasChange = !unavailable && kpi.change_pct != null && !isNaN(kpi.change_pct)
  const isPositiveChange = hasChange && kpi.change_pct! >= 0
  const isGoodChange = isLowerBetter ? !isPositiveChange : isPositiveChange

  const valLen = displayValue.length
  let textSizeClass = 'text-xl xl:text-2xl'
  if (valLen >= 15) {
    textSizeClass = 'text-base sm:text-lg xl:text-xl'
  } else if (valLen >= 11) {
    textSizeClass = 'text-lg sm:text-xl xl:text-2xl'
  } else if (isHero) {
    textSizeClass = 'text-2xl xl:text-3xl'
  }

  return (
    <div
      className={`card flex flex-col justify-between p-4 space-y-3 h-full min-w-0 transition-all ${
        isHero ? 'border-black bg-white shadow-sm ring-1 ring-black/5' : ''
      }`}
    >
      {/* Label & Optional Info Icon */}
      <div className="flex items-start justify-between gap-2 min-w-0">
        <span className="text-[11px] font-semibold uppercase tracking-wider text-textSecondary leading-snug break-words">
          {kpi.label}
        </span>
        {kpi.unavailable_reason && (
          <span title={kpi.unavailable_reason} className="text-textTertiary cursor-help shrink-0 mt-0.5">
            <Info size={14} />
          </span>
        )}
      </div>

      {/* Main Content Area */}
      <div className="space-y-2 min-w-0">
        <div
          title={displayValue}
          className={`font-bold tracking-tight text-textPrimary tabular-nums leading-tight truncate ${textSizeClass}`}
          style={{ letterSpacing: '-0.02em' }}
        >
          {displayValue}
        </div>

        {/* Subtitle / Explanatory Line or Comparison Badge */}
        {unavailable ? (
          <div className="text-[11px] font-medium leading-normal text-textTertiary line-clamp-2">
            {kpi.unavailable_reason || 'Data unavailable for selected period.'}
          </div>
        ) : hasChange ? (
          <div className="flex flex-wrap items-center gap-1.5 pt-0.5">
            <span
              className={`inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-semibold tabular-nums border ${
                isGoodChange
                  ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                  : 'bg-red-50 text-red-700 border-red-200'
              }`}
            >
              {isPositiveChange ? '↑' : '↓'} {Math.abs(kpi.change_pct!)}%
            </span>
            <span className="text-[11px] text-textTertiary font-medium">vs prev period</span>
          </div>
        ) : (
          <div className="text-[11px] text-textTertiary font-medium">Current period metric</div>
        )}
      </div>
    </div>
  )
}
