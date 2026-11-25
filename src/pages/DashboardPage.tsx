import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import api, { AnalyticsResponse, Insight } from '../lib/api'
import { useAuth } from '../context/AuthContext'
import { filtersToPayload, useFilters } from '../context/FilterContext'
import KPICard from '../components/KPICard'
import ChartPanel from '../components/ChartPanel'
import EmptyState from '../components/EmptyState'
import { KPICardSkeleton, ChartPanelSkeleton, FadeContainer } from '../components/SkeletonLoader'
import { Lightbulb, ArrowRight } from 'lucide-react'
import { motion } from 'framer-motion'

export default function DashboardPage() {
  const { activeBusiness } = useAuth()
  const { filters } = useFilters()
  const [data, setData] = useState<AnalyticsResponse | null>(null)
  const [insights, setInsights] = useState<Insight[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!activeBusiness) {
      setLoading(false)
      return
    }

    const controller = new AbortController()
    setLoading(true)

    // Clear previous data before showing new date range to prevent stale data flash
    setData(null)

    api
      .post<AnalyticsResponse>(`/analytics/dashboard/${activeBusiness.id}`, filtersToPayload(filters), {
        signal: controller.signal,
      })
      .then(({ data: d }) => setData(d))
      .catch((err) => {
        if (err?.name !== 'CanceledError') {
          setData(null)
        }
      })
      .finally(() => setLoading(false))

    api
      .get<Insight[]>(`/analytics/insights/${activeBusiness.id}`, { signal: controller.signal })
      .then(({ data: ins }) => setInsights(ins.slice(0, 2)))
      .catch(() => setInsights([]))

    return () => {
      controller.abort()
    }
  }, [activeBusiness, filters])

  if (!activeBusiness) {
    return (
      <EmptyState
        title="No Business Selected"
        message="Create or select a business to start viewing executive e-commerce analytics."
        action={<Link to="/connect" className="btn-primary">Connect Data Source</Link>}
      />
    )
  }

  if (loading && !data) {
    return (
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div className="h-8 w-48 animate-pulse rounded bg-slate-100" />
          <div className="h-8 w-32 animate-pulse rounded bg-slate-100" />
        </div>

        {/* Exact-dimension Skeletons (0 CLS) */}
        <div className="grid grid-cols-2 gap-4 md:grid-cols-3 lg:grid-cols-5">
          {Array.from({ length: 10 }).map((_, i) => (
            <KPICardSkeleton key={i} />
          ))}
        </div>

        <div className="grid gap-6 lg:grid-cols-2">
          <ChartPanelSkeleton />
          <ChartPanelSkeleton />
        </div>
      </div>
    )
  }

  const hasOrders = data?.meta?.availability && (data.meta.availability as { orders?: boolean }).orders

  if (!hasOrders && !loading) {
    return (
      <EmptyState
        title="No E-Commerce Data Connected"
        message="Upload your e-commerce order data or connect an external data source to activate the executive dashboard."
        action={<Link to="/connect" className="btn-primary">Connect Data Source</Link>}
      />
    )
  }

  return (
    <FadeContainer>
      <div className="space-y-6 min-w-0">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-textPrimary">Executive Dashboard</h1>
            <p className="text-xs text-textSecondary">{activeBusiness.name} — Real-time performance overview</p>
          </div>
          <Link to="/reports" className="btn-secondary text-xs">
            Export PDF Report
          </Link>
        </div>

        {/* Core KPI Cards Grid */}
        <div className="grid grid-cols-2 gap-4 md:grid-cols-3 lg:grid-cols-5 min-w-0">
          {data?.kpis.map((kpi, idx) => (
            <motion.div
              key={kpi.key}
              className="min-w-0 h-full"
              initial={{ opacity: 0, scale: 0.96 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ duration: 0.2, delay: idx * 0.03 }}
            >
              <KPICard kpi={kpi} currency={activeBusiness.currency} isHero={idx === 0} />
            </motion.div>
          ))}
        </div>


        {/* Automated Business Insights Highlight */}
        {insights.length > 0 && (
          <div className="card border-l-4 border-l-black bg-surface">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2 text-xs font-semibold uppercase text-textPrimary">
                <Lightbulb size={16} />
                <span>Automated Business Insights</span>
              </div>
              <Link to="/insights" className="flex items-center gap-1 text-xs font-medium text-textSecondary hover:text-textPrimary">
                <span>View All</span>
                <ArrowRight size={12} />
              </Link>
            </div>
            <div className="grid gap-3 md:grid-cols-2">
              {insights.map((ins) => (
                <div key={ins.id} className="rounded-lg border border-surface-border bg-white p-3">
                  <h4 className="text-xs font-semibold text-textPrimary">{ins.title}</h4>
                  <p className="mt-1 text-xs text-textSecondary">{ins.description}</p>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Main Analytics Charts */}
        <div className="grid gap-6 lg:grid-cols-2 min-w-0">
          {data?.charts.map((chart) => (
            <ChartPanel key={chart.name} name={chart.name} data={chart.data} />
          ))}
        </div>
      </div>
    </FadeContainer>
  )
}
