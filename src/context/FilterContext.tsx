import { createContext, useContext, useState, ReactNode } from 'react'

export interface GlobalFilters {
  startDate: string
  endDate: string
  comparePrevious: boolean
  granularity: 'daily' | 'weekly' | 'monthly' | 'quarterly' | 'yearly'
  categoryId?: number
  productId?: number
  region?: string
  country?: string
  salesChannel?: string
  orderStatus?: string
  paymentMethod?: string
}

interface FilterContextType {
  filters: GlobalFilters
  setFilters: (f: Partial<GlobalFilters>) => void
}

const defaultFilters: GlobalFilters = {
  startDate: new Date(Date.now() - 30 * 86400000).toISOString().slice(0, 10),
  endDate: '2026-11-30',
  comparePrevious: true,
  granularity: 'daily',
}

const FilterContext = createContext<FilterContextType | null>(null)

export function FilterProvider({ children }: { children: ReactNode }) {
  const [filters, setFiltersState] = useState<GlobalFilters>(defaultFilters)
  const setFilters = (partial: Partial<GlobalFilters>) => {
    setFiltersState((prev) => ({ ...prev, ...partial }))
  }
  return (
    <FilterContext.Provider value={{ filters, setFilters }}>
      {children}
    </FilterContext.Provider>
  )
}

export function useFilters() {
  const ctx = useContext(FilterContext)
  if (!ctx) throw new Error('useFilters must be used within FilterProvider')
  return ctx
}

export function filtersToPayload(filters: GlobalFilters) {
  return {
    start_date: filters.startDate ? new Date(filters.startDate).toISOString() : null,
    end_date: filters.endDate ? new Date(filters.endDate + 'T23:59:59').toISOString() : null,
    compare_previous: filters.comparePrevious,
    granularity: filters.granularity,
    category_id: filters.categoryId,
    product_id: filters.productId,
    region: filters.region,
    country: filters.country,
    sales_channel: filters.salesChannel,
    order_status: filters.orderStatus,
    payment_method: filters.paymentMethod,
  }
}
