import { useEffect, useState } from 'react'
import api, { AnalyticsResponse } from '../lib/api'
import { useAuth } from '../context/AuthContext'
import { filtersToPayload, useFilters } from '../context/FilterContext'
import KPICard from '../components/KPICard'
import ChartPanel from '../components/ChartPanel'
import EmptyState from '../components/EmptyState'

export function CategoryAnalyticsPage() {
  const { activeBusiness } = useAuth()
  const { filters } = useFilters()
  const [data, setData] = useState<AnalyticsResponse | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!activeBusiness) return
    setLoading(true)
    api.post<AnalyticsResponse>(`/analytics/categories/${activeBusiness.id}`, filtersToPayload(filters))
      .then(({ data: d }) => setData(d))
      .catch(() => setData(null))
      .finally(() => setLoading(false))
  }, [activeBusiness, filters])

  if (!activeBusiness) return <EmptyState title="No business" message="Select a business." />
  if (loading) return <div className="card h-48 animate-pulse bg-slate-100" />

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Category Analytics</h1>
      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        {data?.kpis.map((k) => <KPICard key={k.key} kpi={k} currency={activeBusiness.currency} />)}
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        {data?.charts.map((c) => <ChartPanel key={c.name} name={c.name} data={c.data} />)}
      </div>
      {data?.tables?.[0]?.rows?.length ? (
        <div className="card overflow-x-auto">
          <h2 className="mb-3 font-semibold text-slate-900">Category Breakdown</h2>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b text-left text-slate-500">
                <th className="px-3 py-2">Category</th>
                <th className="px-3 py-2">Revenue</th>
                <th className="px-3 py-2">Units</th>
                <th className="px-3 py-2">Orders</th>
                <th className="px-3 py-2">Profit</th>
                <th className="px-3 py-2">Margin</th>
              </tr>
            </thead>
            <tbody>
              {data.tables[0].rows.map((r: Record<string, unknown>, i: number) => (
                <tr key={i} className="border-b border-slate-100">
                  <td className="px-3 py-2 font-medium">{String(r.category)}</td>
                  <td className="px-3 py-2">₹{Number(r.revenue || 0).toLocaleString()}</td>
                  <td className="px-3 py-2">{String(r.units)}</td>
                  <td className="px-3 py-2">{String(r.orders)}</td>
                  <td className="px-3 py-2">{r.profit != null ? `₹${Number(r.profit).toLocaleString()}` : 'N/A'}</td>
                  <td className="px-3 py-2">{r.margin != null ? `${r.margin}%` : 'N/A'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </div>
  )
}

export function CohortPage() {
  const { activeBusiness } = useAuth()
  const [data, setData] = useState<AnalyticsResponse | null>(null)

  useEffect(() => {
    if (!activeBusiness) return
    api.get<AnalyticsResponse>(`/analytics/cohorts/${activeBusiness.id}`)
      .then(({ data: d }) => setData(d))
      .catch(() => setData(null))
  }, [activeBusiness])

  if (!activeBusiness) return <EmptyState title="No business" message="Select a business." />

  const rows = data?.tables?.[0]?.rows || []
  const unavailable = data?.kpis?.[0]?.unavailable_reason

  if (unavailable) {
    return <EmptyState title="Cohort Analysis unavailable" message={unavailable} />
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Cohort Retention Analysis</h1>
      <p className="text-sm text-slate-500">Percentage of customers making repeat purchases in subsequent months following their first order.</p>

      {rows.length > 0 ? (
        <div className="card overflow-x-auto">
          <table className="w-full text-center text-sm">
            <thead>
              <tr className="border-b bg-slate-50 text-slate-600">
                <th className="px-4 py-3 text-left">Cohort Month</th>
                <th className="px-3 py-3">Customers</th>
                <th className="px-3 py-3">Month 0</th>
                <th className="px-3 py-3">Month 1</th>
                <th className="px-3 py-3">Month 2</th>
                <th className="px-3 py-3">Month 3</th>
                <th className="px-3 py-3">Month 4</th>
                <th className="px-3 py-3">Month 5</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r: Record<string, unknown>, i: number) => (
                <tr key={i} className="border-b border-slate-100">
                  <td className="px-4 py-3 text-left font-medium">{String(r.cohort)}</td>
                  <td className="px-3 py-3 font-semibold text-slate-700">{String(r.size)}</td>
                  {[0, 1, 2, 3, 4, 5].map((m) => {
                    const val = Number(r[`m${m}`] || 0)
                    const bg = val > 50 ? 'bg-emerald-500 text-white' : val > 20 ? 'bg-emerald-200 text-emerald-900' : val > 0 ? 'bg-emerald-50 text-emerald-800' : 'bg-slate-50 text-slate-400'
                    return (
                      <td key={m} className={`px-3 py-3 font-medium ${bg}`}>
                        {val}%
                      </td>
                    )
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <EmptyState title="No cohort data" message="Upload customer purchase history to render cohort retention heatmaps." />
      )}
    </div>
  )
}

export function ConversionFunnelPage() {
  const { activeBusiness } = useAuth()
  const [data, setData] = useState<AnalyticsResponse | null>(null)

  useEffect(() => {
    if (!activeBusiness) return
    api.get<AnalyticsResponse>(`/analytics/funnel/${activeBusiness.id}`)
      .then(({ data: d }) => setData(d))
      .catch(() => setData(null))
  }, [activeBusiness])

  if (!activeBusiness) return <EmptyState title="No business" message="Select a business." />

  const unavailable = data?.kpis?.[0]?.unavailable_reason

  if (unavailable) {
    return <EmptyState title="Conversion Analytics Unavailable" message={unavailable} />
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Conversion Funnel</h1>
      <div className="grid grid-cols-2 gap-4">
        {data?.kpis.map((k) => <KPICard key={k.key} kpi={k} currency={activeBusiness.currency} />)}
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        {data?.charts.map((c) => <ChartPanel key={c.name} name={c.name} data={c.data} />)}
      </div>
    </div>
  )
}

export function ParetoPage() {
  const { activeBusiness } = useAuth()
  const [data, setData] = useState<AnalyticsResponse | null>(null)

  useEffect(() => {
    if (!activeBusiness) return
    api.get<AnalyticsResponse>(`/analytics/pareto/${activeBusiness.id}`)
      .then(({ data: d }) => setData(d))
      .catch(() => setData(null))
  }, [activeBusiness])

  if (!activeBusiness) return <EmptyState title="No business" message="Select a business." />

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Pareto (80/20) Analysis</h1>
      <p className="text-sm text-slate-500">Identify top products responsible for 80% of total revenue contribution.</p>
      <div className="grid grid-cols-2 gap-4">
        {data?.kpis.map((k) => <KPICard key={k.key} kpi={k} currency={activeBusiness.currency} />)}
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        {data?.charts.map((c) => <ChartPanel key={c.name} name={c.name} data={c.data} />)}
      </div>
    </div>
  )
}

export function ForecastPage() {
  const { activeBusiness } = useAuth()
  const [data, setData] = useState<AnalyticsResponse | null>(null)

  useEffect(() => {
    if (!activeBusiness) return
    api.get<AnalyticsResponse>(`/analytics/forecast/${activeBusiness.id}`)
      .then(({ data: d }) => setData(d))
      .catch(() => setData(null))
  }, [activeBusiness])

  if (!activeBusiness) return <EmptyState title="No business" message="Select a business." />

  const unavailable = data?.kpis?.[0]?.unavailable_reason

  if (unavailable) {
    return <EmptyState title="Sales Forecasting Unavailable" message={unavailable} />
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Sales Forecasting</h1>
      <p className="text-sm text-slate-500">30-day projected revenue baseline and statistical confidence bounds based on historical order trends.</p>
      <div className="grid grid-cols-2 gap-4">
        {data?.kpis.map((k) => <KPICard key={k.key} kpi={k} currency={activeBusiness.currency} />)}
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        {data?.charts.map((c) => <ChartPanel key={c.name} name={c.name} data={c.data} />)}
      </div>
    </div>
  )
}

export function GeographyPage() {
  const { activeBusiness } = useAuth()
  const { filters } = useFilters()
  const [data, setData] = useState<AnalyticsResponse | null>(null)

  useEffect(() => {
    if (!activeBusiness) return
    api.post<AnalyticsResponse>(`/analytics/geography/${activeBusiness.id}`, filtersToPayload(filters))
      .then(({ data: d }) => setData(d))
      .catch(() => setData(null))
  }, [activeBusiness, filters])

  if (!activeBusiness) return <EmptyState title="No business" message="Select a business." />

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Geographic Analytics</h1>
      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        {data?.kpis.map((k) => <KPICard key={k.key} kpi={k} currency={activeBusiness.currency} />)}
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        {data?.charts.map((c) => <ChartPanel key={c.name} name={c.name} data={c.data} />)}
      </div>
      {data?.tables?.[0]?.rows?.length ? (
        <div className="card overflow-x-auto">
          <h2 className="mb-3 font-semibold text-slate-900">Regional Performance</h2>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b text-left text-slate-500">
                <th className="px-3 py-2">Country</th>
                <th className="px-3 py-2">State/Region</th>
                <th className="px-3 py-2">City</th>
                <th className="px-3 py-2">Revenue</th>
                <th className="px-3 py-2">Orders</th>
                <th className="px-3 py-2">Customers</th>
                <th className="px-3 py-2">AOV</th>
              </tr>
            </thead>
            <tbody>
              {data.tables[0].rows.map((r: Record<string, unknown>, i: number) => (
                <tr key={i} className="border-b border-slate-100">
                  <td className="px-3 py-2 font-medium">{String(r.country)}</td>
                  <td className="px-3 py-2">{String(r.state)}</td>
                  <td className="px-3 py-2">{String(r.city)}</td>
                  <td className="px-3 py-2 font-semibold">₹{Number(r.revenue || 0).toLocaleString()}</td>
                  <td className="px-3 py-2">{String(r.orders)}</td>
                  <td className="px-3 py-2">{String(r.customers)}</td>
                  <td className="px-3 py-2">₹{Number(r.aov || 0).toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </div>
  )
}

export function ProfitabilityPage() {
  const { activeBusiness } = useAuth()
  const { filters } = useFilters()
  const [data, setData] = useState<AnalyticsResponse | null>(null)
  const [adChannel, setAdChannel] = useState('Google Ads')
  const [adSpendVal, setAdSpendVal] = useState('')
  const [adCampaign, setAdCampaign] = useState('')
  const [adMsg, setAdMsg] = useState('')

  const fetchDeepDive = () => {
    if (!activeBusiness) return
    api.post<AnalyticsResponse>(`/analytics/profitability-deep-dive/${activeBusiness.id}`, filtersToPayload(filters))
      .then(({ data: d }) => setData(d))
      .catch(() => setData(null))
  }

  useEffect(() => {
    fetchDeepDive()
  }, [activeBusiness, filters])

  const handleAddAdSpend = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!activeBusiness || !adSpendVal) return
    setAdMsg('')
    try {
      await api.post(`/analytics/ad-spend/${activeBusiness.id}`, {
        channel: adChannel,
        spend: parseFloat(adSpendVal),
        date: new Date().toISOString(),
        campaign: adCampaign || undefined,
      })
      setAdMsg('Ad spend recorded! Recalculating MER & CAC...')
      setAdSpendVal('')
      setAdCampaign('')
      fetchDeepDive()
    } catch {
      setAdMsg('Failed to record ad spend.')
    }
  }

  if (!activeBusiness) return <EmptyState title="No business" message="Select a business." />

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Profitability & MER/CAC Deep Dive</h1>
        <p className="text-sm text-slate-500">True Contribution Margin (Revenue - COGS - Shipping - Gateway Fees - Refunds) and Marketing Efficiency Ratio (MER & CAC).</p>
      </div>

      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        {data?.kpis.map((k) => <KPICard key={k.key} kpi={k} currency={activeBusiness.currency} />)}
      </div>

      {/* Manual Ad Spend Entry Form */}
      <form onSubmit={handleAddAdSpend} className="card space-y-3 bg-slate-900 text-white">
        <h2 className="text-sm font-bold">Record Marketing Ad Spend (Unblocks MER & CAC)</h2>
        {adMsg && <div className="rounded bg-brand-600/30 p-2 text-xs text-brand-200">{adMsg}</div>}
        <div className="grid gap-3 sm:grid-cols-3">
          <div>
            <label className="mb-1 block text-xs text-slate-400">Marketing Channel</label>
            <select className="input text-xs bg-slate-800 text-white border-slate-700" value={adChannel} onChange={(e) => setAdChannel(e.target.value)}>
              <option value="Google Ads">Google Ads</option>
              <option value="Meta Ads">Meta Ads (Facebook/Insta)</option>
              <option value="TikTok Ads">TikTok Ads</option>
              <option value="Email Marketing">Email Marketing</option>
              <option value="Influencer">Influencer / Affiliate</option>
            </select>
          </div>
          <div>
            <label className="mb-1 block text-xs text-slate-400">Ad Spend Amount (₹)</label>
            <input
              type="number"
              step="0.01"
              required
              placeholder="e.g. 15000"
              value={adSpendVal}
              onChange={(e) => setAdSpendVal(e.target.value)}
              className="input text-xs bg-slate-800 text-white border-slate-700"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs text-slate-400">Campaign Name (Optional)</label>
            <input
              type="text"
              placeholder="e.g. Summer Retargeting"
              value={adCampaign}
              onChange={(e) => setAdCampaign(e.target.value)}
              className="input text-xs bg-slate-800 text-white border-slate-700"
            />
          </div>
        </div>
        <div className="flex justify-end">
          <button type="submit" className="rounded-lg bg-brand-500 px-4 py-2 text-xs font-semibold text-white hover:bg-brand-600 transition">
            Save Ad Spend Record
          </button>
        </div>
      </form>

      {/* Breakdown Table */}
      {data?.tables && data.tables.length > 0 && (
        <div className="card overflow-x-auto">
          <h2 className="mb-3 font-semibold text-slate-900">Profit & Loss Contribution Waterfall</h2>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b text-left text-slate-500">
                <th className="px-3 py-2">Cost / Revenue Line Item</th>
                <th className="px-3 py-2 text-right">Amount (₹)</th>
                <th className="px-3 py-2 text-right">% of Gross Revenue</th>
              </tr>
            </thead>
            <tbody>
              {data.tables.map((r: any, i: number) => (
                <tr key={i} className={`border-b border-slate-100 ${r.metric === 'Contribution Margin' ? 'bg-emerald-50/60 font-bold text-emerald-950' : ''}`}>
                  <td className="px-3 py-2">{r.metric}</td>
                  <td className="px-3 py-2 text-right tabular-nums">₹{Number(r.amount).toLocaleString()}</td>
                  <td className="px-3 py-2 text-right tabular-nums">{r.pct_revenue}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

export function ReturnsPage() {
  const { activeBusiness } = useAuth()
  const [data, setData] = useState<AnalyticsResponse | null>(null)

  useEffect(() => {
    if (!activeBusiness) return
    api.get<AnalyticsResponse>(`/analytics/returns/${activeBusiness.id}`)
      .then(({ data: d }) => setData(d))
      .catch(() => setData(null))
  }, [activeBusiness])

  if (!activeBusiness) return <EmptyState title="No business" message="Select a business." />

  const unavailable = data?.kpis?.[0]?.unavailable_reason
  if (unavailable) return <EmptyState title="Returns Analytics Unavailable" message={unavailable} />

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-textPrimary">Returns Analytics</h1>
      <div className="grid grid-cols-2 gap-4">
        {data?.kpis.map((k) => <KPICard key={k.key} kpi={k} currency={activeBusiness.currency} />)}
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        {data?.charts.map((c) => <ChartPanel key={c.name} name={c.name} data={c.data} />)}
      </div>
    </div>
  )
}

export function MarketingPage() {
  const { activeBusiness } = useAuth()
  const { filters } = useFilters()
  const [data, setData] = useState<AnalyticsResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [adChannel, setAdChannel] = useState('Google Ads')
  const [adSpendVal, setAdSpendVal] = useState('')
  const [adCampaign, setAdCampaign] = useState('')
  const [adMsg, setAdMsg] = useState('')
  const [searchTerm, setSearchTerm] = useState('')

  const fetchMarketingData = () => {
    if (!activeBusiness) {
      setLoading(false)
      return
    }
    setLoading(true)
    api.post<AnalyticsResponse>(`/analytics/marketing/${activeBusiness.id}`, filtersToPayload(filters))
      .then(({ data: d }) => setData(d))
      .catch(() => setData(null))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    fetchMarketingData()
  }, [activeBusiness, filters])

  const handleAddAdSpend = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!activeBusiness || !adSpendVal) return
    setAdMsg('')
    try {
      await api.post(`/analytics/ad-spend/${activeBusiness.id}`, {
        channel: adChannel,
        spend: parseFloat(adSpendVal),
        date: new Date().toISOString(),
        campaign: adCampaign || undefined,
      })
      setAdMsg('Ad spend recorded successfully! Updating channel attribution...')
      setAdSpendVal('')
      setAdCampaign('')
      fetchMarketingData()
    } catch {
      setAdMsg('Failed to record ad spend.')
    }
  }

  if (!activeBusiness) return <EmptyState title="No Business Selected" message="Select or create a business." />
  if (loading) return <div className="card h-64 animate-pulse bg-surface min-w-0" />

  const unavailable = data?.kpis?.length && data.kpis.every((k) => k.unavailable_reason)

  return (
    <div className="space-y-6 min-w-0">
      <div>
        <h1 className="text-2xl font-bold text-textPrimary">Marketing Analytics & Attribution</h1>
        <p className="text-xs text-textSecondary">Multi-channel ad spend tracking, revenue attribution, Blended ROAS, CAC, and channel performance metrics.</p>
      </div>

      {unavailable ? (
        <EmptyState title="Marketing Analytics Unavailable" message={data?.kpis[0]?.unavailable_reason || 'Marketing data not uploaded.'} />
      ) : (
        <>
          {/* Executive Marketing KPIs */}
          <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
            {data?.kpis.map((kpi) => (
              <KPICard key={kpi.key} kpi={kpi} currency={activeBusiness.currency} />
            ))}
          </div>

          {/* Record Marketing Ad Spend Tool */}
          <form onSubmit={handleAddAdSpend} className="card space-y-4 bg-white border border-surface-border">
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-bold text-textPrimary">Record Marketing Ad Spend</h2>
              <span className="text-xs text-textSecondary">Unblocks MER, Blended ROAS & CAC Calculations</span>
            </div>
            {adMsg && <div className="rounded-lg bg-emerald-50 p-2.5 text-xs font-semibold text-emerald-800 border border-emerald-200">{adMsg}</div>}
            <div className="grid gap-4 sm:grid-cols-3">
              <div>
                <label className="mb-1 block text-xs font-medium text-textSecondary">Marketing Channel</label>
                <select className="input text-xs" value={adChannel} onChange={(e) => setAdChannel(e.target.value)}>
                  <option value="Google Ads">Google Ads</option>
                  <option value="Meta Ads">Meta Ads (Facebook/Instagram)</option>
                  <option value="TikTok Ads">TikTok Ads</option>
                  <option value="Email Marketing">Email Marketing</option>
                  <option value="Influencer">Influencer / Affiliate</option>
                </select>
              </div>
              <div>
                <label className="mb-1 block text-xs font-medium text-textSecondary">Ad Spend Amount (₹)</label>
                <input
                  type="number"
                  step="0.01"
                  required
                  placeholder="e.g. 15000"
                  value={adSpendVal}
                  onChange={(e) => setAdSpendVal(e.target.value)}
                  className="input text-xs"
                />
              </div>
              <div>
                <label className="mb-1 block text-xs font-medium text-textSecondary">Campaign Name (Optional)</label>
                <input
                  type="text"
                  placeholder="e.g. Summer Retargeting"
                  value={adCampaign}
                  onChange={(e) => setAdCampaign(e.target.value)}
                  className="input text-xs"
                />
              </div>
            </div>
            <div className="flex justify-end pt-1">
              <button type="submit" className="btn-primary text-xs">
                Save Ad Spend Record
              </button>
            </div>
          </form>

          {/* Charts */}
          <div className="grid gap-6 lg:grid-cols-2 min-w-0">
            {data?.charts.map((c) => (
              <ChartPanel key={c.name} name={c.name} data={c.data} />
            ))}
          </div>

          {/* Marketing Channel Performance Data Table */}
          {data?.tables && data.tables.length > 0 && (
            <div className="card space-y-4">
              <div className="flex flex-wrap items-center justify-between gap-4 border-b border-surface-border pb-3">
                <h3 className="text-sm font-semibold capitalize text-textPrimary">Channel Performance Breakdown</h3>
                <input
                  type="text"
                  placeholder="Filter channels..."
                  className="input w-full sm:w-64 text-xs py-1.5"
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                />
              </div>

              <div className="table-scroll-container">
                <table className="w-full text-left text-xs">
                  <thead>
                    <tr className="border-b border-surface-border bg-surface text-textSecondary uppercase font-medium">
                      <th className="px-3 py-2.5">Channel</th>
                      <th className="px-3 py-2.5 text-right">Spend (₹)</th>
                      <th className="px-3 py-2.5 text-right">Revenue (₹)</th>
                      <th className="px-3 py-2.5 text-right">Conversions</th>
                      <th className="px-3 py-2.5 text-right">ROAS</th>
                      <th className="px-3 py-2.5 text-right">CAC (₹)</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-surface-border tabular-nums font-medium text-textPrimary">
                    {data.tables[0]?.rows
                      ?.filter((r: any) => String(r.channel || '').toLowerCase().includes(searchTerm.toLowerCase()))
                      .map((r: any, idx: number) => (
                        <tr key={idx} className="hover:bg-surface transition-colors">
                          <td className="px-3 py-2.5 font-bold text-textPrimary">{r.channel}</td>
                          <td className="px-3 py-2.5 text-right">₹{Number(r.spend || 0).toLocaleString()}</td>
                          <td className="px-3 py-2.5 text-right">₹{Number(r.revenue || 0).toLocaleString()}</td>
                          <td className="px-3 py-2.5 text-right">{r.conversions || 0}</td>
                          <td className="px-3 py-2.5 text-right font-bold text-emerald-700">{r.roas != null ? `${r.roas}x` : '—'}</td>
                          <td className="px-3 py-2.5 text-right font-semibold">₹{r.cac != null ? Number(r.cac).toLocaleString() : '—'}</td>
                        </tr>
                      ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  )
}

