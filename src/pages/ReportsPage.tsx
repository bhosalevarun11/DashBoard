import { useState, useEffect } from 'react'
import { Download, FileText, CheckCircle, Sliders, Calendar, Send } from 'lucide-react'
import api, { SavedCustomReport, ScheduledReport, AnalyticsResponse } from '../lib/api'
import { useAuth } from '../context/AuthContext'
import EmptyState from '../components/EmptyState'

type Tab = 'pdf' | 'custom' | 'schedules'

export default function ReportsPage() {
  const { activeBusiness } = useAuth()
  const [activeTab, setActiveTab] = useState<Tab>('pdf')
  const [reportType, setReportType] = useState('monthly')
  const [downloading, setDownloading] = useState(false)

  // Custom Report Builder state
  const [customMetric, setCustomMetric] = useState('revenue')
  const [customDimension, setCustomDimension] = useState('sales_channel')
  const [customPreset, setCustomPreset] = useState('30d')
  const [customChartType, setCustomChartType] = useState('bar')
  const [customReportName, setCustomReportName] = useState('')
  const [previewResult, setPreviewResult] = useState<AnalyticsResponse | null>(null)
  const [loadingPreview, setLoadingPreview] = useState(false)

  // Saved reports & schedules lists
  const [savedReports, setSavedReports] = useState<SavedCustomReport[]>([])
  const [scheduledReports, setScheduledReports] = useState<ScheduledReport[]>([])

  // Schedule modal form state
  const [scheduleName, setScheduleName] = useState('Weekly Digest')
  const [scheduleFrequency, setScheduleFrequency] = useState('weekly')
  const [scheduleEmail, setScheduleEmail] = useState('')
  const [scheduleWebhook, setScheduleWebhook] = useState('')
  const [scheduleMsg, setScheduleMsg] = useState('')

  useEffect(() => {
    if (activeBusiness) {
      loadSavedReports()
      loadScheduledReports()
    }
  }, [activeBusiness])

  const loadSavedReports = async () => {
    if (!activeBusiness) return
    try {
      const { data } = await api.get<SavedCustomReport[]>(`/reports-custom/saved/${activeBusiness.id}`)
      setSavedReports(data)
    } catch (e) {
      console.error(e)
    }
  }

  const loadScheduledReports = async () => {
    if (!activeBusiness) return
    try {
      const { data } = await api.get<ScheduledReport[]>(`/reports-custom/schedules/${activeBusiness.id}`)
      setScheduledReports(data)
    } catch (e) {
      console.error(e)
    }
  }

  if (!activeBusiness) {
    return <EmptyState title="No business selected" message="Select a business to generate and export reports." />
  }

  const reports = [
    { id: 'monthly', title: 'Monthly Business Report', desc: 'Comprehensive overview of revenue, profit, orders, customers, and key insights.' },
    { id: 'sales', title: 'Sales Performance Report', desc: 'Detailed breakdown of gross vs net sales, AOV, discounts, taxes, and shipping.' },
    { id: 'product', title: 'Product Analytics Report', desc: 'Top & worst selling products, revenue, units sold, costs, margins, and sell-through rates.' },
    { id: 'customer', title: 'Customer & RFM Report', desc: 'Customer retention rates, customer lifetime value, RFM segmentation distribution, and location analysis.' },
    { id: 'inventory', title: 'Inventory Valuation Report', desc: 'Current stock levels, stockout risks, low-stock warnings, reorder points, and total inventory value.' },
    { id: 'profitability', title: 'Profitability Analysis Report', desc: 'Revenue vs cost structure analysis, gross/net margins, and profit contribution by channel.' },
    { id: 'returns', title: 'Returns & Refunds Report', desc: 'Return rates, refund amounts, unit loss, and top return reasons breakdown.' },
  ]

  const [downloadError, setDownloadError] = useState('')

  const downloadPDF = async () => {
    setDownloading(true)
    setDownloadError('')
    try {
      const response = await api.post(`/analytics/reports/${activeBusiness.id}/pdf?report_type=${reportType}`, {}, {
        responseType: 'blob',
      })
      const blob = new Blob([response.data], { type: 'application/pdf' })
      const url = window.URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.setAttribute('download', `${reportType}_report_${activeBusiness.name.toLowerCase().replace(/\s+/g, '_')}.pdf`)
      document.body.appendChild(link)
      link.click()
      link.remove()
      window.URL.revokeObjectURL(url)
    } catch (err: any) {
      console.error('Failed to download PDF report', err)
      let msg = 'Failed to generate PDF report. Please check server logs.'
      if (err.response?.data instanceof Blob) {
        try {
          const text = await err.response.data.text()
          const parsed = JSON.parse(text)
          if (parsed?.detail) msg = parsed.detail
        } catch {
          // fallback
        }
      } else if (err.response?.data?.detail) {
        msg = err.response.data.detail
      }
      setDownloadError(msg)
    } finally {
      setDownloading(false)
    }
  }

  const handleRunCustomReport = async () => {
    setLoadingPreview(true)
    try {
      const { data } = await api.post<AnalyticsResponse>(
        `/analytics/custom-report/${activeBusiness.id}?metric=${customMetric}&dimension=${customDimension}&date_range_preset=${customPreset}&chart_type=${customChartType}`
      )
      setPreviewResult(data)
    } catch (err) {
      console.error('Failed custom report preview', err)
    } finally {
      setLoadingPreview(false)
    }
  }

  const handleSaveCustomReport = async () => {
    if (!customReportName.trim()) return
    try {
      await api.post(`/reports-custom/saved/${activeBusiness.id}`, {
        name: customReportName,
        metric: customMetric,
        dimension: customDimension,
        date_range_preset: customPreset,
        chart_type: customChartType,
      })
      setCustomReportName('')
      loadSavedReports()
    } catch (err) {
      console.error('Failed to save report', err)
    }
  }

  const handleCreateSchedule = async (e: React.FormEvent) => {
    e.preventDefault()
    setScheduleMsg('')
    try {
      await api.post(`/reports-custom/schedules/${activeBusiness.id}`, {
        name: scheduleName,
        frequency: scheduleFrequency,
        recipient_email: scheduleEmail || undefined,
        webhook_url: scheduleWebhook || undefined,
        is_active: true,
      })
      setScheduleMsg('Scheduled digest created successfully!')
      setScheduleName('')
      setScheduleEmail('')
      setScheduleWebhook('')
      loadScheduledReports()
    } catch (err) {
      setScheduleMsg('Failed to create schedule.')
    }
  }

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Reports & BI Hub</h1>
          <p className="text-sm text-slate-500">Generate executive PDF reports, build custom no-code reports, and schedule digest delivery.</p>
        </div>

        {/* Tabs Switcher */}
        <div className="inline-flex rounded-xl bg-slate-100 p-1">
          <button
            onClick={() => setActiveTab('pdf')}
            className={`rounded-lg px-4 py-2 text-xs font-semibold transition ${activeTab === 'pdf' ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-600 hover:text-slate-900'}`}
          >
            PDF Executive Reports
          </button>
          <button
            onClick={() => setActiveTab('custom')}
            className={`rounded-lg px-4 py-2 text-xs font-semibold transition ${activeTab === 'custom' ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-600 hover:text-slate-900'}`}
          >
            No-Code Custom Builder
          </button>
          <button
            onClick={() => setActiveTab('schedules')}
            className={`rounded-lg px-4 py-2 text-xs font-semibold transition ${activeTab === 'schedules' ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-600 hover:text-slate-900'}`}
          >
            Scheduled Digests
          </button>
        </div>
      </div>

      {/* Tab 1: Executive PDF Reports */}
      {activeTab === 'pdf' && (
        <div className="space-y-6">
          <div className="grid gap-4 md:grid-cols-2">
            {reports.map((r) => (
              <div
                key={r.id}
                onClick={() => setReportType(r.id)}
                className={`card cursor-pointer border-2 transition ${
                  reportType === r.id ? 'border-brand-500 bg-brand-50/50 shadow-md' : 'border-slate-200 hover:border-slate-300'
                }`}
              >
                <div className="flex items-start justify-between">
                  <div className="flex items-center gap-3">
                    <div className={`rounded-lg p-2 ${reportType === r.id ? 'bg-brand-600 text-white' : 'bg-slate-100 text-slate-600'}`}>
                      <FileText size={20} />
                    </div>
                    <div>
                      <h3 className="font-semibold text-slate-900">{r.title}</h3>
                      <p className="mt-1 text-xs text-slate-500">{r.desc}</p>
                    </div>
                  </div>
                  {reportType === r.id && <CheckCircle size={18} className="text-brand-600" />}
                </div>
              </div>
            ))}
          </div>

          {downloadError && (
            <div className="rounded-lg bg-red-50 border border-red-200 p-3.5 text-sm font-semibold text-red-700">
              {downloadError}
            </div>
          )}

          <div className="card flex items-center justify-between bg-slate-900 text-white">
            <div>
              <h2 className="text-lg font-bold">Export {reports.find((r) => r.id === reportType)?.title}</h2>
              <p className="text-xs text-slate-400">Download formatted PDF document for {activeBusiness.name}.</p>
            </div>
            <button
              onClick={downloadPDF}
              disabled={downloading}
              className="flex items-center gap-2 rounded-lg bg-brand-500 px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-brand-600 disabled:opacity-50"
            >
              <Download size={18} />
              {downloading ? 'Generating PDF...' : 'Download PDF Report'}
            </button>
          </div>
        </div>
      )}

      {/* Tab 2: Custom Report Builder */}
      {activeTab === 'custom' && (
        <div className="space-y-6">
          <div className="card space-y-4">
            <h2 className="text-lg font-bold text-slate-900 flex items-center gap-2">
              <Sliders size={20} className="text-brand-600" />
              Configure Custom Report
            </h2>

            <div className="grid gap-4 sm:grid-cols-4">
              <div>
                <label className="mb-1 block text-xs font-semibold text-slate-700">Metric</label>
                <select className="input" value={customMetric} onChange={(e) => setCustomMetric(e.target.value)}>
                  <option value="revenue">Total Revenue</option>
                  <option value="orders">Total Orders</option>
                  <option value="aov">Average Order Value (AOV)</option>
                  <option value="contribution_margin">Contribution Margin</option>
                  <option value="shipping">Shipping Cost</option>
                </select>
              </div>

              <div>
                <label className="mb-1 block text-xs font-semibold text-slate-700">Dimension</label>
                <select className="input" value={customDimension} onChange={(e) => setCustomDimension(e.target.value)}>
                  <option value="sales_channel">Sales Channel</option>
                  <option value="category">Category</option>
                  <option value="payment_method">Payment Method</option>
                  <option value="region">Customer Region</option>
                  <option value="country">Country</option>
                </select>
              </div>

              <div>
                <label className="mb-1 block text-xs font-semibold text-slate-700">Time Window</label>
                <select className="input" value={customPreset} onChange={(e) => setCustomPreset(e.target.value)}>
                  <option value="7d">Last 7 Days</option>
                  <option value="30d">Last 30 Days</option>
                  <option value="90d">Last 90 Days</option>
                  <option value="1y">Last 1 Year</option>
                </select>
              </div>

              <div>
                <label className="mb-1 block text-xs font-semibold text-slate-700">Chart Type</label>
                <select className="input" value={customChartType} onChange={(e) => setCustomChartType(e.target.value)}>
                  <option value="bar">Bar Chart</option>
                  <option value="line">Line Chart</option>
                  <option value="table">Data Table Only</option>
                </select>
              </div>
            </div>

            <div className="flex items-center justify-between pt-2">
              <button onClick={handleRunCustomReport} disabled={loadingPreview} className="btn-primary">
                {loadingPreview ? 'Generating...' : 'Run & Preview Report'}
              </button>

              <div className="flex items-center gap-2">
                <input
                  type="text"
                  placeholder="Save as report name..."
                  value={customReportName}
                  onChange={(e) => setCustomReportName(e.target.value)}
                  className="input w-64 text-sm"
                />
                <button onClick={handleSaveCustomReport} disabled={!customReportName.trim()} className="btn-secondary">
                  Save Report
                </button>
              </div>
            </div>
          </div>

          {/* Preview Results Card */}
          {previewResult && (
            <div className="card space-y-4">
              <div className="flex items-center justify-between">
                <h3 className="font-bold text-slate-900">Custom Report Preview</h3>
                <span className="text-xs text-slate-500 font-mono">
                  {customMetric} by {customDimension} ({customPreset})
                </span>
              </div>

              {previewResult.tables && previewResult.tables.length > 0 ? (
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs">
                    <thead className="bg-slate-100 font-semibold text-slate-700">
                      <tr>
                        <th className="p-2.5">Dimension ({customDimension})</th>
                        <th className="p-2.5 text-right">Metric Value</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-200">
                      {previewResult.tables.map((row: any, idx: number) => (
                        <tr key={idx} className="hover:bg-slate-50">
                          <td className="p-2.5 font-medium text-slate-900">{row.dimension}</td>
                          <td className="p-2.5 text-right font-semibold text-slate-900 tabular-nums">
                            {row.metric_value}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <p className="text-xs text-slate-500">No data found for the selected custom configuration.</p>
              )}
            </div>
          )}

          {/* Saved Custom Reports */}
          {savedReports.length > 0 && (
            <div className="card space-y-3">
              <h3 className="font-bold text-slate-900">Your Saved Custom Reports</h3>
              <div className="grid gap-3 sm:grid-cols-2">
                {savedReports.map((sr) => (
                  <div key={sr.id} className="rounded-xl border border-slate-200 p-3 shadow-sm bg-white hover:border-slate-400 transition">
                    <h4 className="font-semibold text-slate-900">{sr.name}</h4>
                    <p className="text-xs text-slate-500 mt-1">
                      {sr.metric} broken down by {sr.dimension} ({sr.date_range_preset})
                    </p>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Tab 3: Scheduled Digest Delivery */}
      {activeTab === 'schedules' && (
        <div className="space-y-6">
          <form onSubmit={handleCreateSchedule} className="card space-y-4">
            <h2 className="text-lg font-bold text-slate-900 flex items-center gap-2">
              <Calendar size={20} className="text-brand-600" />
              Configure Recurring Digest Schedule
            </h2>

            {scheduleMsg && <div className="rounded-lg bg-emerald-50 border border-emerald-200 p-3 text-xs text-emerald-800">{scheduleMsg}</div>}

            <div className="grid gap-4 sm:grid-cols-2">
              <div>
                <label className="mb-1 block text-xs font-semibold text-slate-700">Digest Name</label>
                <input
                  type="text"
                  required
                  value={scheduleName}
                  onChange={(e) => setScheduleName(e.target.value)}
                  className="input"
                  placeholder="Weekly Executive Summary"
                />
              </div>

              <div>
                <label className="mb-1 block text-xs font-semibold text-slate-700">Frequency</label>
                <select className="input" value={scheduleFrequency} onChange={(e) => setScheduleFrequency(e.target.value)}>
                  <option value="daily">Daily Morning Digest</option>
                  <option value="weekly">Weekly Summary (Every Monday)</option>
                </select>
              </div>

              <div>
                <label className="mb-1 block text-xs font-semibold text-slate-700">Recipient Email (SMTP)</label>
                <input
                  type="email"
                  value={scheduleEmail}
                  onChange={(e) => setScheduleEmail(e.target.value)}
                  className="input"
                  placeholder="executives@company.com"
                />
              </div>

              <div>
                <label className="mb-1 block text-xs font-semibold text-slate-700">Slack / Teams Webhook URL</label>
                <input
                  type="url"
                  value={scheduleWebhook}
                  onChange={(e) => setScheduleWebhook(e.target.value)}
                  className="input"
                  placeholder="https://hooks.slack.com/services/..."
                />
              </div>
            </div>

            <div className="flex justify-end pt-2">
              <button type="submit" className="btn-primary flex items-center gap-2">
                <Send size={16} />
                Activate Schedule
              </button>
            </div>
          </form>

          {/* List Active Schedules */}
          {scheduledReports.length > 0 && (
            <div className="card space-y-3">
              <h3 className="font-bold text-slate-900">Active Digest Schedules</h3>
              <div className="divide-y divide-slate-200">
                {scheduledReports.map((sc) => (
                  <div key={sc.id} className="flex items-center justify-between py-3">
                    <div>
                      <h4 className="font-semibold text-slate-900">{sc.name}</h4>
                      <p className="text-xs text-slate-500 mt-0.5">
                        Frequency: <span className="font-semibold text-slate-700 uppercase">{sc.frequency}</span>
                        {sc.recipient_email && ` • Email: ${sc.recipient_email}`}
                        {sc.webhook_url && ` • Webhook Configured`}
                      </p>
                    </div>
                    <span className="rounded-full bg-emerald-100 px-2.5 py-1 text-xs font-semibold text-emerald-800">Active</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
