export function formatCurrency(value: number | string | null | undefined, currency: string = 'INR'): string {
  if (value == null || value === '' || (typeof value === 'number' && isNaN(value))) return '—'
  const num = typeof value === 'number' ? value : parseFloat(String(value))
  if (isNaN(num)) return '—'
  const symbol = currency === 'USD' ? '$' : currency === 'EUR' ? '€' : '₹'
  const formatted = new Intl.NumberFormat('en-IN', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(num)
  return `${symbol}${formatted}`
}

export function formatNumber(value: number | string | null | undefined): string {
  if (value == null || value === '' || (typeof value === 'number' && isNaN(value))) return '—'
  const num = typeof value === 'number' ? value : parseFloat(String(value))
  if (isNaN(num)) return '—'
  return new Intl.NumberFormat('en-IN').format(num)
}

export function formatPercent(value: number | string | null | undefined): string {
  if (value == null || value === '' || (typeof value === 'number' && isNaN(value))) return '—'
  const num = typeof value === 'number' ? value : parseFloat(String(value))
  if (isNaN(num)) return '—'
  return `${num > 0 ? '+' : ''}${num.toFixed(1)}%`
}

export function formatDate(dateStr: string): string {
  if (!dateStr) return ''
  try {
    const d = new Date(dateStr)
    return d.toLocaleDateString('en-IN', { month: 'short', day: 'numeric', year: 'numeric' })
  } catch {
    return dateStr
  }
}
