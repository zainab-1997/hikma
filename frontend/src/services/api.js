const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000').replace(/\/+$/, '')

function extractErrorMessage(errorBody, response) {
  const detail = errorBody?.detail
  const message = typeof detail === 'string' ? detail : null
  return message || `Request failed with status ${response.status}`
}

async function postJson(path, body) {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })

  if (!response.ok) {
    const errorBody = await response.json().catch(() => null)
    throw new Error(extractErrorMessage(errorBody, response))
  }

  return response.json()
}

async function getJson(path, params) {
  const queryString = buildQueryString(params)
  const query = queryString ? `?${queryString}` : ''
  const response = await fetch(`${API_BASE_URL}${path}${query}`)

  if (!response.ok) {
    const errorBody = await response.json().catch(() => null)
    throw new Error(extractErrorMessage(errorBody, response))
  }

  return response.json()
}

export function buildQueryString(params = {}) {
  const safeParams = Object.fromEntries(
    Object.entries(params).filter(([, value]) => value !== undefined && value !== null && value !== ''),
  )
  return new URLSearchParams(safeParams).toString()
}

export async function checkBackendHealth() {
  const response = await fetch(`${API_BASE_URL}/api/health/live`)

  if (!response.ok) {
    throw new Error(`Health check failed with status ${response.status}`)
  }

  return response.json()
}

export function parseOrder(message) {
  return postJson('/api/orders/parse', { message })
}

export function applyBusinessRules(reviewInput) {
  return postJson('/api/orders/apply-rules', reviewInput)
}

export function matchProducts(reviewOrder) {
  return postJson('/api/orders/match-products', reviewOrder)
}

export function searchProducts(searchText) {
  return getJson('/api/products', searchText ? { search: searchText } : undefined)
}

export function selectProduct(row, officialName) {
  return postJson('/api/products/select', { row, official_name: officialName })
}

export function generateExcelOrder(request) {
  return postJson('/api/orders/generate-excel', request)
}

export function listOrders(filters = {}) {
  const params = Object.fromEntries(
    Object.entries(filters).filter(([, value]) => value !== undefined && value !== null && value !== ''),
  )
  return getJson('/api/orders', Object.keys(params).length ? params : undefined)
}

export function getOrderDetail(orderId) {
  return getJson(`/api/orders/${encodeURIComponent(orderId)}`)
}

export function getEmailConfig() {
  return getJson('/api/email/config')
}

export function sendOrderEmail(orderId, request) {
  return postJson(`/api/orders/${encodeURIComponent(orderId)}/send-email`, request)
}

export function listOrderEmails(orderId) {
  return getJson(`/api/orders/${encodeURIComponent(orderId)}/emails`)
}

export function getOrderEmailDetail(orderId, deliveryId) {
  return getJson(`/api/orders/${encodeURIComponent(orderId)}/emails/${encodeURIComponent(deliveryId)}`)
}

export function resolveApiUrl(path) {
  return `${API_BASE_URL}${path}`
}

const CUSTOMER_SORT_FIELDS = new Set([
  'customer_name', 'order_count', 'total_sales', 'average_order_value', 'latest_order_date',
])
const PRODUCT_SORT_FIELDS = new Set([
  'official_product_name', 'total_quantity', 'total_free_quantity', 'order_count', 'unique_customer_count',
])
const SORT_DIRECTIONS = new Set(['asc', 'desc'])

function analyticsParams(filters = {}, extra = {}) {
  return { ...filters, ...extra }
}

export function getAnalyticsOverview(filters) {
  return getJson('/api/analytics/overview', analyticsParams(filters))
}

export function getSalesOverTime(filters, granularity) {
  return getJson('/api/analytics/sales-over-time', analyticsParams(filters, { granularity }))
}

export function getAnalyticsByGovernorate(filters) {
  return getJson('/api/analytics/by-governorate', analyticsParams(filters))
}

export function getAnalyticsByCustomer(filters, pagination, sorting) {
  const sortBy = CUSTOMER_SORT_FIELDS.has(sorting.sort_by) ? sorting.sort_by : 'total_sales'
  const sortDirection = SORT_DIRECTIONS.has(sorting.sort_direction) ? sorting.sort_direction : 'desc'
  return getJson('/api/analytics/by-customer', analyticsParams(filters, {
    limit: pagination.limit,
    offset: pagination.offset,
    sort_by: sortBy,
    sort_direction: sortDirection,
  }))
}

export function getProductAnalytics(filters, pagination, sorting) {
  const sortBy = PRODUCT_SORT_FIELDS.has(sorting.sort_by) ? sorting.sort_by : 'total_quantity'
  const sortDirection = SORT_DIRECTIONS.has(sorting.sort_direction) ? sorting.sort_direction : 'desc'
  return getJson('/api/analytics/products', analyticsParams(filters, {
    limit: pagination.limit,
    offset: pagination.offset,
    sort_by: sortBy,
    sort_direction: sortDirection,
  }))
}

export function getPriceTypeAnalytics(filters) {
  return getJson('/api/analytics/price-types', analyticsParams(filters))
}

export function getCustomerTypeAnalytics(filters) {
  return getJson('/api/analytics/customer-types', analyticsParams(filters))
}

export function getEmailDeliveryAnalytics(filters) {
  return getJson('/api/analytics/email-deliveries', analyticsParams(filters))
}

export function getAnalyticsFilterOptions() {
  return getJson('/api/analytics/filter-options')
}
