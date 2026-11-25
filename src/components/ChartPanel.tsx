import { useState } from 'react'
import { createPortal } from 'react-dom'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { Table as TableIcon, X } from 'lucide-react'
import EmptyState from './EmptyState'
import { formatCurrency, formatNumber } from '../lib/formatters'

interface Props {
  name: string
  data: Record<string, unknown>[]
}

const CustomTooltip = ({ active, payload, label }: any) => {
  if (active && payload && payload.length) {
    return (
      <div className="rounded-lg border border-slate-200 bg-white p-3 shadow-lg">
        <div className="text-xs font-semibold text-textSecondary">{label}</div>
        {payload.map((entry: any, index: number) => {
          const isRev = String(entry.name).toLowerCase().includes('revenue') || String(entry.dataKey).toLowerCase().includes('revenue')
          return (
            <div key={index} className="mt-1 flex items-center justify-between gap-4 text-xs font-medium tabular-nums text-textPrimary">
              <div className="flex items-center gap-1.5">
                <span className="h-2 w-2 rounded-full" style={{ backgroundColor: entry.color || '#0a0a0a' }} />
                <span className="capitalize">{entry.name}:</span>
              </div>
              <span>
                {typeof entry.value === 'number'
                  ? isRev
                    ? formatCurrency(entry.value)
                    : formatNumber(entry.value)
                  : String(entry.value)}
              </span>
            </div>
          )
        })}
      </div>
    )
  }
  return null
}

export default function ChartPanel({ name, data }: Props) {
  const [showTableModal, setShowTableModal] = useState(false)

  if (!data?.length) {
    return (
      <div className="card flex h-[320px] items-center justify-center min-w-0">
        <EmptyState title="No Chart Data" message={`Not enough data to display ${name.replace(/_/g, ' ')}.`} />
      </div>
    )
  }

  const title = name.replace(/_/g, ' ').replace(/\b\w/g, (l) => l.toUpperCase())
  const isLineChart = name.includes('revenue') || name.includes('orders') || name.includes('forecast')
  const isOrders = name.includes('orders')
  const lineKey = isOrders ? 'orders' : name.includes('forecast') ? 'forecast_revenue' : 'revenue'

  const dataKey = data[0]?.revenue != null ? 'revenue' : data[0]?.count != null ? 'count' : 'spend'
  const xKey = data[0]?.period
    ? 'period'
    : data[0]?.product
    ? 'product'
    : data[0]?.channel
    ? 'channel'
    : data[0]?.segment
    ? 'segment'
    : 'category'

  const allKeys = data.length ? Object.keys(data[0]) : []

  return (
    <div className="card min-w-0 overflow-hidden flex flex-col justify-between">
      <div className="mb-4 flex items-center justify-between gap-2">
        <h3 className="text-sm font-semibold text-textPrimary truncate">{title}</h3>
        <button
          onClick={() => setShowTableModal(true)}
          className="flex items-center gap-1 text-xs font-medium text-textSecondary hover:text-black border border-surface-border rounded px-2.5 py-1 bg-surface hover:bg-white transition shrink-0"
        >
          <TableIcon size={13} />
          <span>Tabular Data</span>
        </button>
      </div>

      <div className="h-[260px] w-full min-w-0">
        <ResponsiveContainer width="100%" height="100%">
          {isLineChart ? (
            <LineChart data={data} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" vertical={false} />
              <XAxis
                dataKey="period"
                tick={{ fontSize: 11, fill: '#6b6b6b' }}
                tickFormatter={(v: any) => String(v).slice(0, 10)}
                dy={5}
              />
              <YAxis tick={{ fontSize: 11, fill: '#6b6b6b' }} dx={-5} />
              <Tooltip content={<CustomTooltip />} />
              <Line
                type="monotone"
                dataKey={lineKey}
                name={title}
                stroke="#0a0a0a"
                strokeWidth={2}
                dot={false}
                activeDot={{ r: 5, fill: '#0a0a0a' }}
              />
            </LineChart>
          ) : (
            <BarChart data={data.slice(0, 15)} margin={{ top: 10, right: 10, left: -20, bottom: 20 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" vertical={false} />
              <XAxis
                dataKey={xKey}
                tick={{ fontSize: 10, fill: '#6b6b6b' }}
                interval={0}
                angle={-15}
                textAnchor="end"
              />
              <YAxis tick={{ fontSize: 11, fill: '#6b6b6b' }} />
              <Tooltip content={<CustomTooltip />} />
              <Bar dataKey={dataKey} name={title} fill="#171717" radius={[4, 4, 0, 0]} />
            </BarChart>
          )}
        </ResponsiveContainer>
      </div>

      {/* Tabular Data Modal — Mounted via Portal to document.body to avoid parent CSS transform clipping/glitching */}
      {showTableModal &&
        createPortal(
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 backdrop-blur-sm animate-fadeIn">
            <div className="w-full max-w-3xl rounded-xl bg-white p-6 shadow-2xl space-y-4 max-h-[85vh] flex flex-col border border-surface-border">
              <div className="flex items-center justify-between border-b border-surface-border pb-3">
                <div>
                  <h3 className="text-base font-bold text-textPrimary">{title} — Tabular Data</h3>
                  <p className="text-xs text-textSecondary">{data.length} total data points</p>
                </div>
                <button
                  onClick={() => setShowTableModal(false)}
                  className="rounded-lg p-1.5 text-textSecondary hover:bg-surface hover:text-textPrimary transition"
                >
                  <X size={18} />
                </button>
              </div>

              <div className="flex-1 overflow-auto border border-surface-border rounded-lg">
                <table className="w-full text-left text-xs">
                  <thead className="bg-surface text-textSecondary uppercase font-semibold sticky top-0 border-b border-surface-border">
                    <tr>
                      {allKeys.map((k) => (
                        <th key={k} className="px-4 py-2.5 capitalize">
                          {k.replace(/_/g, ' ')}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-surface-border tabular-nums font-medium text-textPrimary">
                    {data.map((row, idx) => (
                      <tr key={idx} className="hover:bg-surface transition-colors">
                        {allKeys.map((k) => {
                          const v = row[k]
                          const isNum = typeof v === 'number'
                          const isRev = k.includes('revenue') || k.includes('spend') || k.includes('price') || k.includes('cost') || k.includes('aov') || k.includes('cac')
                          const formatted = isNum
                            ? isRev
                              ? formatCurrency(v as number)
                              : formatNumber(v as number)
                            : String(v ?? '—')

                          return (
                            <td key={k} className={`px-4 py-2.5 ${isNum ? 'font-bold text-textPrimary' : 'text-textSecondary'}`}>
                              {formatted}
                            </td>
                          )
                        })}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              <div className="flex justify-end pt-2">
                <button onClick={() => setShowTableModal(false)} className="btn-secondary text-xs">
                  Close
                </button>
              </div>
            </div>
          </div>,
          document.body
        )}
    </div>
  )
}
