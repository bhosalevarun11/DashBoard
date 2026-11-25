import axios from 'axios'

let inMemoryAccessToken: string | null = null

export function setAccessToken(token: string | null) {
  inMemoryAccessToken = token
}

export function getAccessToken(): string | null {
  return inMemoryAccessToken
}

const envApiUrl = (import.meta as any).env?.VITE_API_URL as string | undefined
export const API_BASE_URL = envApiUrl ? (envApiUrl.replace(/\/+$/, '') + '/api') : '/api'

const api = axios.create({
  baseURL: API_BASE_URL,
  withCredentials: true,
})

api.interceptors.request.use((config) => {
  if (inMemoryAccessToken) {
    config.headers.Authorization = `Bearer ${inMemoryAccessToken}`
  }
  return config
})

// Auto-refresh interceptor for 401 responses
let isRefreshing = false
let failedQueue: Array<{ resolve: (token: string) => void; reject: (err: unknown) => void }> = []

const processQueue = (error: unknown, token: string | null = null) => {
  failedQueue.forEach((prom) => {
    if (error) {
      prom.reject(error)
    } else if (token) {
      prom.resolve(token)
    }
  })
  failedQueue = []
}

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config
    if (error.response?.status === 401 && !originalRequest._retry && !originalRequest.url?.includes('/auth/login') && !originalRequest.url?.includes('/auth/refresh')) {
      if (isRefreshing) {
        return new Promise((resolve, reject) => {
          failedQueue.push({ resolve, reject })
        }).then((token) => {
          originalRequest.headers.Authorization = `Bearer ${token}`
          return api(originalRequest)
        })
      }

      originalRequest._retry = true
      isRefreshing = true

      try {
        const { data } = await axios.post(API_BASE_URL + '/auth/refresh', {}, { withCredentials: true })
        setAccessToken(data.access_token)
        processQueue(null, data.access_token)
        originalRequest.headers.Authorization = `Bearer ${data.access_token}`
        return api(originalRequest)
      } catch (refreshErr) {
        processQueue(refreshErr, null)
        setAccessToken(null)
        localStorage.removeItem('access_token')
        localStorage.removeItem('refresh_token')
        return Promise.reject(refreshErr)
      } finally {
        isRefreshing = false
      }
    }
    return Promise.reject(error)
  }
)

export default api

export interface User {
  id: number
  name: string
  email: string
  role: string
}

export interface Business {
  id: number
  name: string
  currency: string
  timezone: string
}

export interface KPICard {
  key: string
  label: string
  value: number | string
  change_pct?: number | null
  format?: string
  unavailable_reason?: string | null
}

export interface AnalyticsResponse {
  kpis: KPICard[]
  charts: { name: string; data: Record<string, unknown>[] }[]
  tables?: { name: string; rows: Record<string, unknown>[] }[]
  meta?: Record<string, unknown>
}

export interface DataAvailability {
  orders: boolean
  products: boolean
  customers: boolean
  inventory: boolean
  returns: boolean
  marketing: boolean
  events: boolean
}

export interface Insight {
  id: number
  insight_type: string
  title: string
  description: string
  impact?: string
  recommended_action?: string
}

export interface Alert {
  id: number
  severity: string
  title: string
  message: string
  category?: string
  is_read: boolean
}

export interface AIQueryResponse {
  query: string
  intent: string
  answer: string
  data: Record<string, unknown>[]
  chart_type: string
}

export interface SavedCustomReport {
  id: number
  name: string
  metric: string
  dimension: string
  date_range_preset: string
  chart_type: string
  filters_json?: string
  created_at: string
}

export interface ScheduledReport {
  id: number
  name: string
  frequency: string
  recipient_email?: string
  webhook_url?: string
  is_active: boolean
  last_sent_at?: string
  created_at: string
}
