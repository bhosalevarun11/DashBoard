import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Database, FileSpreadsheet, ShoppingBag, Store, CheckCircle, Loader2, ArrowRight, Zap, AlertCircle } from 'lucide-react'
import api from '../lib/api'
import { useAuth } from '../context/AuthContext'
import EmptyState from '../components/EmptyState'

type Tab = 'files' | 'database' | 'integrations' | 'agent'

export default function ConnectDataPage() {
  const { activeBusiness, refreshBusinesses } = useAuth()
  const navigate = useNavigate()
  const [tab, setTab] = useState<Tab>('files')
  const [message, setMessage] = useState('')
  const [isError, setIsError] = useState(false)
  const [successBanner, setSuccessBanner] = useState<string | null>(null)
  
  const [uploadResults, setUploadResults] = useState<any[]>([])
  const [importingJobId, setImportingJobId] = useState<number | null>(null)
  const [importedJobs, setImportedJobs] = useState<Record<number, number>>({})

  const [isTestingConnection, setIsTestingConnection] = useState(false)
  const [isConnectingDb, setIsConnectingDb] = useState(false)
  const [isSeedingSample, setIsSeedingSample] = useState(false)
  const [isConnectingShopify, setIsConnectingShopify] = useState(false)
  const [isConnectingWoo, setIsConnectingWoo] = useState(false)

  const [dbForm, setDbForm] = useState({
    name: 'PostgreSQL Store DB',
    db_type: 'postgresql',
    host: 'localhost',
    port: 5433,
    database_name: 'ecommerce_analytics',
    username: 'postgres',
    password: 'varun11',
    ssl: false,
  })

  const [shopifyForm, setShopifyForm] = useState({ shop_domain: '', access_token: '', name: 'Shopify Store' })
  const [wooForm, setWooForm] = useState({ store_url: '', consumer_key: '', consumer_secret: '', name: 'WooCommerce Store' })
  const [agentToken, setAgentToken] = useState<string | null>(null)

  if (!activeBusiness) {
    return <EmptyState title="Create a business first" message="Register or select a business before connecting data." />
  }

  const handleAutoFillPostgres = () => {
    setDbForm({
      name: 'Local PostgreSQL 17',
      db_type: 'postgresql',
      host: 'localhost',
      port: 5433,
      database_name: 'ecommerce_analytics',
      username: 'postgres',
      password: 'varun11',
      ssl: false,
    })
    setMessage('Auto-filled local PostgreSQL credentials (Port 5433).')
    setIsError(false)
  }

  const testConnection = async () => {
    setIsTestingConnection(true)
    setMessage('Testing database connection...')
    setIsError(false)
    try {
      const { data } = await api.post('/data/test-connection', dbForm)
      if (data.success) {
        setMessage('Connection test successful! Database is reachable.')
        setIsError(false)
      } else {
        setMessage(`Connection test failed: ${data.message}`)
        setIsError(true)
      }
    } catch (err: any) {
      setMessage(err?.response?.data?.detail || 'Connection test failed')
      setIsError(true)
    } finally {
      setIsTestingConnection(false)
    }
  }

  const connectDatabase = async () => {
    setIsConnectingDb(true)
    setMessage('Connecting external database and syncing initial schema...')
    setIsError(false)
    try {
      const { data } = await api.post(`/data/connect-database?business_id=${activeBusiness.id}`, dbForm)
      setSuccessBanner(`Database connected successfully! Connected ${data?.name || 'database source'}.`)
      setMessage('Database connected and initial sync completed.')
      await refreshBusinesses()
    } catch (err: any) {
      const msg = err?.response?.data?.detail
      setMessage(msg || 'Database connection failed. Please check host, port, and credentials.')
      setIsError(true)
    } finally {
      setIsConnectingDb(false)
    }
  }

  const handleSeedSampleData = async () => {
    setIsSeedingSample(true)
    setMessage('Importing sample store datasets (orders, products, customers, inventory)...')
    setIsError(false)
    try {
      const { data } = await api.post(`/data/seed-sample-data/${activeBusiness.id}`)
      setSuccessBanner(`Successfully imported ${data.total_imported} sample records into your dashboard store!`)
      setMessage('Sample store data active. Executive dashboard is ready.')
      await refreshBusinesses()
    } catch (err: any) {
      setMessage(err?.response?.data?.detail || 'Failed to seed sample data')
      setIsError(true)
    } finally {
      setIsSeedingSample(false)
    }
  }

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files
    if (!files?.length) return
    const formData = new FormData()
    Array.from(files).forEach((f) => formData.append('files', f))
    setMessage('Uploading and inspecting files...')
    setIsError(false)
    try {
      const { data } = await api.post(`/data/upload/${activeBusiness.id}`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      setUploadResults(data.uploads)
      setMessage(`Uploaded ${data.uploads.length} file(s). Click 'Import Valid Records' to ingest data.`)
    } catch (err: any) {
      setMessage(err?.response?.data?.detail || 'Upload failed')
      setIsError(true)
    }
  }

  const importJob = async (jobId: number) => {
    setImportingJobId(jobId)
    setMessage('Importing valid records into database...')
    setIsError(false)
    try {
      const { data } = await api.post(`/data/import/${activeBusiness.id}/${jobId}`)
      setImportedJobs((prev) => ({ ...prev, [jobId]: data.imported }))
      setSuccessBanner(`Successfully imported ${data.imported} records into your store!`)
      setMessage(`Successfully imported ${data.imported} valid records! Analytics updated.`)
      await refreshBusinesses()
    } catch (err: any) {
      setMessage(err?.response?.data?.detail || 'Import failed')
      setIsError(true)
    } finally {
      setImportingJobId(null)
    }
  }

  const registerAgent = async () => {
    try {
      const { data } = await api.post('/data/connector/register', {
        name: 'Local Connector Agent',
        business_id: activeBusiness.id,
      })
      setAgentToken(data.agent_token)
      setMessage('Agent Token generated successfully!')
      setIsError(false)
    } catch {
      setMessage('Failed to generate Agent Token')
      setIsError(true)
    }
  }

  const connectShopify = async () => {
    setIsConnectingShopify(true)
    try {
      await api.post(`/data/shopify/${activeBusiness.id}`, shopifyForm)
      setSuccessBanner('Shopify connected successfully. Initial product & order sync started.')
      setMessage('Shopify store connected.')
      await refreshBusinesses()
    } catch (err: any) {
      setMessage(err?.response?.data?.detail || 'Shopify connection failed')
      setIsError(true)
    } finally {
      setIsConnectingShopify(false)
    }
  }

  const connectWoo = async () => {
    setIsConnectingWoo(true)
    try {
      await api.post(`/data/woocommerce/${activeBusiness.id}`, wooForm)
      setSuccessBanner('WooCommerce connected successfully. Initial sync started.')
      setMessage('WooCommerce store connected.')
      await refreshBusinesses()
    } catch (err: any) {
      setMessage(err?.response?.data?.detail || 'WooCommerce connection failed')
      setIsError(true)
    } finally {
      setIsConnectingWoo(false)
    }
  }

  const tabs = [
    { id: 'files' as Tab, label: 'CSV / Excel Upload', icon: FileSpreadsheet },
    { id: 'database' as Tab, label: 'External Database', icon: Database },
    { id: 'integrations' as Tab, label: 'E-Commerce Integrations', icon: ShoppingBag },
    { id: 'agent' as Tab, label: 'Local Agent', icon: Store },
  ]

  return (
    <div className="mx-auto max-w-4xl space-y-6 min-w-0">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-textPrimary">Connect Data</h1>
          <p className="text-sm text-textSecondary">Connect database, upload files, or import sample data into your e-commerce platform.</p>
        </div>

        <button
          onClick={handleSeedSampleData}
          disabled={isSeedingSample}
          className="flex items-center gap-2 rounded-xl bg-black px-4 py-2.5 text-xs font-semibold text-white hover:bg-neutral-800 transition shadow-sm disabled:opacity-50"
        >
          {isSeedingSample ? <Loader2 size={16} className="animate-spin" /> : <Zap size={16} className="text-yellow-400 fill-yellow-400" />}
          <span>1-Click Load Sample Demo Store Data</span>
        </button>
      </div>

      {successBanner && (
        <div className="flex flex-wrap items-center justify-between gap-4 rounded-xl border border-emerald-300 bg-emerald-50 p-4 text-emerald-900 shadow-sm">
          <div className="flex items-center gap-3">
            <CheckCircle className="text-emerald-600 shrink-0" size={20} />
            <div className="text-xs font-semibold">{successBanner}</div>
          </div>
          <button
            onClick={() => navigate('/')}
            className="flex items-center gap-2 rounded-lg bg-emerald-700 px-4 py-2 text-xs font-semibold text-white hover:bg-emerald-800 transition"
          >
            <span>Open Executive Dashboard</span>
            <ArrowRight size={14} />
          </button>
        </div>
      )}

      {message && !successBanner && (
        <div className={`flex items-center gap-2.5 rounded-xl border px-4 py-3 text-xs font-medium ${
          isError ? 'border-red-200 bg-red-50 text-red-800' : 'border-slate-200 bg-surface text-textPrimary'
        }`}>
          {isError ? <AlertCircle size={16} className="text-red-600 shrink-0" /> : <Loader2 size={16} className="animate-spin text-black shrink-0" />}
          <span>{message}</span>
        </div>
      )}

      <div className="flex flex-wrap gap-2 border-b border-surface-border pb-2">
        {tabs.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            onClick={() => {
              setTab(id)
              setMessage('')
              setIsError(false)
            }}
            className={`flex items-center gap-2 rounded-lg px-4 py-2 text-xs font-semibold transition ${
              tab === id ? 'bg-black text-white' : 'text-textSecondary hover:bg-surface hover:text-textPrimary'
            }`}
          >
            <Icon size={16} /> {label}
          </button>
        ))}
      </div>

      {tab === 'files' && (
        <div className="card space-y-4">
          <div>
            <h2 className="font-semibold text-textPrimary">Upload CSV / Excel Files</h2>
            <p className="text-xs text-textSecondary mt-1">
              Select one or multiple files (`orders.csv`, `products.csv`, `customers.csv`, `inventory.csv`).
            </p>
          </div>

          <div className="rounded-xl border-2 border-dashed border-surface-border p-6 text-center hover:border-black transition-colors">
            <input
              type="file"
              multiple
              accept=".csv,.xlsx,.xls"
              onChange={handleFileUpload}
              className="block w-full text-xs text-textSecondary file:mr-4 file:rounded-lg file:border-0 file:bg-black file:px-4 file:py-2 file:text-xs file:font-semibold file:text-white hover:file:bg-neutral-800 cursor-pointer"
            />
          </div>

          {uploadResults.length > 0 && (
            <div className="space-y-4 pt-2">
              <h3 className="text-xs font-semibold uppercase text-textSecondary">Inspected Datasets</h3>
              {uploadResults.map((r: any) => {
                const isImported = importedJobs[r.job_id] !== undefined
                const isImporting = importingJobId === r.job_id

                return (
                  <div key={r.job_id} className="rounded-xl border border-surface-border p-4 bg-white space-y-3">
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <div>
                        <div className="font-semibold text-sm text-textPrimary">{r.filename}</div>
                        <div className="text-xs text-textSecondary mt-0.5">
                          Detected Dataset: <span className="font-semibold text-black uppercase">{r.inspection.detected_dataset || 'Unknown'}</span>
                        </div>
                      </div>

                      {isImported ? (
                        <div className="flex items-center gap-1.5 rounded-full bg-emerald-50 px-3 py-1 text-xs font-semibold text-emerald-700 border border-emerald-200">
                          <CheckCircle size={14} />
                          <span>Imported {importedJobs[r.job_id]} Records</span>
                        </div>
                      ) : (
                        <button
                          onClick={() => importJob(r.job_id)}
                          disabled={isImporting}
                          className="btn-primary text-xs"
                        >
                          {isImporting ? (
                            <>
                              <Loader2 size={14} className="animate-spin" />
                              <span>Importing...</span>
                            </>
                          ) : (
                            <span>Import Valid Records</span>
                          )}
                        </button>
                      )}
                    </div>

                    <div className="grid grid-cols-4 gap-2 text-center text-xs tabular-nums font-medium">
                      <div className="rounded-lg bg-surface p-2 border border-surface-border">Total: {r.validation.total_records}</div>
                      <div className="rounded-lg bg-emerald-50 p-2 text-emerald-700 border border-emerald-200">Valid: {r.validation.valid_records}</div>
                      <div className="rounded-lg bg-amber-50 p-2 text-amber-700 border border-amber-200">Warnings: {r.validation.warning_records}</div>
                      <div className="rounded-lg bg-red-50 p-2 text-red-700 border border-red-200">Errors: {r.validation.error_records}</div>
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </div>
      )}

      {tab === 'database' && (
        <div className="card space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div>
              <h2 className="font-semibold text-textPrimary">Connect External Database</h2>
              <p className="text-xs text-textSecondary mt-0.5">Direct SQL database connection (PostgreSQL, MySQL, SQL Server).</p>
            </div>
            <button
              onClick={handleAutoFillPostgres}
              type="button"
              className="text-xs font-semibold text-black underline hover:text-neutral-700"
            >
              ⚡ Auto-Fill Local PostgreSQL (Port 5433)
            </button>
          </div>

          <div className="grid gap-4 md:grid-cols-2">
            <div>
              <label className="mb-1 block text-xs font-medium text-textSecondary">Connection Name</label>
              <input className="input text-xs" value={dbForm.name} onChange={(e) => setDbForm({ ...dbForm, name: e.target.value })} />
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-textSecondary">Database Type</label>
              <select className="input text-xs" value={dbForm.db_type} onChange={(e) => setDbForm({ ...dbForm, db_type: e.target.value })}>
                <option value="postgresql">PostgreSQL</option>
                <option value="mysql">MySQL</option>
                <option value="sqlserver">SQL Server</option>
              </select>
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-textSecondary">Host</label>
              <input className="input text-xs" value={dbForm.host} onChange={(e) => setDbForm({ ...dbForm, host: e.target.value })} placeholder="localhost" />
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-textSecondary">Port</label>
              <input type="number" className="input text-xs" value={dbForm.port} onChange={(e) => setDbForm({ ...dbForm, port: Number(e.target.value) })} />
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-textSecondary">Database Name</label>
              <input className="input text-xs" value={dbForm.database_name} onChange={(e) => setDbForm({ ...dbForm, database_name: e.target.value })} />
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-textSecondary">Username</label>
              <input className="input text-xs" value={dbForm.username} onChange={(e) => setDbForm({ ...dbForm, username: e.target.value })} />
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-textSecondary">Password</label>
              <input type="password" className="input text-xs" value={dbForm.password} onChange={(e) => setDbForm({ ...dbForm, password: e.target.value })} />
            </div>
            <div className="flex items-center gap-2 pt-6">
              <input type="checkbox" id="ssl" checked={dbForm.ssl} onChange={(e) => setDbForm({ ...dbForm, ssl: e.target.checked })} />
              <label htmlFor="ssl" className="text-xs text-textSecondary">Use SSL Mode</label>
            </div>
          </div>

          <div className="flex flex-wrap gap-3 pt-2">
            <button
              onClick={testConnection}
              disabled={isTestingConnection || isConnectingDb}
              className="btn-secondary text-xs flex items-center gap-2"
            >
              {isTestingConnection && <Loader2 size={14} className="animate-spin" />}
              <span>Test Connection</span>
            </button>

            <button
              onClick={connectDatabase}
              disabled={isConnectingDb || isTestingConnection}
              className="btn-primary text-xs flex items-center gap-2"
            >
              {isConnectingDb ? (
                <>
                  <Loader2 size={14} className="animate-spin" />
                  <span>Connecting & Syncing...</span>
                </>
              ) : (
                <span>Connect Database</span>
              )}
            </button>
          </div>
        </div>
      )}

      {tab === 'integrations' && (
        <div className="space-y-4">
          <div className="card space-y-4">
            <div className="flex items-center gap-2"><Store size={18} /><h2 className="font-semibold text-textPrimary">Shopify</h2></div>
            <div className="grid gap-3 md:grid-cols-2">
              <input className="input text-xs" placeholder="your-store.myshopify.com" value={shopifyForm.shop_domain}
                onChange={(e) => setShopifyForm({ ...shopifyForm, shop_domain: e.target.value })} />
              <input className="input text-xs" type="password" placeholder="Admin API Access Token" value={shopifyForm.access_token}
                onChange={(e) => setShopifyForm({ ...shopifyForm, access_token: e.target.value })} />
            </div>
            <button onClick={connectShopify} disabled={isConnectingShopify} className="btn-primary text-xs flex items-center gap-2">
              {isConnectingShopify && <Loader2 size={14} className="animate-spin" />}
              <span>Connect Shopify Store</span>
            </button>
          </div>

          <div className="card space-y-4">
            <div className="flex items-center gap-2"><Store size={18} /><h2 className="font-semibold text-textPrimary">WooCommerce</h2></div>
            <div className="grid gap-3 md:grid-cols-2">
              <input className="input text-xs" placeholder="https://yourstore.com" value={wooForm.store_url}
                onChange={(e) => setWooForm({ ...wooForm, store_url: e.target.value })} />
              <input className="input text-xs" placeholder="Consumer Key" value={wooForm.consumer_key}
                onChange={(e) => setWooForm({ ...wooForm, consumer_key: e.target.value })} />
              <input className="input text-xs" type="password" placeholder="Consumer Secret" value={wooForm.consumer_secret}
                onChange={(e) => setWooForm({ ...wooForm, consumer_secret: e.target.value })} />
            </div>
            <button onClick={connectWoo} disabled={isConnectingWoo} className="btn-primary text-xs flex items-center gap-2">
              {isConnectingWoo && <Loader2 size={14} className="animate-spin" />}
              <span>Connect WooCommerce Store</span>
            </button>
          </div>
        </div>
      )}

      {tab === 'agent' && (
        <div className="card space-y-4">
          <h2 className="font-semibold text-textPrimary">Local Database Connector Agent</h2>
          <p className="text-xs text-textSecondary">
            For local databases running on private networks without public IP access, generate an Agent Token and execute `connector/agent.py`.
          </p>
          {!agentToken ? (
            <button onClick={registerAgent} className="btn-primary text-xs">Generate Agent Token</button>
          ) : (
            <div className="space-y-3 rounded-lg border border-surface-border bg-surface p-4 text-xs font-mono">
              <div className="text-textSecondary">Your Agent Token:</div>
              <div className="select-all rounded bg-white p-2 border border-surface-border text-black font-bold">{agentToken}</div>
              <div className="text-textSecondary pt-2 font-sans">Run locally:</div>
              <code className="block rounded bg-black p-2 text-white font-mono">
                python connector/agent.py http://localhost:8000 {agentToken}
              </code>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
