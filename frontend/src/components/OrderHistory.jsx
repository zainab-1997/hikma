import { useEffect, useMemo, useState } from 'react'
import { listOrders, resolveApiUrl } from '../services/api'
import AppIcon from './ui/AppIcon'
import EmailHistoryModal from './EmailHistoryModal'
import OrderDetailModal from './OrderDetailModal'
import SendEmailModal from './SendEmailModal'

const PAGE_SIZE = 20
const EMPTY_FILTERS = { customer_name: '', governorate: '', price_type: '' }
const EMAIL_STATUS_LABELS = { sent: 'Sent', failed: 'Failed', sending: 'Sending', pending: 'Pending' }

function formatPriceType(value) {
  if (value === 'pharmacy') return 'Pharmacy & Hospital'
  if (value === 'drug_store') return 'Drug Store'
  return 'Unknown'
}

function formatDate(value) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return { date: value, time: '' }
  return { date: date.toLocaleDateString(), time: date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) }
}

function EmailStatus({ order }) {
  const status = order.email_status || 'none'
  const label = EMAIL_STATUS_LABELS[status] || 'Not sent'
  return <div className="history-email-status">
    <span className={`email-status-badge email-status-badge--${status}`}>{label}</span>
    {order.last_email_sent_at && <small>
      {order.email_status === 'sent' ? `Sent ${new Date(order.last_email_sent_at).toLocaleDateString()}` : `Previously sent ${new Date(order.last_email_sent_at).toLocaleDateString()}`}
    </small>}
  </div>
}

function OrderHistory() {
  const [filters, setFilters] = useState(EMPTY_FILTERS)
  const [appliedFilters, setAppliedFilters] = useState({})
  const [offset, setOffset] = useState(0)
  const [refreshKey, setRefreshKey] = useState(0)
  const [orders, setOrders] = useState([])
  const [total, setTotal] = useState(0)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState('')
  const [selectedOrderId, setSelectedOrderId] = useState(null)
  const [sendEmailOrder, setSendEmailOrder] = useState(null)
  const [emailHistoryOrderId, setEmailHistoryOrderId] = useState(null)

  useEffect(() => {
    let cancelled = false
    listOrders({ ...appliedFilters, limit: PAGE_SIZE, offset })
      .then((result) => {
        if (cancelled) return
        setOrders(result.orders)
        setTotal(result.total)
        setError('')
      })
      .catch((err) => { if (!cancelled) setError(err.message || 'Failed to load order history.') })
      .finally(() => { if (!cancelled) setIsLoading(false) })
    return () => { cancelled = true }
  }, [appliedFilters, offset, refreshKey])

  const currentPageValue = useMemo(
    () => orders.reduce((sum, order) => sum + order.selected_order_total, 0),
    [orders],
  )
  const sentCount = orders.filter((order) => order.email_status === 'sent').length
  const failedCount = orders.filter((order) => order.email_status === 'failed').length
  const selectedOrder = orders.find((order) => order.order_id === selectedOrderId)
  const hasNextPage = offset + PAGE_SIZE < total
  const hasPreviousPage = offset > 0

  const applyFilters = (event) => {
    event.preventDefault()
    setIsLoading(true)
    setOffset(0)
    setAppliedFilters({ ...filters })
  }
  const resetFilters = () => {
    setFilters(EMPTY_FILTERS)
    setAppliedFilters({})
    setOffset(0)
    setIsLoading(true)
  }
  const refresh = () => {
    setIsLoading(true)
    setRefreshKey((key) => key + 1)
  }
  const changePage = (nextOffset) => {
    setIsLoading(true)
    setOffset(nextOffset)
  }

  return (
    <div className="history-page">
      <header className="page-heading">
        <div><span className="page-heading__eyebrow">Operational records</span><h2>Order History</h2>
          <p>Review generated orders, download files, and manage email delivery.</p></div>
        <div className="page-heading__actions">
          <span className="result-count">{total.toLocaleString()} orders</span>
          <button type="button" className="btn btn--secondary" onClick={refresh} disabled={isLoading}>
            <AppIcon name="refresh" size={16} /> Refresh
          </button>
        </div>
      </header>

      <section className="card history-filters" aria-labelledby="history-filters-title">
        <div className="history-filters__heading"><div><h3 id="history-filters-title">Find orders</h3>
          <p>Filters apply only when you choose Apply Filters.</p></div></div>
        <form className="history-filter-grid" onSubmit={applyFilters}>
          <label className="field"><span className="field__label">Customer Name</span>
            <input type="text" className="field__input" dir="auto" placeholder="Search customer…"
              value={filters.customer_name} onChange={(event) => setFilters((current) => ({ ...current, customer_name: event.target.value }))} />
          </label>
          <label className="field"><span className="field__label">Governorate</span>
            <input type="text" className="field__input" dir="auto" placeholder="Search governorate…"
              value={filters.governorate} onChange={(event) => setFilters((current) => ({ ...current, governorate: event.target.value }))} />
          </label>
          <label className="field"><span className="field__label">Price Type</span>
            <select className="field__input" value={filters.price_type}
              onChange={(event) => setFilters((current) => ({ ...current, price_type: event.target.value }))}>
              <option value="">All price types</option>
              <option value="pharmacy">Pharmacy & Hospital</option>
              <option value="drug_store">Drug Store</option>
            </select>
          </label>
          <div className="history-filter-actions">
            <button type="button" className="btn btn--ghost" onClick={resetFilters}>Reset</button>
            <button type="submit" className="btn btn--primary">Apply Filters</button>
          </div>
        </form>
      </section>

      <section className="history-summary" aria-label="Current page summary">
        <article><span>Orders shown</span><strong>{orders.length}</strong></article>
        <article><span>Current page value</span><strong>{currentPageValue.toLocaleString()} <small>IQD</small></strong></article>
        <article><span>Sent emails</span><strong>{sentCount}</strong></article>
        <article><span>Failed emails</span><strong>{failedCount}</strong></article>
      </section>

      <section className="card history-records" aria-labelledby="history-records-title">
        <div className="history-records__heading"><h3 id="history-records-title">Generated orders</h3>
          {!isLoading && orders.length > 0 && <span>{offset + 1}–{Math.min(offset + PAGE_SIZE, total)} of {total}</span>}</div>
        {error && <div className="table-state table-state--error" role="alert">
          <strong>Unable to load order history.</strong><button type="button" className="btn btn--secondary btn--small" onClick={refresh}>Try again</button>
        </div>}
        {isLoading && <div className="table-state table-state--loading" role="status">
          <span className="table-loading-bar" /><span className="table-loading-bar" /><span className="table-loading-bar" />
          <p>Loading orders…</p>
        </div>}
        {!isLoading && !error && orders.length === 0 && <div className="table-state">
          <strong>No orders found</strong><p>Try changing or resetting the current filters.</p>
        </div>}
        {!isLoading && !error && orders.length > 0 && <div className="data-table-wrap">
          <table className="data-table history-table">
            <thead><tr>
              <th scope="col">Order</th><th scope="col">Customer</th><th scope="col">Governorate</th>
              <th scope="col">Price Type</th><th scope="col" className="numeric-cell">Total</th>
              <th scope="col">Created</th><th scope="col">Email</th><th scope="col" className="action-cell">Actions</th>
            </tr></thead>
            <tbody>{orders.map((order) => {
              const created = formatDate(order.created_at)
              return <tr key={order.order_id}>
                <td data-label="Order"><strong className="history-order-number">{order.order_number}</strong></td>
                <td data-label="Customer" dir="auto"><strong>{order.order_title || order.customer_name || 'Not provided'}</strong><small>{order.customer_type ? order.customer_type.replace('_', ' ') : 'Unknown type'}</small></td>
                <td data-label="Governorate" dir="auto">{order.governorate || 'Not provided'}</td>
                <td data-label="Price Type"><span className="record-badge">{formatPriceType(order.selected_price_type)}</span></td>
                <td data-label="Total" className="numeric-cell"><strong>{order.selected_order_total.toLocaleString()}</strong><small> IQD</small></td>
                <td data-label="Created"><span>{created.date}</span><small>{created.time}</small></td>
                <td data-label="Email"><EmailStatus order={order} /></td>
                <td data-label="Actions" className="action-cell"><div className="row-actions">
                  <button type="button" className="btn btn--secondary btn--small" onClick={() => setSelectedOrderId(order.order_id)}>View Details</button>
                  <a className="btn btn--ghost btn--small" href={resolveApiUrl(order.download_url)} download>Download</a>
                  <button type="button" className="btn btn--ghost btn--small" onClick={() => setSendEmailOrder(order)}>Send Email</button>
                  <button type="button" className="btn btn--ghost btn--small" onClick={() => setEmailHistoryOrderId(order.order_id)}>Email History</button>
                </div></td>
              </tr>
            })}</tbody>
          </table>
        </div>}
        {total > PAGE_SIZE && <div className="table-pagination">
          <span>{Math.min(offset + 1, total)}–{Math.min(offset + PAGE_SIZE, total)} of {total}</span>
          <div><button type="button" className="btn btn--secondary btn--small" disabled={!hasPreviousPage}
            onClick={() => changePage(Math.max(0, offset - PAGE_SIZE))}>Previous</button>
            <button type="button" className="btn btn--secondary btn--small" disabled={!hasNextPage}
              onClick={() => changePage(offset + PAGE_SIZE)}>Next</button></div>
        </div>}
      </section>

      {selectedOrderId && <OrderDetailModal orderId={selectedOrderId} onClose={() => setSelectedOrderId(null)}
        onSendEmail={selectedOrder ? () => { setSelectedOrderId(null); setSendEmailOrder(selectedOrder) } : undefined} />}
      {sendEmailOrder && <SendEmailModal orderId={sendEmailOrder.order_id} orderNumber={sendEmailOrder.order_number}
        generatedFilename={sendEmailOrder.download_url.split('/').pop()} onClose={() => setSendEmailOrder(null)} />}
      {emailHistoryOrderId && <EmailHistoryModal orderId={emailHistoryOrderId} onClose={() => setEmailHistoryOrderId(null)} />}
    </div>
  )
}

export default OrderHistory
