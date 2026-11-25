import { useEffect, useState } from 'react'
import api, { AnalyticsResponse } from '../lib/api'
import { useAuth } from '../context/AuthContext'
import { filtersToPayload, useFilters } from '../context/FilterContext'
import KPICard from '../components/KPICard'
import ChartPanel from '../components/ChartPanel'
import EmptyState from '../components/EmptyState'
import { Search } from 'lucide-react'

interface Props {
  title: string
  endpoint: string
  method?: 'get' | 'post'
  emptyMessage?: string
  showTable?: boolean
}

export default function AnalyticsPage({
  title,
  endpoint,
  method = 'post',
  emptyMessage = 'Required data has not been uploaded.',
  showTable = false,
}: Props) {
  const { activeBusiness } = useAuth()
  const { filters } = useFilters()
  const [data, setData] = useState<AnalyticsResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [searchTerm, setSearchTerm] = useState('')

  useEffect(() => {
    if (!activeBusiness) {
      setLoading(false)
      return
    }
    setLoading(true)
    const req =
      method === 'get'
        ? api.get<AnalyticsResponse>(endpoint)
        : api.post<AnalyticsResponse>(endpoint, filtersToPayload(filters))

    req
      .then(({ data: d }) => setData(d))
      .catch(() => setData(null))
      .finally(() => setLoading(false))
  }, [activeBusiness, filters, endpoint, method])

  if (!activeBusiness) {
    return <EmptyState title="No Business Selected" message="Select or create a business." />
  }

  if (loading) return <div className="card h-64 animate-pulse bg-slate-100 min-w-0" />

  const unavailable = data?.kpis?.length && data.kpis.every((k) => k.unavailable_reason)

  return (
    <div className="space-y-6 min-w-0">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-textPrimary">{title}</h1>
      </div>

      {unavailable ? (
        <EmptyState title="Analytics Module Unavailable" message={data?.kpis[0]?.unavailable_reason || emptyMessage} />
      ) : (
        <>
          {data?.kpis.length ? (
            <div className="grid grid-cols-2 gap-4 md:grid-cols-3 lg:grid-cols-5">
              {data.kpis.map((kpi) => (
                <KPICard key={kpi.key} kpi={kpi} currency={activeBusiness.currency} />
              ))}
            </div>
          ) : null}

          <div className="grid gap-6 lg:grid-cols-2 min-w-0">
            {data?.charts.map((c) => (
              <ChartPanel key={c.name} name={c.name} data={c.data} />
            ))}
          </div>

          {showTable && data?.tables?.map((t) => {
            const keys = Object.keys(t.rows[0] || {})
            const filteredRows = t.rows.filter((r) =>
              Object.values(r).some((val) =>
                String(val ?? '').toLowerCase().includes(searchTerm.toLowerCase())
              )
            )

            return (
              <div key={t.name} className="card space-y-4">
                <div className="flex flex-wrap items-center justify-between gap-4 border-b border-surface-border pb-3">
                  <h3 className="text-sm font-semibold capitalize text-textPrimary">{t.name.replace(/_/g, ' ')}</h3>
                  <div className="relative w-full sm:w-64">
                    <Search size={16} className="absolute left-3 top-2.5 text-textTertiary" />
                    <input
                      type="text"
                      placeholder="Search table..."
                      className="input pl-9 text-xs py-1.5"
                      value={searchTerm}
                      onChange={(e) => setSearchTerm(e.target.value)}
                    />
                  </div>
                </div>

                <div className="table-scroll-container">
                  <table className="w-full text-left text-xs">
                    <thead>
                      <tr className="border-b border-surface-border bg-surface text-textSecondary uppercase font-medium">
                        {keys.map((k) => (
                          <th key={k} className="px-3 py-2.5 min-w-[120px]">
                            {k.replace(/_/g, ' ')}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-surface-border">
                      {filteredRows.slice(0, 50).map((row, i) => (
                        <tr key={i} className="hover:bg-surface transition-colors">
                          {Object.entries(row).map(([k, v], j) => {
                            const isNumeric = typeof v === 'number'
                            const strVal = String(v ?? '')
                            return (
                              <td
                                key={j}
                                title={strVal}
                                className={`px-3 py-2.5 max-w-[200px] truncate-cell ${
                                  isNumeric ? 'tabular-nums font-medium text-textPrimary' : 'text-textSecondary'
                                }`}
                              >
                                {isNumeric && (k.includes('revenue') || k.includes('cost') || k.includes('price') || k.includes('profit'))
                                  ? `₹${(v as number).toLocaleString('en-IN')}`
                                  : strVal}

                              </td>
                            )
                          })}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )
          })}
        </>
      )}
    </div>
  )
}
