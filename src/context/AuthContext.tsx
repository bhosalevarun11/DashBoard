import { createContext, useContext, useEffect, useState, ReactNode } from 'react'
import api, { Business, User, setAccessToken } from '../lib/api'

interface AuthContextType {
  user: User | null
  businesses: Business[]
  activeBusiness: Business | null
  setActiveBusiness: (b: Business | null) => void
  login: (email: string, password: string) => Promise<void>
  register: (name: string, email: string, password: string) => Promise<void>
  logout: () => Promise<void>
  refreshBusinesses: () => Promise<void>
  loading: boolean
}

const AuthContext = createContext<AuthContextType | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [businesses, setBusinesses] = useState<Business[]>([])
  const [activeBusiness, setActiveBusiness] = useState<Business | null>(null)
  const [loading, setLoading] = useState(true)

  const refreshBusinesses = async () => {
    try {
      const { data } = await api.get<Business[]>('/auth/businesses')
      setBusinesses(data)
      if (data.length && !activeBusiness) {
        setActiveBusiness(data[0])
      }
    } catch {
      // Ignore if unauthenticated
    }
  }

  useEffect(() => {
    // Purge any legacy raw tokens from localStorage to prevent XSS exposure
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')

    // Attempt initial silent refresh using HttpOnly cookie
    api.post('/auth/refresh')
      .then(async ({ data }) => {
        setAccessToken(data.access_token)
        const me = await api.get<User>('/auth/me')
        setUser(me.data)
        await refreshBusinesses()
      })
      .catch(() => {
        setAccessToken(null)
      })
      .finally(() => setLoading(false))
  }, [])

  const login = async (email: string, password: string) => {
    const { data } = await api.post('/auth/login', { email, password })
    setAccessToken(data.access_token)
    const me = await api.get<User>('/auth/me')
    setUser(me.data)
    await refreshBusinesses()
  }

  const register = async (name: string, email: string, password: string) => {
    const { data } = await api.post('/auth/register', { name, email, password })
    setAccessToken(data.access_token)
    const me = await api.get<User>('/auth/me')
    setUser(me.data)
    await refreshBusinesses()
  }

  const logout = async () => {
    try {
      await api.post('/auth/logout')
    } catch {
      // Ignore network errors on logout
    } finally {
      setAccessToken(null)
      setUser(null)
      setBusinesses([])
      setActiveBusiness(null)
    }
  }

  return (
    <AuthContext.Provider value={{
      user, businesses, activeBusiness, setActiveBusiness,
      login, register, logout, refreshBusinesses, loading,
    }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
