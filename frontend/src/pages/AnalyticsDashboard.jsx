import { useCallback, useEffect, useState } from 'react'
import AnalyticsFilters from '../components/analytics/AnalyticsFilters'
import AnalyticsSection from '../components/analytics/AnalyticsSection'
import CustomerAnalyticsTable from '../components/analytics/CustomerAnalyticsTable'
import EmailAnalytics from '../components/analytics/EmailAnalytics'
import OverviewCards from '../components/analytics/OverviewCards'
import ProductAnalyticsTable from '../components/analytics/ProductAnalyticsTable'
import SalesTrendChart from '../components/analytics/SalesTrendChart'
import { CustomerTypeSplit, GovernorateAnalytics, PriceTypeSplit } from '../components/analytics/SplitAnalytics'
import {
  getAnalyticsByCustomer, getAnalyticsByGovernorate, getAnalyticsFilterOptions, getAnalyticsOverview,
  getCustomerTypeAnalytics, getEmailDeliveryAnalytics, getPriceTypeAnalytics, getProductAnalytics,
  getSalesOverTime,
} from '../services/api'

const EMPTY_FILTERS = {
  date_from: '', date_to: '', governorate: '', customer_type: '',
  selected_price_type: '', customer_name: '', product_name: '',
}
const EMPTY_OPTIONS = { governorates: [], customer_types: [], price_types: [] }
const CUSTOMER_DEFAULT = { limit: 10, offset: 0 }
const PRODUCT_DEFAULT = { limit: 10, offset: 0 }

function AnalyticsDashboard() {
  const [options, setOptions] = useState(EMPTY_OPTIONS)
  const [draftFilters, setDraftFilters] = useState(EMPTY_FILTERS)
  const [appliedFilters, setAppliedFilters] = useState(EMPTY_FILTERS)
  const [filterError, setFilterError] = useState('')
  const [granularity, setGranularity] = useState('daily')
  const [customerPage, setCustomerPage] = useState(CUSTOMER_DEFAULT)
  const [productPage, setProductPage] = useState(PRODUCT_DEFAULT)
  const [customerSort, setCustomerSort] = useState({ sort_by: 'total_sales', sort_direction: 'desc' })
  const [productSort, setProductSort] = useState({ sort_by: 'total_quantity', sort_direction: 'desc' })
  const [refreshKey, setRefreshKey] = useState(0)
  const [data, setData] = useState({})
  const [loading, setLoading] = useState({})
  const [errors, setErrors] = useState({})

  const runSection = useCallback(async (key, request) => {
    setLoading((current) => ({ ...current, [key]: true }))
    setErrors((current) => ({ ...current, [key]: false }))
    try {
      const result = await request()
      setData((current) => ({ ...current, [key]: result }))
    } catch {
      setErrors((current) => ({ ...current, [key]: true }))
    } finally {
      setLoading((current) => ({ ...current, [key]: false }))
    }
  }, [])

  const loadPrimary = useCallback(() => {
    runSection('overview', () => getAnalyticsOverview(appliedFilters))
    runSection('governorates', () => getAnalyticsByGovernorate(appliedFilters))
    runSection('priceTypes', () => getPriceTypeAnalytics(appliedFilters))
    runSection('customerTypes', () => getCustomerTypeAnalytics(appliedFilters))
    runSection('email', () => getEmailDeliveryAnalytics(appliedFilters))
  }, [appliedFilters, runSection])

  const loadSales = useCallback(() => runSection('sales', () => getSalesOverTime(appliedFilters, granularity)), [appliedFilters, granularity, runSection])
  const loadCustomers = useCallback(() => runSection('customers', () => getAnalyticsByCustomer(appliedFilters, customerPage, customerSort)), [appliedFilters, customerPage, customerSort, runSection])
  const loadProducts = useCallback(() => runSection('products', () => getProductAnalytics(appliedFilters, productPage, productSort)), [appliedFilters, productPage, productSort, runSection])

  useEffect(() => {
    getAnalyticsFilterOptions().then(setOptions).catch(() => setErrors((current) => ({ ...current, filters: true })))
  }, [])
  useEffect(() => { Promise.resolve().then(loadPrimary) }, [loadPrimary, refreshKey])
  useEffect(() => { Promise.resolve().then(loadSales) }, [loadSales, refreshKey])
  useEffect(() => { Promise.resolve().then(loadCustomers) }, [loadCustomers, refreshKey])
  useEffect(() => { Promise.resolve().then(loadProducts) }, [loadProducts, refreshKey])

  const applyFilters = () => {
    if (draftFilters.date_from && draftFilters.date_to && draftFilters.date_from > draftFilters.date_to) {
      setFilterError('Date From must be on or before Date To.')
      return
    }
    setFilterError('')
    setCustomerPage(CUSTOMER_DEFAULT)
    setProductPage(PRODUCT_DEFAULT)
    setAppliedFilters({ ...draftFilters })
  }
  const resetFilters = () => {
    setFilterError('')
    setDraftFilters(EMPTY_FILTERS)
    setAppliedFilters(EMPTY_FILTERS)
    setCustomerPage(CUSTOMER_DEFAULT)
    setProductPage(PRODUCT_DEFAULT)
  }
  const toggleSort = (setter, current, field) => {
    setter({
      sort_by: field,
      sort_direction: current.sort_by === field && current.sort_direction === 'desc' ? 'asc' : 'desc',
    })
  }
  const initialLoading = !data.overview && loading.overview

  return (
    <div className="analytics-dashboard">
      <div className="analytics-hero">
        <div><span className="analytics-eyebrow">Business intelligence</span><h1>Order Analytics</h1>
          <p>Read-only performance reporting from persisted orders and delivery attempts.</p></div>
        {initialLoading && <span className="analytics-loading-pill">Loading dashboard…</span>}
      </div>
      <AnalyticsFilters options={options} draft={draftFilters} onChange={setDraftFilters} onApply={applyFilters}
        onReset={resetFilters} onRefresh={() => setRefreshKey((key) => key + 1)}
        error={filterError || (errors.filters ? 'Filter options could not be loaded. You can still use dates and search fields.' : '')}
        loading={Object.values(loading).some(Boolean)} />

      <AnalyticsSection title="Overview" subtitle="Key order, sales, quantity, customer, and delivery totals."
        loading={loading.overview} error={errors.overview} onRetry={loadPrimary}>
        <OverviewCards data={data.overview} />
      </AnalyticsSection>
      <AnalyticsSection title="Sales Trend" subtitle="Sales values with the underlying operational figures."
        loading={loading.sales} error={errors.sales} onRetry={loadSales}>
        <SalesTrendChart rows={data.sales || []} granularity={granularity} onGranularityChange={setGranularity} />
      </AnalyticsSection>

      <div className="analytics-two-column">
        <AnalyticsSection title="Sales by Governorate" loading={loading.governorates} error={errors.governorates} onRetry={loadPrimary}>
          <GovernorateAnalytics rows={data.governorates || []} />
        </AnalyticsSection>
        <AnalyticsSection title="Price-Type Split" loading={loading.priceTypes} error={errors.priceTypes} onRetry={loadPrimary}>
          <PriceTypeSplit rows={data.priceTypes || []} />
        </AnalyticsSection>
        <AnalyticsSection title="Customer-Type Split" loading={loading.customerTypes} error={errors.customerTypes} onRetry={loadPrimary}>
          <CustomerTypeSplit rows={data.customerTypes || []} />
        </AnalyticsSection>
        <AnalyticsSection title="Email Delivery Performance" loading={loading.email} error={errors.email} onRetry={loadPrimary}>
          <EmailAnalytics data={data.email} />
        </AnalyticsSection>
      </div>

      <AnalyticsSection title="Top Customers" subtitle="Sort and page through aggregated customer performance."
        loading={loading.customers} error={errors.customers} onRetry={loadCustomers}>
        <CustomerAnalyticsTable data={data.customers} sorting={customerSort}
          onSort={(field) => { setCustomerPage(CUSTOMER_DEFAULT); toggleSort(setCustomerSort, customerSort, field) }}
          onPage={(offset) => setCustomerPage((page) => ({ ...page, offset }))} />
      </AnalyticsSection>
      <AnalyticsSection title="Product Performance" subtitle="Historical order-line volume and customer reach."
        loading={loading.products} error={errors.products} onRetry={loadProducts}>
        <ProductAnalyticsTable data={data.products} sorting={productSort}
          onSort={(field) => { setProductPage(PRODUCT_DEFAULT); toggleSort(setProductSort, productSort, field) }}
          onPage={(offset) => setProductPage((page) => ({ ...page, offset }))} />
      </AnalyticsSection>
    </div>
  )
}

export default AnalyticsDashboard
