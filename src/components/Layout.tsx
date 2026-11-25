import { ReactNode, useState } from 'react'
import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import {
  AlertTriangle, BarChart3, Boxes, Globe, LayoutDashboard, Lightbulb,
  LineChart, LogOut, Package, RefreshCw, Settings, ShoppingCart, TrendingUp,
  Upload, Users, Wallet, PieChart, Layers, Filter, Menu, X, Sparkles,
} from 'lucide-react'

import { useAuth } from '../context/AuthContext'
import { useFilters } from '../context/FilterContext'
import AIQueryDrawer from './AIQueryDrawer'

const navItems = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/sales', label: 'Sales', icon: TrendingUp },
  { to: '/products', label: 'Products', icon: Package },
  { to: '/categories', label: 'Categories', icon: BarChart3 },
  { to: '/customers', label: 'Customers', icon: Users },
  { to: '/rfm', label: 'RFM', icon: Users },
  { to: '/cohorts', label: 'Cohorts', icon: Layers },
  { to: '/funnel', label: 'Funnel', icon: Filter },
  { to: '/orders', label: 'Orders', icon: ShoppingCart },
  { to: '/inventory', label: 'Inventory', icon: Boxes },
  { to: '/returns', label: 'Returns', icon: RefreshCw },
  { to: '/marketing', label: 'Marketing', icon: LineChart },
  { to: '/geography', label: 'Geography', icon: Globe },
  { to: '/profitability', label: 'Profitability', icon: Wallet },
  { to: '/pareto', label: 'Pareto (80/20)', icon: PieChart },
  { to: '/forecast', label: 'Forecast', icon: LineChart },
  { to: '/insights', label: 'Insights', icon: Lightbulb },
  { to: '/alerts', label: 'Alerts', icon: AlertTriangle },
  { to: '/reports', label: 'Reports', icon: BarChart3 },
  { to: '/connect', label: 'Connect Data', icon: Upload },
  { to: '/settings', label: 'Settings', icon: Settings },
]

export default function AppLayout({ children }: { children?: ReactNode }) {
  const { user, businesses, activeBusiness, setActiveBusiness, logout } = useAuth()
  const { filters, setFilters } = useFilters()
  const navigate = useNavigate()
  const [mobileOpen, setMobileOpen] = useState(false)
  const [aiDrawerOpen, setAiDrawerOpen] = useState(false)

  return (
    <div className="flex min-h-screen bg-white text-textPrimary antialiased">
      {/* Mobile Backdrop */}
      {mobileOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/40 backdrop-blur-sm lg:hidden"
          onClick={() => setMobileOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside
        className={`fixed inset-y-0 left-0 z-50 flex w-64 flex-col border-r border-surface-border bg-white transition-transform duration-200 lg:translate-x-0 ${
          mobileOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        <div className="flex items-center justify-between border-b border-surface-border px-5 py-4">
          <div>
            <div className="text-base font-bold text-textPrimary">Analytics BI</div>
            <div className="text-xs text-textSecondary">Intelligence Platform</div>
          </div>
          <button onClick={() => setMobileOpen(false)} className="lg:hidden text-textSecondary">
            <X size={20} />
          </button>
        </div>

        <nav className="flex-1 overflow-y-auto p-3 space-y-1">
          {navItems.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              end={to === '/'}
              onClick={() => setMobileOpen(false)}
              className={({ isActive }: { isActive: boolean }) => `sidebar-link ${isActive ? 'sidebar-link-active' : ''}`}
            >
              <Icon size={18} />
              <span className="truncate">{label}</span>
            </NavLink>
          ))}
        </nav>

        <div className="border-t border-surface-border p-3">
          <button
            onClick={() => {
              logout()
              navigate('/login')
            }}
            className="sidebar-link w-full text-red-600 hover:bg-red-50 hover:text-red-700"
          >
            <LogOut size={18} />
            <span>Logout</span>
          </button>
        </div>
      </aside>

      {/* Main Content Area */}
      <div className="flex flex-1 flex-col lg:pl-64 min-w-0">
        {/* Sticky Top Bar */}
        <header className="sticky top-0 z-30 border-b border-surface-border bg-white/95 backdrop-blur px-4 lg:px-8 py-3">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-3">
              <button
                onClick={() => setMobileOpen(true)}
                className="lg:hidden p-1 text-textSecondary hover:text-textPrimary"
              >
                <Menu size={22} />
              </button>

              <div className="relative">
                <select
                  aria-label="Active Business Selector"
                  className="input w-auto min-w-[180px] font-semibold pr-8 bg-surface text-xs py-1.5"
                  value={activeBusiness?.id ?? ''}
                  onChange={(e) => {
                    const b = businesses.find((x) => x.id === Number(e.target.value))
                    setActiveBusiness(b ?? null)
                  }}
                >
                  {businesses.length === 0 && <option value="">No business selected</option>}
                  {businesses.map((b) => (
                    <option key={b.id} value={b.id}>
                      {b.name} ({b.currency})
                    </option>
                  ))}
                </select>
              </div>
            </div>

            {/* Global Date, Granularity & Compare Toolbar */}
            <div className="flex flex-wrap items-center gap-2.5">
              {/* Grouped Date Range Container */}
              <div className="flex items-center rounded-lg border border-surface-border bg-surface px-2.5 py-1 space-x-1.5 shadow-sm">
                <input
                  type="date"
                  aria-label="Start Date"
                  className="bg-transparent text-xs font-medium text-textPrimary focus:outline-none cursor-pointer"
                  value={filters.startDate}
                  onChange={(e) => setFilters({ startDate: e.target.value })}
                />
                <span className="text-xs font-bold text-textTertiary">→</span>
                <input
                  type="date"
                  aria-label="End Date"
                  className="bg-transparent text-xs font-medium text-textPrimary focus:outline-none cursor-pointer"
                  value={filters.endDate}
                  onChange={(e) => setFilters({ endDate: e.target.value })}
                />
              </div>

              {/* Granularity Selector */}
              <select
                aria-label="Date Granularity"
                className="input w-auto text-xs py-1.5 bg-surface font-medium"
                value={filters.granularity}
                onChange={(e) => setFilters({ granularity: e.target.value as GlobalFilters['granularity'] })}
              >
                <option value="daily">Daily</option>
                <option value="weekly">Weekly</option>
                <option value="monthly">Monthly</option>
                <option value="quarterly">Quarterly</option>
                <option value="yearly">Yearly</option>
              </select>

              {/* Compare Toggle */}
              <label className="flex items-center gap-1.5 text-xs text-textSecondary cursor-pointer bg-surface px-2.5 py-1.5 rounded-lg border border-surface-border font-medium hover:text-textPrimary transition">
                <input
                  type="checkbox"
                  className="rounded border-gray-300 text-black focus:ring-black cursor-pointer"
                  checked={filters.comparePrevious}
                  onChange={(e) => setFilters({ comparePrevious: e.target.checked })}
                />
                <span>Compare</span>
              </label>

              {/* AI Assistant Trigger */}
              <button
                onClick={() => setAiDrawerOpen(true)}
                className="flex items-center gap-1.5 rounded-lg bg-black px-3 py-1.5 text-xs font-semibold text-white shadow-sm hover:bg-neutral-800 transition"
              >
                <Sparkles className="h-3.5 w-3.5 text-amber-300 animate-pulse" />
                <span>AI Assistant (Moby)</span>
              </button>
            </div>

            <div className="hidden xl:block text-xs font-semibold text-textPrimary">
              {user?.name}
            </div>
          </div>
        </header>

        {/* Page Main View */}
        <main className="flex-1 p-4 lg:p-8 min-w-0">{children ?? <Outlet />}</main>
        <AIQueryDrawer isOpen={aiDrawerOpen} onClose={() => setAiDrawerOpen(false)} />
      </div>
    </div>
  )
}

type GlobalFilters = import('../context/FilterContext').GlobalFilters
