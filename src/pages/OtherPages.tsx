import { useEffect, useState } from 'react'
import api, { Alert, Insight } from '../lib/api'
import { useAuth } from '../context/AuthContext'
import EmptyState from '../components/EmptyState'

const severityColors: Record<string, string> = {
  critical: 'border-red-300 bg-red-50',
  warning: 'border-amber-300 bg-amber-50',
  positive: 'border-emerald-300 bg-emerald-50',
  information: 'border-blue-300 bg-blue-50',
}

export function InsightsPage() {
  const { activeBusiness } = useAuth()
  const [insights, setInsights] = useState<Insight[]>([])

  useEffect(() => {
    if (!activeBusiness) return
    api.post<Insight[]>(`/analytics/insights/${activeBusiness.id}/generate`)
      .then(({ data }) => setInsights(data))
      .catch(() => api.get<Insight[]>(`/analytics/insights/${activeBusiness.id}`).then(({ data }) => setInsights(data)))
  }, [activeBusiness])

  if (!activeBusiness) return <EmptyState title="No business" message="Select a business." />

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Automated Insights</h1>
      {insights.length === 0 ? (
        <EmptyState title="No insights yet" message="Import data to generate business insights from your analytics." />
      ) : (
        <div className="space-y-3">
          {insights.map((i) => (
            <div key={i.id} className="card">
              <div className="text-xs font-medium uppercase text-brand-600">{i.insight_type.replace(/_/g, ' ')}</div>
              <h3 className="mt-1 font-semibold">{i.title}</h3>
              <p className="mt-1 text-sm text-slate-600">{i.description}</p>
              {i.recommended_action && (
                <div className="mt-3 rounded-lg bg-brand-50 px-3 py-2 text-sm">
                  <span className="font-medium">Recommended action:</span> {i.recommended_action}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export function AlertsPage() {
  const { activeBusiness } = useAuth()
  const [alerts, setAlerts] = useState<Alert[]>([])

  useEffect(() => {
    if (!activeBusiness) return
    api.post<Alert[]>(`/analytics/alerts/${activeBusiness.id}/generate`)
      .then(({ data }) => setAlerts(data))
      .catch(() => api.get<Alert[]>(`/analytics/alerts/${activeBusiness.id}`).then(({ data }) => setAlerts(data)))
  }, [activeBusiness])

  if (!activeBusiness) return <EmptyState title="No business" message="Select a business." />

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Alert Center</h1>
      {alerts.length === 0 ? (
        <EmptyState title="No alerts" message="Alerts will appear when inventory, sales, or other metrics need attention." />
      ) : (
        <div className="space-y-3">
          {alerts.map((a) => (
            <div key={a.id} className={`card border-l-4 ${severityColors[a.severity] || ''}`}>
              <div className="text-xs font-medium uppercase">{a.severity}</div>
              <h3 className="font-semibold">{a.title}</h3>
              <p className="text-sm text-slate-600">{a.message}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export function OrdersPage() {
  const { activeBusiness } = useAuth()
  const [orders, setOrders] = useState<Record<string, unknown>[]>([])
  const [total, setTotal] = useState(0)
  const [offset, setOffset] = useState(0)
  const limit = 50

  useEffect(() => {
    if (!activeBusiness) return
    api.get(`/analytics/orders/${activeBusiness.id}`, { params: { limit, offset } }).then(({ data }) => {
      if (Array.isArray(data)) {
        setOrders(data)
        setTotal(data.length)
      } else {
        setOrders(data.items || [])
        setTotal(data.total || 0)
      }
    })
  }, [activeBusiness, offset])

  if (!activeBusiness) return <EmptyState title="No business" message="Select a business." />

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Orders</h1>
        <span className="text-xs text-slate-500">Total Records: {total}</span>
      </div>
      {orders.length === 0 ? (
        <EmptyState title="No orders" message="Upload order data to view order analytics." />
      ) : (
        <div className="card space-y-4">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-left text-slate-500">
                  {Object.keys(orders[0]).map((k) => <th key={k} className="px-3 py-2 uppercase text-xs">{k.replace('_', ' ')}</th>)}
                </tr>
              </thead>
              <tbody>
                {orders.map((o, i) => (
                  <tr key={i} className="border-b border-slate-100 hover:bg-slate-50">
                    {Object.values(o).map((v, j) => <td key={j} className="px-3 py-2 font-mono text-xs">{String(v ?? '')}</td>)}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="flex items-center justify-between pt-2 text-xs text-slate-600">
            <span>Showing {offset + 1} to {Math.min(offset + limit, total)} of {total} entries</span>
            <div className="flex gap-2">
              <button
                type="button"
                className="btn-secondary px-3 py-1 text-xs"
                disabled={offset === 0}
                onClick={() => setOffset((prev) => Math.max(0, prev - limit))}
              >
                Previous
              </button>
              <button
                type="button"
                className="btn-secondary px-3 py-1 text-xs"
                disabled={offset + limit >= total}
                onClick={() => setOffset((prev) => prev + limit)}
              >
                Next
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export function SettingsPage() {
  const { activeBusiness } = useAuth()
  const [sources, setSources] = useState<Record<string, unknown>[]>([])

  useEffect(() => {
    if (!activeBusiness) return
    api.get(`/data/sources/${activeBusiness.id}`).then(({ data }) => setSources(data))
  }, [activeBusiness])

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Settings — Data Sources</h1>
      {sources.length === 0 ? (
        <EmptyState title="No data sources" message="Connect databases, upload files, or integrate e-commerce platforms." />
      ) : (
        <div className="space-y-3">
          {sources.map((s) => (
            <div key={String(s.id)} className="card flex items-center justify-between">
              <div>
                <div className="font-medium">{String(s.name)}</div>
                <div className="text-sm text-slate-500">{String(s.source_type)} — {String(s.status)}</div>
              </div>
              <div className="text-sm text-slate-500">{String(s.records_imported)} records</div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export function PlaceholderPage({ title, message }: { title: string; message: string }) {
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">{title}</h1>
      <EmptyState title={`${title} module`} message={message} />
    </div>
  )
}
