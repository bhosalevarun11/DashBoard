import { lazy, Suspense } from 'react'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { AuthProvider, useAuth } from './context/AuthContext'
import { FilterProvider } from './context/FilterContext'
import AppLayout from './components/Layout'

const LoginPage = lazy(() => import('./pages/LoginPage'))
const RegisterPage = lazy(() => import('./pages/RegisterPage'))
const DashboardPage = lazy(() => import('./pages/DashboardPage'))
const ConnectDataPage = lazy(() => import('./pages/ConnectDataPage'))
const AnalyticsPage = lazy(() => import('./pages/AnalyticsPage'))
const ReportsPage = lazy(() => import('./pages/ReportsPage'))

const CategoryAnalyticsPage = lazy(() => import('./pages/AdvancedAnalyticsPages').then(m => ({ default: m.CategoryAnalyticsPage })))
const CohortPage = lazy(() => import('./pages/AdvancedAnalyticsPages').then(m => ({ default: m.CohortPage })))
const ConversionFunnelPage = lazy(() => import('./pages/AdvancedAnalyticsPages').then(m => ({ default: m.ConversionFunnelPage })))
const ForecastPage = lazy(() => import('./pages/AdvancedAnalyticsPages').then(m => ({ default: m.ForecastPage })))
const GeographyPage = lazy(() => import('./pages/AdvancedAnalyticsPages').then(m => ({ default: m.GeographyPage })))
const ParetoPage = lazy(() => import('./pages/AdvancedAnalyticsPages').then(m => ({ default: m.ParetoPage })))
const ProfitabilityPage = lazy(() => import('./pages/AdvancedAnalyticsPages').then(m => ({ default: m.ProfitabilityPage })))
const ReturnsPage = lazy(() => import('./pages/AdvancedAnalyticsPages').then(m => ({ default: m.ReturnsPage })))
const MarketingPage = lazy(() => import('./pages/AdvancedAnalyticsPages').then(m => ({ default: m.MarketingPage })))

const AlertsPage = lazy(() => import('./pages/OtherPages').then(m => ({ default: m.AlertsPage })))
const InsightsPage = lazy(() => import('./pages/OtherPages').then(m => ({ default: m.InsightsPage })))
const OrdersPage = lazy(() => import('./pages/OtherPages').then(m => ({ default: m.OrdersPage })))
const SettingsPage = lazy(() => import('./pages/OtherPages').then(m => ({ default: m.SettingsPage })))

function PrivateRoute({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth()
  if (loading) return <div className="flex min-h-screen items-center justify-center font-medium text-slate-500">Loading Dashboard...</div>
  if (!user) return <Navigate to="/login" replace />
  return <AppLayout>{children}</AppLayout>
}

function PageLoader() {
  return (
    <div className="flex h-64 w-full items-center justify-center text-sm font-medium text-textSecondary">
      <div className="h-6 w-6 animate-spin rounded-full border-2 border-brand-600 border-t-transparent mr-2" />
      <span>Loading Module...</span>
    </div>
  )
}

function AppRoutes() {
  const { activeBusiness } = useAuth()
  const bid = activeBusiness?.id

  return (
    <Suspense fallback={<PageLoader />}>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
        <Route path="/" element={<PrivateRoute><DashboardPage /></PrivateRoute>} />
        <Route path="/connect" element={<PrivateRoute><ConnectDataPage /></PrivateRoute>} />
        <Route path="/sales" element={<PrivateRoute><AnalyticsPage title="Sales Analytics" endpoint={`/analytics/sales/${bid}`} /></PrivateRoute>} />
        <Route path="/products" element={<PrivateRoute><AnalyticsPage title="Product Analytics" endpoint={`/analytics/products/${bid}`} showTable /></PrivateRoute>} />
        <Route path="/categories" element={<PrivateRoute><CategoryAnalyticsPage /></PrivateRoute>} />
        <Route path="/customers" element={<PrivateRoute><AnalyticsPage title="Customer Analytics" endpoint={`/analytics/customers/${bid}`} emptyMessage="Customer Analytics unavailable because customer data has not been uploaded." /></PrivateRoute>} />
        <Route path="/rfm" element={<PrivateRoute><AnalyticsPage title="RFM Analysis" endpoint={`/analytics/rfm/${bid}`} method="get" showTable /></PrivateRoute>} />
        <Route path="/cohorts" element={<PrivateRoute><CohortPage /></PrivateRoute>} />
        <Route path="/funnel" element={<PrivateRoute><ConversionFunnelPage /></PrivateRoute>} />
        <Route path="/inventory" element={<PrivateRoute><AnalyticsPage title="Inventory Analytics" endpoint={`/analytics/inventory/${bid}`} method="get" showTable /></PrivateRoute>} />
        <Route path="/returns" element={<PrivateRoute><ReturnsPage /></PrivateRoute>} />
        <Route path="/marketing" element={<PrivateRoute><MarketingPage /></PrivateRoute>} />
        <Route path="/geography" element={<PrivateRoute><GeographyPage /></PrivateRoute>} />
        <Route path="/profitability" element={<PrivateRoute><ProfitabilityPage /></PrivateRoute>} />
        <Route path="/pareto" element={<PrivateRoute><ParetoPage /></PrivateRoute>} />
        <Route path="/forecast" element={<PrivateRoute><ForecastPage /></PrivateRoute>} />
        <Route path="/insights" element={<PrivateRoute><InsightsPage /></PrivateRoute>} />
        <Route path="/alerts" element={<PrivateRoute><AlertsPage /></PrivateRoute>} />
        <Route path="/orders" element={<PrivateRoute><OrdersPage /></PrivateRoute>} />
        <Route path="/reports" element={<PrivateRoute><ReportsPage /></PrivateRoute>} />
        <Route path="/settings" element={<PrivateRoute><SettingsPage /></PrivateRoute>} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Suspense>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <FilterProvider>
          <AppRoutes />
        </FilterProvider>
      </AuthProvider>
    </BrowserRouter>
  )
}
